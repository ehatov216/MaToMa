"""MarkovTimescale — 上位タイムスケール（256s+）のMarkov連鎖状態機械。

5つのマクロ状態（void/sparse/medium/dense/intense）を遷移し、
ChaosEngineの引力点を切り替えることでサウンドの大局的方向性を制御する。

制御比率: Markov 70% + フィードバック（エネルギー推定）30%
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import TYPE_CHECKING, Awaitable, Callable

from tidal_patterns import get_preset

if TYPE_CHECKING:
    from autonomous import ChaosEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 5つのマクロ状態と引力点
# ---------------------------------------------------------------------------

STATES: list[str] = ["void", "sparse", "medium", "dense", "intense"]

# 各状態でChaosEngineに設定する引力点
STATE_ATTRACTORS: dict[str, dict[str, dict[str, float]]] = {
    "void": {
        "granular": {"density": 5.0, "spray": 0.1, "pos": 0.5, "room": 0.8},
        "drone": {
            "shimmer": 0.1, "feedback_amt": 0.1,
            "room": 0.8, "amp": 0.15,
        },
        "gran_synth": {
            "density": 8.0, "bright": 0.1,
            "chaos": 0.1, "room": 0.9, "amp": 0.1,
        },
        "gran_sampler": {
            "density": 5.0, "spray": 0.1, "pos": 0.5,
            "room": 0.9, "amp": 0.1,
        },
    },
    "sparse": {
        "granular": {"density": 10.0, "spray": 0.3, "pos": 0.5, "room": 0.6},
        "drone": {
            "shimmer": 0.3, "feedback_amt": 0.2,
            "room": 0.7, "amp": 0.25,
        },
        "gran_synth": {
            "density": 15.0, "bright": 0.3,
            "chaos": 0.2, "room": 0.7, "amp": 0.2,
        },
        "gran_sampler": {
            "density": 10.0, "spray": 0.2, "pos": 0.5,
            "room": 0.7, "amp": 0.2,
        },
    },
    "medium": {
        "granular": {"density": 15.0, "spray": 0.5, "pos": 0.5, "room": 0.5},
        "drone": {
            "shimmer": 0.4, "feedback_amt": 0.25,
            "room": 0.7, "amp": 0.35,
        },
        "gran_synth": {
            "density": 30.0, "bright": 0.4,
            "chaos": 0.3, "room": 0.6, "amp": 0.35,
        },
        "gran_sampler": {
            "density": 20.0, "spray": 0.3, "pos": 0.5,
            "room": 0.5, "amp": 0.4,
        },
    },
    "dense": {
        "granular": {"density": 25.0, "spray": 0.6, "pos": 0.5, "room": 0.4},
        "drone": {
            "shimmer": 0.6, "feedback_amt": 0.35,
            "room": 0.6, "amp": 0.5,
        },
        "gran_synth": {
            "density": 45.0, "bright": 0.6,
            "chaos": 0.5, "room": 0.4, "amp": 0.5,
        },
        "gran_sampler": {
            "density": 35.0, "spray": 0.5, "pos": 0.5,
            "room": 0.4, "amp": 0.55,
        },
    },
    "intense": {
        "granular": {"density": 35.0, "spray": 0.7, "pos": 0.5, "room": 0.3},
        "drone": {
            "shimmer": 0.8, "feedback_amt": 0.45,
            "room": 0.5, "amp": 0.65,
        },
        "gran_synth": {
            "density": 55.0, "bright": 0.8,
            "chaos": 0.7, "room": 0.3, "amp": 0.65,
        },
        "gran_sampler": {
            "density": 50.0, "spray": 0.7, "pos": 0.5,
            "room": 0.3, "amp": 0.7,
        },
    },
}

# 各状態のグローバル設定（speed / dejavu_prob）
STATE_GLOBALS: dict[str, dict[str, float]] = {
    "void":    {"speed": 0.3, "dejavu_prob": 0.5},
    "sparse":  {"speed": 0.5, "dejavu_prob": 0.4},
    "medium":  {"speed": 0.8, "dejavu_prob": 0.3},
    "dense":   {"speed": 1.2, "dejavu_prob": 0.15},
    "intense": {"speed": 1.8, "dejavu_prob": 0.05},
}

# 遷移行列: 行=現在状態, 列=次状態 (void/sparse/medium/dense/intense)
BASE_MATRIX: dict[str, list[float]] = {
    "void":    [0.40, 0.40, 0.15, 0.04, 0.01],
    "sparse":  [0.20, 0.35, 0.35, 0.08, 0.02],
    "medium":  [0.05, 0.20, 0.40, 0.25, 0.10],
    "dense":   [0.02, 0.08, 0.30, 0.40, 0.20],
    "intense": [0.05, 0.10, 0.25, 0.40, 0.20],
}

# エネルギー閾値
_ENERGY_HIGH = 0.65  # これを超えたら void/sparse 方向へ +30%
_ENERGY_LOW = 0.25  # これを下回ったら dense/intense 方向へ +30%

# Markov vs フィードバックの比率
_MARKOV_WEIGHT = 0.70
_FEEDBACK_WEIGHT = 0.30

# 各Markov状態に対応するTidalプリセット名
TIDAL_PRESET_BY_STATE: dict[str, str] = {
    "void":    "minimal_klank",
    "sparse":  "opn_sparse",
    "medium":  "alva_euclidean",
    "dense":   "alva_phase",
    "intense": "chaos_collapse",
}


# ---------------------------------------------------------------------------
# MarkovTimescale クラス
# ---------------------------------------------------------------------------

class MarkovTimescale:
    """Markov連鎖で5状態を遷移し、ChaosEngineに引力点を設定する。

    Args:
        chaos_engine: ChaosEngine インスタンス（引力点設定用）
        interval: 状態遷移間隔（秒）。デフォルト60s。
    """

    def __init__(
        self,
        chaos_engine: ChaosEngine,
        broadcast: Callable[[dict], Awaitable[None]],
        interval: float = 60.0,
        tidal_controller=None,
    ) -> None:
        self._chaos = chaos_engine
        self._broadcast = broadcast
        self._interval = interval
        self._tidal = tidal_controller
        self._state: str = "medium"
        self._running: bool = False
        self._task: asyncio.Task | None = None
        self._state_start: float = 0.0
        self._current_speed: float = STATE_GLOBALS["medium"]["speed"]
        self._current_dejavu_prob: float = (
            STATE_GLOBALS["medium"]["dejavu_prob"]
        )

    # ------------------------------------------------------------------
    # 公開API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Markovループを開始する。既に動いている場合は何もしない。"""
        if self._running:
            return
        self._running = True
        self._state_start = time.time()
        self._task = asyncio.ensure_future(self._loop())
        logger.info(
            "[Markov] started  state=%s  interval=%.1fs",
            self._state, self._interval,
        )

    def stop(self) -> None:
        """Markovループを停止する。"""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None
        logger.info("[Markov] stopped")

    def set_interval(self, seconds: float) -> None:
        """遷移間隔を変更する（次の遷移から適用）。"""
        self._interval = max(5.0, float(seconds))
        logger.info("[Markov] interval → %.1fs", self._interval)

    def get_state(self) -> dict:
        """現在の状態情報を返す（フロントエンド表示用）。"""
        elapsed = time.time() - self._state_start if self._running else 0.0
        remaining = max(0.0, self._interval - elapsed)
        return {
            "running": self._running,
            "state": self._state,
            "interval": self._interval,
            "elapsed": round(elapsed, 1),
            "remaining": round(remaining, 1),
            "speed": self._current_speed,
            "dejavu_prob": self._current_dejavu_prob,
        }

    # ------------------------------------------------------------------
    # 内部ループ
    # ------------------------------------------------------------------

    async def _loop(self) -> None:
        try:
            # まず現在状態の引力点を即適用し、状態をブロードキャスト
            self._apply_state(self._state)
            _msg = {"type": "markov_state", "state": self.get_state()}
            asyncio.ensure_future(self._broadcast(_msg))

            while self._running:
                # interval 秒を1秒ごとに分割し、カウントダウンを配信
                elapsed = 0.0
                while self._running and elapsed < self._interval:
                    await asyncio.sleep(1.0)
                    elapsed += 1.0
                    _msg = {"type": "markov_state", "state": self.get_state()}
                    asyncio.ensure_future(self._broadcast(_msg))

                if not self._running:
                    break

                next_state = self._next_state()
                logger.info(
                    "[Markov] %s → %s  (interval=%.1fs)",
                    self._state, next_state, self._interval,
                )
                self._state = next_state
                self._state_start = time.time()
                self._apply_state(next_state)
                _msg = {"type": "markov_state", "state": self.get_state()}
                asyncio.ensure_future(self._broadcast(_msg))
        except asyncio.CancelledError:
            pass

    def _next_state(self) -> str:
        """Markov 70% + エネルギーフィードバック 30% で次状態を選ぶ。"""
        current_idx = STATES.index(self._state)
        markov_probs = list(BASE_MATRIX[self._state])  # コピー

        # フィードバック補正
        energy = self._compute_energy()
        feedback_probs = list(markov_probs)  # ベースからコピー
        if energy > _ENERGY_HIGH:
            # 高エネルギー → 静かな方向を強調 (idx 0=void, 1=sparse)
            for i in [0, 1]:
                feedback_probs[i] *= 1.30
        elif energy < _ENERGY_LOW:
            # 低エネルギー → 活発な方向を強調 (idx 3=dense, 4=intense)
            for i in [3, 4]:
                feedback_probs[i] *= 1.30

        # 70/30 ブレンド
        total_m = sum(markov_probs) or 1.0
        total_f = sum(feedback_probs) or 1.0
        blended = [
            _MARKOV_WEIGHT * (markov_probs[i] / total_m)
            + _FEEDBACK_WEIGHT * (feedback_probs[i] / total_f)
            for i in range(len(STATES))
        ]

        # 重み付きサンプリング
        r = random.random()
        cumulative = 0.0
        total_b = sum(blended)
        for i, w in enumerate(blended):
            cumulative += w / total_b
            if r <= cumulative:
                return STATES[i]
        return STATES[current_idx]  # フォールバック

    def _compute_energy(self) -> float:
        """ChaosEngineの現在値からエネルギーを 0〜1 で推定する。

        4ソースの加重平均:
          granular.density (÷40)   × 0.30
          gran_synth.density (÷60) × 0.25
          gran_sampler.density(÷55)× 0.25
          drone.amp                × 0.20
        """
        try:
            state = self._chaos.get_state()

            def _v(layer: str, param: str, default: float) -> float:
                return state.get(layer, {}).get(param, {}).get("value", default)

            gran_density = min(1.0, _v("granular", "density", 15.0) / 40.0)
            synth_density = min(1.0, _v("gran_synth", "density", 30.0) / 60.0)
            samp_density = min(
                1.0, _v("gran_sampler", "density", 20.0) / 55.0
            )
            drone_amp = _v("drone", "amp", 0.35)

            energy = (
                0.30 * gran_density
                + 0.25 * synth_density
                + 0.25 * samp_density
                + 0.20 * drone_amp
            )
            return min(1.0, max(0.0, energy))
        except Exception:
            return 0.5  # 取得失敗時は中立

    def _apply_state(self, state: str) -> None:
        """ChaosEngineの全レイヤーに引力点とグローバル設定を適用する。"""
        attractors = STATE_ATTRACTORS[state]
        for layer, params in attractors.items():
            for param, value in params.items():
                try:
                    self._chaos.set_attractor(layer, param, value)
                except Exception as e:
                    logger.warning(
                        "[Markov] set_attractor failed  layer=%s param=%s: %s",
                        layer, param, e,
                    )
        globals_ = STATE_GLOBALS[state]
        self._current_speed = globals_["speed"]
        self._current_dejavu_prob = globals_["dejavu_prob"]
        self._chaos.set_speed(self._current_speed)
        self._chaos.set_dejavu_prob(self._current_dejavu_prob)
        logger.debug("[Markov] applied state=%s", state)

        # Tidalプリセットを自動切換え
        if self._tidal is not None:
            preset_name = TIDAL_PRESET_BY_STATE[state]
            try:
                codes = get_preset(preset_name)
                for code in codes:
                    self._tidal.evaluate(code)
                self._tidal.state["preset"] = preset_name
                asyncio.ensure_future(
                    self._broadcast(
                        {"type": "tidal_applied", "preset": preset_name}
                    )
                )
                logger.info("[Markov] tidal preset → %s", preset_name)
            except Exception as e:
                logger.warning("[Markov] tidal preset failed: %s", e)
