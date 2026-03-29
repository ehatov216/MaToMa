"""
MaToMa Turing Machine ステップシーケンサー
==========================================
2020 Beat-Machine / Fors Opal / Sugar Bytes Nest の設計思想を参考に実装。

設計:
  - 16ステップの循環バッファ（拡張可能）
  - 各ステップが複数パラメーターの値を持つ（Opal のパラメーター・ロック）
  - mutation_prob: ステップを通過するたびに値が少しずつ変異（Turing Machine）
  - trig_prob: 各ステップが発火する確率（2020 TRIG）
  - BPM + step_div で時間解像度を制御（1/4, 1/8, 1/16, 1/32）

シーケンスされるパラメーター:
  drone_cutoff  → /matoma/drone/param cutoff  (フィルター開閉リズム)
  drone_drift   → /matoma/drone/param drift   (カオス度のリズム)
  spectral_smear → /matoma/spectral/param smear (スペクトルぼかしリズム)
  spectral_chaos → /matoma/spectral/param chaos (グリッチ強度リズム)
"""

import asyncio
import random
from dataclasses import dataclass, field
from typing import Awaitable, Callable

# ── シーケンス対象パラメーター ────────────────────────────────────────
# key → (OSCアドレス, OSC引数名, 最小値, 最大値)
SEQ_PARAMS: dict[str, tuple[str, str, float, float]] = {
    "drone_cutoff":   ("/matoma/drone/param",   "cutoff", 400.0, 2800.0),  # 120Hzは無音に近いため400以上
    "drone_drift":    ("/matoma/drone/param",   "drift",  0.0,   0.6),
    "spectral_smear": ("/matoma/spectral/param","smear",  0.1,   0.9),
    "spectral_chaos": ("/matoma/spectral/param","chaos",  0.1,   0.8),
}

# デフォルトの初期値（ステップ生成時に使う中心値）
_CENTERS: dict[str, float] = {
    "drone_cutoff":   1200.0,   # 中心を明るめに（暗い方向へも変異するが無音にはならない）
    "drone_drift":    0.2,
    "spectral_smear": 0.45,
    "spectral_chaos": 0.35,
}

# ステップ解像度 (step_div) のプリセット
STEP_DIVS = {
    "1/4":  1.0,
    "1/8":  0.5,
    "1/16": 0.25,
    "1/32": 0.125,
}


@dataclass
class Step:
    """シーケンサーの1ステップ。"""
    values: dict[str, float] = field(default_factory=dict)
    enabled: bool = True


def _init_step() -> Step:
    """ランダムな初期値を持つステップを生成する。"""
    values: dict[str, float] = {}
    for key, (_, _, mn, mx) in SEQ_PARAMS.items():
        center = _CENTERS.get(key, (mn + mx) / 2)
        # 中心値から ±25% のランダム初期値
        span = (mx - mn) * 0.25
        values[key] = max(mn, min(mx, center + random.uniform(-span, span)))  # noqa: S311
    return Step(values=values)


class TuringSequencer:
    """Turing Machine スタイルのステップシーケンサー。

    使い方:
        seq = TuringSequencer(sc_client.send_message, broadcast)
        seq.set_bpm(120.0)
        seq.start()
        seq.stop()
    """

    def __init__(
        self,
        send_osc: Callable[[str, list], None],
        broadcast: Callable[[dict], Awaitable[None]],
    ) -> None:
        self._send_osc = send_osc
        self._broadcast = broadcast
        self._running = False
        self._task: asyncio.Task | None = None

        self.n_steps: int = 16
        self.current_step: int = 0

        # テンポ制御
        self.bpm: float = 120.0
        self.step_div: float = 0.5   # 1/8 音符がデフォルト

        # 確率制御（2020 TRIG / Turing Machine mutation）
        self.trig_prob: float = 0.8
        self.mutation_prob: float = 0.05

        # ステップデータ
        self._steps: list[Step] = [_init_step() for _ in range(self.n_steps)]

        # アクティブなパラメーター（UIから選択）
        self._active_params: set[str] = {"drone_cutoff"}

    # ── 外部API ──────────────────────────────────────────────────────

    def start(self) -> None:
        if not self._running:
            self._running = True
            self._task = asyncio.get_running_loop().create_task(self._loop())

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        self.current_step = 0

    def set_bpm(self, bpm: float) -> None:
        self.bpm = max(20.0, min(300.0, float(bpm)))

    def set_step_div(self, div_name: str) -> None:
        self.step_div = STEP_DIVS.get(div_name, 0.5)

    def set_trig_prob(self, prob: float) -> None:
        self.trig_prob = max(0.0, min(1.0, float(prob)))

    def set_mutation_prob(self, prob: float) -> None:
        self.mutation_prob = max(0.0, min(1.0, float(prob)))

    def set_step_enabled(self, step_idx: int, enabled: bool) -> None:
        if 0 <= step_idx < self.n_steps:
            self._steps[step_idx].enabled = enabled

    def set_active_params(self, params: list[str]) -> None:
        self._active_params = set(params) & set(SEQ_PARAMS.keys())

    def get_state(self) -> dict:
        return {
            "running": self._running,
            "current_step": self.current_step,
            "bpm": self.bpm,
            "step_div": self.step_div,
            "trig_prob": self.trig_prob,
            "mutation_prob": self.mutation_prob,
            "active_params": sorted(self._active_params),
            "steps_enabled": [s.enabled for s in self._steps],
            "step_values": [
                {k: round(v, 3) for k, v in s.values.items() if k in self._active_params}
                for s in self._steps
            ],
        }

    # ── 内部ループ ────────────────────────────────────────────────────

    async def _loop(self) -> None:
        while self._running:
            # 60/BPM = 1拍の秒数, × step_div = ステップ間隔
            interval = (60.0 / self.bpm) * self.step_div
            await asyncio.sleep(interval)
            if not self._running:
                break
            await self._tick()

    async def _tick(self) -> None:
        step = self._steps[self.current_step]
        fired: dict[str, float] = {}

        # TRIG: 確率でステップを発火
        if step.enabled and random.random() < self.trig_prob:  # noqa: S311
            for key in self._active_params:
                if key not in step.values:
                    continue
                addr, param, _, _ = SEQ_PARAMS[key]
                val = step.values[key]
                self._send_osc(addr, [param, val])
                fired[key] = val

        # Turing Machine: mutation_prob でステップの値を少しずつ変異
        if random.random() < self.mutation_prob:  # noqa: S311
            for key in self._active_params:
                if key not in step.values:
                    continue
                _, _, mn, mx = SEQ_PARAMS[key]
                span = mx - mn
                if random.random() < 0.15:  # noqa: S311
                    # 15%の確率でランダムにリセット（大きな変化）
                    step.values[key] = random.uniform(mn, mx)  # noqa: S311
                else:
                    # 小さなランダムウォーク
                    delta = span * random.uniform(-0.12, 0.12)  # noqa: S311
                    step.values[key] = max(mn, min(mx, step.values[key] + delta))

        # ブラウザへステップ位置・発火情報を通知
        await self._broadcast({
            "type": "seq_tick",
            "step": self.current_step,
            "fired": fired,
            "enabled": step.enabled,
            "step_values": {
                k: round(step.values.get(k, 0), 3)
                for k in self._active_params
            },
        })

        # 次のステップへ
        self.current_step = (self.current_step + 1) % self.n_steps
