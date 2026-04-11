"""
ThreeLayerController — 3層時間制御システム。

Upper（Markov状態機械）が Middle と Lower の両方に独立した制御パラメーターを渡す。
Middle（BoundedWalk）はUpperのゾーン内をドリフトし、
Lower（Dejavu）はMiddleの現在値を参照点として微変動する。

制御フロー:
  Upper（Markov状態）
    ├── center/width/speed ───→ Middle（どこをどう動くか）
    └── snap_prob/micro_range ─→ Lower（どれくらい揺らすか）
                                      ↑
  Middle の現在値 ───────────────────┘（参照点）
  Lower → OSC 送信
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from collections import deque
from dataclasses import dataclass
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

# ── 定数 ─────────────────────────────────────────────────────────────────
HISTORY_LEN     = 8
UPDATE_INTERVAL = 0.1   # 秒（10Hz）

# ── パラメーター仕様 ──────────────────────────────────────────────────────
# {layer: {param: (min_val, max_val, init_val, osc_address)}}
PARAM_SPECS: dict[str, dict[str, tuple]] = {
    "drone": {
        "feedback_amt": (0.0,  1.0,  0.25, "/matoma/drone/param"),
        "shimmer":      (0.0,  1.0,  0.40, "/matoma/drone/param"),
        "room":         (0.0,  1.0,  0.70, "/matoma/drone/param"),
        "amp":          (0.0,  1.0,  0.35, "/matoma/drone/param"),
    },
    "granular": {
        "density": (1.0,  60.0, 15.0, "/matoma/granular/param"),
        "spray":   (0.0,  1.0,  0.50, "/matoma/granular/param"),
        "pos":     (0.0,  1.0,  0.50, "/matoma/granular/param"),
        "room":    (0.0,  1.0,  0.50, "/matoma/granular/param"),
    },
    "gran_synth": {
        "density":  (1.0,  80.0, 35.0, "/matoma/gran_synth/param"),
        "grainDur": (0.01, 1.0,  0.18, "/matoma/gran_synth/param"),
        "bright":   (0.0,  1.0,  0.40, "/matoma/gran_synth/param"),
        "chaos":    (0.0,  1.0,  0.30, "/matoma/gran_synth/param"),
        "room":     (0.0,  1.0,  0.60, "/matoma/gran_synth/param"),
        "amp":      (0.0,  1.0,  0.40, "/matoma/gran_synth/param"),
    },
    "gran_sampler": {
        "pos":     (0.0,  1.0,  0.50, "/matoma/gran_sampler/param"),
        "density": (1.0,  70.0, 20.0, "/matoma/gran_sampler/param"),
        "spray":   (0.0,  1.0,  0.30, "/matoma/gran_sampler/param"),
        "room":    (0.0,  1.0,  0.40, "/matoma/gran_sampler/param"),
        "amp":     (0.0,  1.0,  0.50, "/matoma/gran_sampler/param"),
    },
    # melody レイヤー: Tidal Control Channel 経由でリズムパターンの音程を制御
    # osc_address="_tidal_ctrl" は送信先 Tidal ctrl ポート(6010)への振り分けを示すセンチネル
    # note: MIDI ノート番号 36=C2, 48=C3, 60=C4(中央C), 72=C5
    "melody": {
        "note": (36.0, 72.0, 48.0, "_tidal_ctrl"),
    },
    # rhythmic レイヤー: Tidal Control Channel 経由でd1/d2/d3の疎密・音量・音程を制御
    # degrade max=0.70 → d3の +0.2 加算後も 0.90 を超えない設計
    "rhythmic": {
        "degrade": (0.0,   0.70,   0.30, "_tidal_ctrl"),
        "amp":     (0.0,   1.0,    0.50, "_tidal_ctrl"),
        "freq":    (80.0,  600.0, 300.0, "_tidal_ctrl"),
    },
}

# ── Markov 状態定義 ───────────────────────────────────────────────────────
STATES: list[str] = ["void", "sparse", "medium", "dense", "intense"]

# {state: {layer: {param: {"center": float, "width": float}}}}
# center: Middle がドリフトする引力中心
# width:  Middle が center からどれだけ離れられるか（ゾーン半幅）
STATE_ZONES: dict[str, dict[str, dict[str, dict[str, float]]]] = {
    "void": {
        # void: ほぼ完全な静寂・消音状態
        "drone": {
            "feedback_amt": {"center": 0.03, "width": 0.03},
            "shimmer":      {"center": 0.03, "width": 0.03},
            "room":         {"center": 0.95, "width": 0.04},  # 広大なリバーブ=音が霧散する
            "amp":          {"center": 0.04, "width": 0.02},  # ほぼ消音
        },
        "granular": {
            "density": {"center":  2.0, "width": 1.5},   # 極少粒
            "spray":   {"center": 0.04, "width": 0.03},
            "pos":     {"center": 0.50, "width": 0.10},
            "room":    {"center": 0.92, "width": 0.05},
        },
        "gran_synth": {
            "density":  {"center":  3.0, "width": 2.0},  # 極少粒
            "grainDur": {"center": 0.35, "width": 0.10}, # 長いグレイン=ぼんやり
            "bright":   {"center": 0.03, "width": 0.03}, # 極暗い
            "chaos":    {"center": 0.03, "width": 0.02}, # 秩序的・動かない
            "room":     {"center": 0.95, "width": 0.04},
            "amp":      {"center": 0.03, "width": 0.02}, # ほぼ消音
        },
        "gran_sampler": {
            "pos":     {"center": 0.50, "width": 0.10},
            "density": {"center":  2.0, "width": 1.5},
            "spray":   {"center": 0.04, "width": 0.03},
            "room":    {"center": 0.95, "width": 0.04},
            "amp":     {"center": 0.03, "width": 0.02}, # ほぼ消音
        },
        # void: 極低音（C2付近）・ほぼ動かない
        "melody": {
            "note": {"center": 36.0, "width": 3.0},
        },
        # void: リズムほぼ消音（degrade高い=音が消える）
        "rhythmic": {
            "degrade": {"center": 0.82, "width": 0.05}, # 82%消音
            "amp":     {"center": 0.04, "width": 0.03},
            "freq":    {"center":  80.0, "width": 15.0},
        },
    },
    "sparse": {
        # sparse: 静寂からわずかに息吹く・点描
        "drone": {
            "feedback_amt": {"center": 0.18, "width": 0.08},
            "shimmer":      {"center": 0.25, "width": 0.10},
            "room":         {"center": 0.78, "width": 0.08},
            "amp":          {"center": 0.22, "width": 0.06},
        },
        "granular": {
            "density": {"center":  9.0, "width": 4.0},
            "spray":   {"center": 0.22, "width": 0.10},
            "pos":     {"center": 0.50, "width": 0.18},
            "room":    {"center": 0.68, "width": 0.10},
        },
        "gran_synth": {
            "density":  {"center": 15.0, "width": 6.0},
            "grainDur": {"center": 0.24, "width": 0.08},
            "bright":   {"center": 0.22, "width": 0.10},
            "chaos":    {"center": 0.18, "width": 0.08},
            "room":     {"center": 0.75, "width": 0.08},
            "amp":      {"center": 0.18, "width": 0.06},
        },
        "gran_sampler": {
            "pos":     {"center": 0.50, "width": 0.18},
            "density": {"center":  9.0, "width": 4.0},
            "spray":   {"center": 0.16, "width": 0.08},
            "room":    {"center": 0.75, "width": 0.08},
            "amp":     {"center": 0.18, "width": 0.06},
        },
        # sparse: 低音〜中低音（A2付近）
        "melody": {
            "note": {"center": 45.0, "width": 6.0},
        },
        # sparse: 散発的・低音
        "rhythmic": {
            "degrade": {"center": 0.60, "width": 0.10},
            "amp":     {"center": 0.26, "width": 0.08},
            "freq":    {"center": 160.0, "width": 35.0},
        },
    },
    "medium": {
        # medium: バランスの取れた中間地点
        "drone": {
            "feedback_amt": {"center": 0.30, "width": 0.10},
            "shimmer":      {"center": 0.48, "width": 0.15},
            "room":         {"center": 0.58, "width": 0.10},
            "amp":          {"center": 0.44, "width": 0.07},
        },
        "granular": {
            "density": {"center": 18.0, "width": 6.0},
            "spray":   {"center": 0.48, "width": 0.16},
            "pos":     {"center": 0.50, "width": 0.25},
            "room":    {"center": 0.48, "width": 0.12},
        },
        "gran_synth": {
            "density":  {"center": 38.0, "width": 10.0},
            "grainDur": {"center": 0.16, "width": 0.07},
            "bright":   {"center": 0.45, "width": 0.14},
            "chaos":    {"center": 0.40, "width": 0.14},
            "room":     {"center": 0.55, "width": 0.10},
            "amp":      {"center": 0.44, "width": 0.07},
        },
        "gran_sampler": {
            "pos":     {"center": 0.50, "width": 0.25},
            "density": {"center": 25.0, "width": 8.0},
            "spray":   {"center": 0.38, "width": 0.14},
            "room":    {"center": 0.50, "width": 0.10},
            "amp":     {"center": 0.50, "width": 0.07},
        },
        # medium: 中音域（F#3付近）
        "melody": {
            "note": {"center": 54.0, "width": 8.0},
        },
        # medium: 標準密度・中音域
        "rhythmic": {
            "degrade": {"center": 0.33, "width": 0.08},
            "amp":     {"center": 0.50, "width": 0.08},
            "freq":    {"center": 290.0, "width": 55.0},
        },
    },
    "dense": {
        # dense: 音が溢れ始める・緊張感
        "drone": {
            "feedback_amt": {"center": 0.52, "width": 0.12},
            "shimmer":      {"center": 0.72, "width": 0.16},
            "room":         {"center": 0.36, "width": 0.10},
            "amp":          {"center": 0.66, "width": 0.07},
        },
        "granular": {
            "density": {"center": 38.0, "width": 10.0},
            "spray":   {"center": 0.68, "width": 0.16},
            "pos":     {"center": 0.50, "width": 0.32},
            "room":    {"center": 0.28, "width": 0.10},
        },
        "gran_synth": {
            "density":  {"center": 62.0, "width": 14.0},
            "grainDur": {"center": 0.09, "width": 0.04},
            "bright":   {"center": 0.72, "width": 0.16},
            "chaos":    {"center": 0.68, "width": 0.16},
            "room":     {"center": 0.28, "width": 0.08},
            "amp":      {"center": 0.68, "width": 0.07},
        },
        "gran_sampler": {
            "pos":     {"center": 0.50, "width": 0.32},
            "density": {"center": 55.0, "width": 12.0},
            "spray":   {"center": 0.65, "width": 0.16},
            "room":    {"center": 0.28, "width": 0.08},
            "amp":     {"center": 0.72, "width": 0.07},
        },
        # dense: 中高音域（D4付近）
        "melody": {
            "note": {"center": 62.0, "width": 9.0},
        },
        # dense: 高密度・中高音
        "rhythmic": {
            "degrade": {"center": 0.08, "width": 0.05},
            "amp":     {"center": 0.76, "width": 0.08},
            "freq":    {"center": 450.0, "width": 85.0},
        },
    },
    "intense": {
        # intense: 飽和・爆発・音が溢れ出す
        "drone": {
            "feedback_amt": {"center": 0.72, "width": 0.15},
            "shimmer":      {"center": 0.94, "width": 0.05},
            "room":         {"center": 0.14, "width": 0.08}, # ほぼドライ=圧迫感
            "amp":          {"center": 0.88, "width": 0.07},
        },
        "granular": {
            "density": {"center": 58.0, "width": 12.0},
            "spray":   {"center": 0.88, "width": 0.08},
            "pos":     {"center": 0.50, "width": 0.40},
            "room":    {"center": 0.12, "width": 0.08},
        },
        "gran_synth": {
            "density":  {"center": 88.0, "width": 18.0}, # 最大粒密度
            "grainDur": {"center": 0.05, "width": 0.03}, # 極短グレイン=ノイズ的
            "bright":   {"center": 0.94, "width": 0.05}, # 極明るい
            "chaos":    {"center": 0.92, "width": 0.07}, # 極カオス
            "room":     {"center": 0.12, "width": 0.07},
            "amp":      {"center": 0.88, "width": 0.07},
        },
        "gran_sampler": {
            "pos":     {"center": 0.50, "width": 0.40},
            "density": {"center": 78.0, "width": 14.0},
            "spray":   {"center": 0.86, "width": 0.10},
            "room":    {"center": 0.12, "width": 0.07},
            "amp":     {"center": 0.90, "width": 0.07},
        },
        # intense: 高音域（Bb4付近）・最大揺れ幅
        "melody": {
            "note": {"center": 70.0, "width": 10.0},
        },
        # intense: 最高密度・ほぼ途切れない
        "rhythmic": {
            "degrade": {"center": 0.01, "width": 0.01}, # ほぼ100%発音
            "amp":     {"center": 0.94, "width": 0.05},
            "freq":    {"center": 640.0, "width": 110.0},
        },
    },
}

# Markov状態ごとのグローバル制御パラメーター
# speed      : Middleのドリフト速度（大きいほど速くzoneに引き寄せられる）
# snap_prob  : LowerのDejavu確率（Upperが直接制御）
# micro_ratio: Lowerの微変動幅 = zone.width × micro_ratio
STATE_CONTROLS: dict[str, dict[str, float]] = {
    "void":    {"speed": 0.3,  "snap_prob": 0.50, "micro_ratio": 0.15},
    "sparse":  {"speed": 0.5,  "snap_prob": 0.40, "micro_ratio": 0.20},
    "medium":  {"speed": 0.8,  "snap_prob": 0.30, "micro_ratio": 0.25},
    "dense":   {"speed": 1.2,  "snap_prob": 0.15, "micro_ratio": 0.35},
    "intense": {"speed": 1.8,  "snap_prob": 0.05, "micro_ratio": 0.50},
}

BASE_MATRIX: dict[str, list[float]] = {
    "void":    [0.40, 0.40, 0.15, 0.04, 0.01],
    "sparse":  [0.20, 0.35, 0.35, 0.08, 0.02],
    "medium":  [0.05, 0.20, 0.40, 0.25, 0.10],
    "dense":   [0.02, 0.08, 0.30, 0.40, 0.20],
    "intense": [0.05, 0.10, 0.25, 0.40, 0.20],
}

_ENERGY_HIGH     = 0.65
_ENERGY_LOW      = 0.25
_MARKOV_WEIGHT   = 0.70
_FEEDBACK_WEIGHT = 0.30


# ── データクラス ──────────────────────────────────────────────────────────

@dataclass
class UpperControl:
    """UpperLayerが各パラメーターに渡す制御仕様。"""
    center:      float  # Middleの引力中心
    width:       float  # Middleがうろつけるzone半幅
    speed:       float  # Middleのドリフト速度
    snap_prob:   float  # LowerのDejavu確率
    micro_range: float  # Lowerの微変動幅（= width × micro_ratio）
    floor:       float  # 絶対最小値（パラメーター仕様由来）
    ceiling:     float  # 絶対最大値（パラメーター仕様由来）


@dataclass
class _ParamState:
    """1パラメーターの実行時状態（イミュータブル更新）。"""
    current:     float  # Lowerの出力値（OSC送信済みの最終値）
    middle:      float  # Middleの現在値（Lowerの参照点）
    osc_address: str

    def with_values(self, current: float, middle: float) -> "_ParamState":
        return _ParamState(
            current=current,
            middle=middle,
            osc_address=self.osc_address,
        )


# ── Middle / Lower 計算関数 ───────────────────────────────────────────────

def _middle_next(current: float, ctrl: UpperControl) -> float:
    """BoundedWalk: Upper ゾーンの中心に引き寄せられながらランダムにドリフト。

    drift: center方向への引き（speed が大きいほど速い）
    noise: zone幅に比例したランダム摂動
    """
    drift = (ctrl.center - current) * ctrl.speed * 0.10
    noise = random.gauss(0.0, ctrl.width * ctrl.speed * 0.05)
    new_val = current + drift + noise
    lo = max(ctrl.floor, ctrl.center - ctrl.width)
    hi = min(ctrl.ceiling, ctrl.center + ctrl.width)
    return max(lo, min(hi, new_val))


def _lower_next(
    middle: float,
    ctrl: UpperControl,
    history: deque[float],
) -> float:
    """Dejavu: Middle値の周辺で微変動。snap_prob で過去値へスナップバック。

    スナップ時: 過去の記憶から値を取り出す（floor/ceiling にクランプ）
    非スナップ時: middle ± micro_range の小さな揺れ
    """
    if history and random.random() < ctrl.snap_prob:
        past = random.choice(list(history))
        return max(ctrl.floor, min(ctrl.ceiling, past))
    noise = random.gauss(0.0, ctrl.micro_range * 0.5)
    return max(ctrl.floor, min(ctrl.ceiling, middle + noise))


# ── UpperLayer ────────────────────────────────────────────────────────────

class UpperLayer:
    """Markov状態機械。60秒ごとに5状態を遷移し、UpperControl を生成する。

    各パラメーターに渡す UpperControl（center/width/speed/snap_prob/micro_range）
    はすべて現在のMarkov状態から計算する。
    """

    def __init__(
        self,
        broadcast: Callable[[dict], Awaitable[None]],
        interval: float = 60.0,
        tidal_controller=None,
        energy_fn: Callable[[], float] | None = None,
    ) -> None:
        self._broadcast = broadcast
        self._interval = interval
        self._tidal = tidal_controller
        self._energy_fn = energy_fn
        self._state: str = "medium"
        self._running = False
        self._task: asyncio.Task | None = None
        self._state_start: float = 0.0
        # 手動オーバーライド: {(layer, param): {"center": float, "width": float}}
        self._overrides: dict[tuple, dict[str, float]] = {}
        # グローバルオーバーライド（bridge.py からの手動調整）
        self._speed_override: float | None = None
        self._snap_override: float | None = None

    def get_control(self, layer: str, param: str) -> UpperControl:
        """現在のMarkov状態から UpperControl を生成する。"""
        zone = STATE_ZONES[self._state][layer][param]
        ctrl = STATE_CONTROLS[self._state]

        # 手動オーバーライドを適用
        override = self._overrides.get((layer, param))
        center = override["center"] if override else zone["center"]
        width  = override.get("width", zone["width"]) if override else zone["width"]

        speed     = self._speed_override   if self._speed_override  is not None else ctrl["speed"]
        snap_prob = self._snap_override    if self._snap_override    is not None else ctrl["snap_prob"]

        min_val, max_val = PARAM_SPECS[layer][param][0], PARAM_SPECS[layer][param][1]
        return UpperControl(
            center=center,
            width=width,
            speed=speed,
            snap_prob=snap_prob,
            micro_range=width * ctrl["micro_ratio"],
            floor=min_val,
            ceiling=max_val,
        )

    def get_state_info(self) -> dict:
        """フロントエンド用状態情報（markov_state メッセージで送信）。"""
        elapsed = time.time() - self._state_start if self._running else 0.0
        ctrl = STATE_CONTROLS[self._state]
        return {
            "running":     self._running,
            "state":       self._state,
            "interval":    self._interval,
            "elapsed":     round(elapsed, 1),
            "remaining":   round(max(0.0, self._interval - elapsed), 1),
            "speed":       self._speed_override or ctrl["speed"],
            "dejavu_prob": self._snap_override  or ctrl["snap_prob"],
        }

    def set_zone_override(
        self,
        layer: str,
        param: str,
        center: float,
        width: float | None = None,
    ) -> None:
        """特定パラメーターのゾーン中心を手動上書きする（引力点の手動調整）。"""
        existing = self._overrides.get((layer, param), {})
        self._overrides[(layer, param)] = {
            "center": center,
            "width":  width if width is not None else existing.get("width", STATE_ZONES[self._state][layer][param]["width"]),
        }

    def clear_zone_override(self, layer: str, param: str) -> None:
        self._overrides.pop((layer, param), None)

    def set_speed_override(self, speed: float | None) -> None:
        self._speed_override = speed

    def set_snap_override(self, prob: float | None) -> None:
        self._snap_override = prob

    def force_state(self, state: str) -> None:
        """Markov状態を強制設定する（シーン切り替え時に使用）。"""
        if state not in STATES:
            logger.warning("[Upper] force_state: unknown state=%s", state)
            return
        logger.info("[Upper] force_state: %s → %s", self._state, state)
        self._state = state
        self._state_start = time.time()
        self._overrides.clear()

    def set_interval(self, seconds: float) -> None:
        self._interval = max(5.0, float(seconds))

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._state_start = time.time()
        self._task = asyncio.create_task(self._loop())
        logger.info("[Upper] started  state=%s  interval=%.1fs", self._state, self._interval)

    def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None
        logger.info("[Upper] stopped")

    async def _loop(self) -> None:
        try:
            await self._broadcast({"type": "markov_state", "state": self.get_state_info()})
            while self._running:
                elapsed = 0.0
                while self._running and elapsed < self._interval:
                    await asyncio.sleep(1.0)
                    elapsed += 1.0
                    await self._broadcast({"type": "markov_state", "state": self.get_state_info()})
                if not self._running:
                    break
                next_state = self._next_state()
                logger.info("[Upper] %s → %s", self._state, next_state)
                self._state = next_state
                self._state_start = time.time()
                self._overrides.clear()  # 新状態では手動オーバーライドをリセット
                await self._broadcast({"type": "markov_state", "state": self.get_state_info()})
        except asyncio.CancelledError:
            pass

    def _next_state(self) -> str:
        markov_probs = list(BASE_MATRIX[self._state])
        feedback_probs = list(markov_probs)

        energy = self._energy_fn() if self._energy_fn else 0.5
        if energy > _ENERGY_HIGH:
            for i in [0, 1]:
                feedback_probs[i] *= 1.30
        elif energy < _ENERGY_LOW:
            for i in [3, 4]:
                feedback_probs[i] *= 1.30

        total_m = sum(markov_probs) or 1.0
        total_f = sum(feedback_probs) or 1.0
        blended = [
            _MARKOV_WEIGHT * (markov_probs[i] / total_m)
            + _FEEDBACK_WEIGHT * (feedback_probs[i] / total_f)
            for i in range(len(STATES))
        ]

        r = random.random()
        cumulative = 0.0
        total_b = sum(blended)
        current_idx = STATES.index(self._state)
        for i, w in enumerate(blended):
            cumulative += w / total_b
            if r <= cumulative:
                return STATES[i]
        return STATES[current_idx]

# ── ThreeLayerController ──────────────────────────────────────────────────

class ThreeLayerController:
    """3層制御システムのメインクラス。

    0.1秒ごとに全パラメーターを更新し、OSC で SuperCollider へ送信する。
    bridge.py から ChaosEngine + MarkovTimescale の代替として使用する。

    公開API（bridge.py との互換性）:
      start / stop
      start_markov / stop_markov / set_markov_interval / get_markov_state
      set_attractor(layer, param, value, range_val)
      set_speed(speed) / set_dejavu_prob(prob)
      set_middle_model / set_lower_model / set_middle_chaos / set_lower_chaos
      set_scene(scene_dict)
      get_state() → {layer: {param: {value, attractor, range}}}
    """

    def __init__(
        self,
        send_osc: Callable[[str, list], None],
        broadcast: Callable[[dict], Awaitable[None]],
        tidal_controller=None,
        interval: float = 60.0,
        send_tidal_ctrl: Callable[[str, float], None] | None = None,
    ) -> None:
        self._send_osc = send_osc
        self._send_tidal_ctrl = send_tidal_ctrl
        self._broadcast = broadcast
        self._running = False
        self._task: asyncio.Task | None = None

        self._upper = UpperLayer(
            broadcast=broadcast,
            interval=interval,
            tidal_controller=tidal_controller,
            energy_fn=self._compute_energy,
        )

        # パラメーター状態: {layer: {param: _ParamState}}
        self._params: dict[str, dict[str, _ParamState]] = {
            layer: {
                param: _ParamState(
                    current=specs[2],
                    middle=specs[2],
                    osc_address=specs[3],
                )
                for param, specs in layer_specs.items()
            }
            for layer, layer_specs in PARAM_SPECS.items()
        }

        # 履歴: {layer/param: deque(maxlen=HISTORY_LEN)}
        self._history: dict[str, deque[float]] = {
            f"{layer}/{param}": deque(maxlen=HISTORY_LEN)
            for layer, specs in PARAM_SPECS.items()
            for param in specs
        }

    # ── ライフサイクル ────────────────────────────────────────────────────

    def start(self) -> None:
        """更新ループと Markov ループを開始する。"""
        if not self._running:
            self._running = True
            loop = asyncio.get_running_loop()
            self._task = loop.create_task(self._loop())
        self._upper.start()

    def stop(self) -> None:
        """更新ループと Markov ループを停止する。"""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        self._upper.stop()

    @property
    def is_running(self) -> bool:
        return self._running

    # ── Markov 操作 ───────────────────────────────────────────────────────

    def start_markov(self) -> None:
        self._upper.start()

    def stop_markov(self) -> None:
        self._upper.stop()

    def set_markov_interval(self, seconds: float) -> None:
        self._upper.set_interval(seconds)

    def get_markov_state(self) -> dict:
        return self._upper.get_state_info()

    # ── パラメーター手動操作（bridge.py 互換） ────────────────────────────

    def set_attractor(
        self,
        layer: str,
        param: str,
        value: float,
        range_val: float | None = None,
    ) -> None:
        """特定パラメーターのゾーン中心を手動上書きする。"""
        if layer in PARAM_SPECS and param in PARAM_SPECS[layer]:
            self._upper.set_zone_override(layer, param, float(value), range_val)

    def set_speed(self, speed: float) -> None:
        """全パラメーターのドリフト速度を上書きする（0.0〜2.0 推奨）。"""
        self._upper.set_speed_override(max(0.0, float(speed)))
        logger.info("[Controller] speed → %.2f", speed)

    def set_dejavu_prob(self, prob: float) -> None:
        """全パラメーターの Dejavu snap_prob を上書きする（0.0〜1.0）。"""
        self._upper.set_snap_override(max(0.0, min(1.0, float(prob))))
        logger.info("[Controller] dejavu_prob → %.2f", prob)

    def set_middle_model(self, name: str) -> None:
        """中位モデルの切り替え（現バージョンは BoundedWalk 固定）。"""
        logger.info("[Controller] set_middle_model(%s) — fixed to BoundedWalk", name)

    def set_lower_model(self, name: str) -> None:
        """下位モデルの切り替え（現バージョンは Dejavu 固定）。"""
        logger.info("[Controller] set_lower_model(%s) — fixed to Dejavu", name)

    def set_middle_chaos(self, ratio: float) -> None:
        """中位カオス比率（現バージョンでは speed として解釈）。"""
        self.set_speed(ratio * 2.0)

    def set_lower_chaos(self, ratio: float) -> None:
        """下位カオス比率（現バージョンでは snap_prob の反転として解釈）。"""
        self.set_dejavu_prob(1.0 - ratio)

    # シーン名（MusicGenerator/SCENE_DNA）→ Markov状態（ThreeLayerController）のマッピング
    # onset_density_target の大小に基づき対応付ける:
    #   void(0.2)=void, vast(0.3)=sparse, warm(0.4)=medium, lost(0.6)=dense, peak(0.9)=intense
    _SCENE_TO_MARKOV: dict[str, str] = {
        "void":  "void",
        "vast":  "sparse",
        "warm":  "medium",
        "lost":  "dense",
        "peak":  "intense",
    }

    def set_scene(self, scene: dict) -> None:
        """シーン定義に従ってゾーン中心を更新する（現在値は急変しない）。"""
        drone   = scene.get("drone", {})
        granular = scene.get("granular", {})
        _overrides = [
            ("drone",    "feedback_amt", drone.get("feedback_attractor")),
            ("drone",    "shimmer",      drone.get("shimmer_attractor")),
            ("drone",    "room",         drone.get("room_attractor")),
            ("granular", "density",      granular.get("density_attractor"),
                                         granular.get("density_range")),
            ("granular", "spray",        granular.get("spray_attractor")),
            ("granular", "room",         granular.get("room_attractor")),
        ]
        for entry in _overrides:
            layer, param, center = entry[0], entry[1], entry[2]
            width = entry[3] if len(entry) > 3 else None
            if center is not None:
                self._upper.set_zone_override(layer, param, float(center), width)

    def set_markov_state_from_scene(self, scene_name: str) -> None:
        """シーン名をMarkov状態に変換してUpperLayerに強制適用する。

        Middle値も新しい状態のcenterへ即スナップして変化を即座に聴覚化する。
        """
        markov_state = self._SCENE_TO_MARKOV.get(scene_name)
        if markov_state is None:
            logger.warning("[Controller] set_markov_state_from_scene: unknown scene=%s", scene_name)
            return
        self._upper.force_state(markov_state)
        # Middle値を新状態のcenterへ即スナップ（BoundedWalkのじわじわ収束を回避）
        self._snap_middle_to_state(markov_state)

    def _snap_middle_to_state(self, state: str) -> None:
        """指定状態のSTATE_ZONESのcenter値へMiddleを即座にリセットする。"""
        zones = STATE_ZONES.get(state, {})
        new_params: dict[str, dict[str, _ParamState]] = {}
        for layer, params in self._params.items():
            new_layer: dict[str, _ParamState] = {}
            for param, ps in params.items():
                center = zones.get(layer, {}).get(param, {}).get("center")
                if center is not None:
                    new_layer[param] = ps.with_values(center, center)
                else:
                    new_layer[param] = ps
            new_params[layer] = new_layer
        self._params = new_params
        logger.info("[Controller] snapped Middle to state=%s", state)

    def get_state(self) -> dict:
        """全パラメーターの現在状態を返す（UI表示用・ChaosEngine 互換形式）。

        {layer: {param: {value, attractor, range}}}
        """
        return {
            layer: {
                param: {
                    "value":     round(state.current, 4),
                    "attractor": round(
                        self._upper.get_control(layer, param).center, 4
                    ),
                    "range":     round(
                        self._upper.get_control(layer, param).width, 4
                    ),
                }
                for param, state in params.items()
            }
            for layer, params in self._params.items()
        }

    # ── 内部実装 ──────────────────────────────────────────────────────────

    def _compute_energy(self) -> float:
        """現在のパラメーター値からエネルギーを 0〜1 で推定する。"""
        try:
            def _v(layer: str, param: str, default: float) -> float:
                return self._params.get(layer, {}).get(param, _ParamState(default, default, "")).current

            gran_density = min(1.0, _v("granular",    "density", 15.0) / 40.0)
            synth_density = min(1.0, _v("gran_synth",  "density", 30.0) / 60.0)
            samp_density  = min(1.0, _v("gran_sampler","density", 20.0) / 55.0)
            drone_amp     = _v("drone", "amp", 0.35)
            energy = (
                0.30 * gran_density
                + 0.25 * synth_density
                + 0.25 * samp_density
                + 0.20 * drone_amp
            )
            return min(1.0, max(0.0, energy))
        except Exception:
            return 0.5

    async def _loop(self) -> None:
        while self._running:
            await asyncio.sleep(UPDATE_INTERVAL)
            if not self._running:
                break
            await self._tick()

    async def _tick(self) -> None:
        """1回の更新: 全パラメーターを Middle → Lower の順に計算し送信する。"""
        new_params: dict[str, dict[str, _ParamState]] = {}

        for layer, params in self._params.items():
            new_layer: dict[str, _ParamState] = {}
            for param, state in params.items():
                path = f"{layer}/{param}"
                ctrl = self._upper.get_control(layer, param)

                new_middle = _middle_next(state.middle, ctrl)
                history = self._history[path]
                new_current = _lower_next(new_middle, ctrl, history)

                history.append(new_current)
                if state.osc_address == "_tidal_ctrl":
                    # melody レイヤー → Tidal Control Channel (port 6010) へ
                    # キー名は "layer_param" 形式（例: "melody_note"）
                    # Tidal 側では cI 0 "melody_note" で参照する
                    if self._send_tidal_ctrl is not None:
                        ctrl_key = f"{layer}_{param}"
                        self._send_tidal_ctrl(ctrl_key, new_current)
                else:
                    self._send_osc(state.osc_address, [param, new_current])

                new_layer[param] = state.with_values(new_current, new_middle)
            new_params[layer] = new_layer

        self._params = new_params

        await self._broadcast({
            "type":  "chaos_state",
            "state": self.get_state(),
        })
