"""
自律モード (Autonomous Mode)
============================
パラメーターを定期的に自動更新するモジュール。

モード:
  random   — ランダムウォーク（各ステップで小さくランダムに動く）
  directed — 設定した目標値に向かって少しずつ近づく

拡張方法:
  新しいモードを追加するには _next_value() に elif ブランチを1つ追加し、
  必要なら PARAM_SPECS にパラメーターを追加するだけでよい。
"""

import asyncio
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Awaitable, Callable

if TYPE_CHECKING:
    from tidal_controller import TidalController

from tidal_patterns import (
    ARP_RHYTHMS,
    PROGRESSIONS,
    make_chord_pattern,
    make_scale_pattern,
)

# ── パラメーター定義 ────────────────────────────────────────────────
# key        : 内部キー名（ブラウザ・bridge から参照する名前）
# value      : (OSCアドレス, OSC引数名, 最小値, 最大値, 初期値)
PARAM_SPECS: dict[str, tuple[str, str, float, float, float]] = {
    "freq":         ("/matoma/param",       "freq",   55.0,  880.0,  220.0),
    "cutoff":       ("/matoma/param",       "cutoff", 200.0, 8000.0, 1000.0),
    "drone_freq":   ("/matoma/drone/param", "freq",   40.0,  220.0,  60.0),
    "drone_detune": ("/matoma/drone/param", "detune", 0.0,   1.0,    0.3),
    "drone_cutoff": ("/matoma/drone/param", "cutoff", 80.0,  3000.0, 800.0),
    "drone_drift":  ("/matoma/drone/param", "drift",  0.0,   1.0,    0.1),
    "drone_room":   ("/matoma/drone/param", "room",   0.0,   1.0,    0.6),
}


@dataclass
class _ParamState:
    osc_address: str
    osc_arg: str
    min_val: float
    max_val: float
    value: float    # 現在値（自律ループが毎ステップ書き換える）
    target: float   # directed モード用の目標値


class AutonomousMode:
    """自律モードの管理クラス。

    使い方:
        auto = AutonomousMode(sc_client.send_message, broadcast)
        auto.set_mode("random")
        auto.set_speed(0.3)
        auto.start()   # ループ開始
        auto.stop()    # ループ停止
    """

    def __init__(
        self,
        send_osc: Callable[[str, list], None],
        broadcast: Callable[[dict], Awaitable[None]],
    ) -> None:
        self._send_osc = send_osc       # sc_client.send_message(address, args)
        self._broadcast = broadcast     # WebSocket で全ブラウザへ送る
        self._running = False
        self._mode = "random"           # "random" | "directed"（追加可能）
        self._speed = 0.3               # 0.0〜1.0
        self._task: asyncio.Task | None = None

        self._params: dict[str, _ParamState] = {
            key: _ParamState(
                osc_address=addr,
                osc_arg=arg,
                min_val=mn,
                max_val=mx,
                value=init,
                target=init,
            )
            for key, (addr, arg, mn, mx, init) in PARAM_SPECS.items()
        }

        # ── Tidal 自律制御 ──────────────────────────────────────────────
        self._tidal: TidalController | None = None
        self._tidal_auto: bool = False
        self._progression_name: str = "ambient_minor"
        self._chord_step: int = 0
        self._arp_rhythm_index: int = 0
        # シンセtickをN回消費するごとにコードを1ステップ進める
        self._tidal_counter: int = 0
        self._tidal_change_interval: int = 4

    # ── 外部から呼ぶ API ──────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def speed(self) -> float:
        return self._speed

    def set_mode(self, mode: str) -> None:
        """モードを切り替える。未知のモードは無視する。"""
        if mode in ("random", "directed"):
            self._mode = mode

    def set_speed(self, speed: float) -> None:
        """変化の速さを設定する（0.0=ゆっくり、1.0=速い）。"""
        self._speed = max(0.0, min(1.0, float(speed)))

    def set_target(self, param: str, value: float) -> None:
        """directed モード用の目標値を設定する。"""
        if param in self._params:
            p = self._params[param]
            p.target = max(p.min_val, min(p.max_val, float(value)))

    def set_tidal(self, tidal: TidalController) -> None:
        """TidalControllerへの参照を渡す（bridge.py 起動時に呼ぶ）。"""
        self._tidal = tidal

    def set_tidal_auto(self, enabled: bool) -> None:
        """Tidal自律モードのON/OFFを切り替える。"""
        self._tidal_auto = enabled

    def set_progression(self, name: str) -> None:
        """コード進行プリセットを変更する。先頭から再スタートする。"""
        if name in PROGRESSIONS:
            self._progression_name = name
            self._chord_step = 0
            self._tidal_counter = 0

    def sync_current(self, param: str, value: float) -> None:
        """スライダー操作時などに現在値を外部から同期する。
        手動操作を自律ループに反映させて、急な飛びを防ぐ。
        """
        if param in self._params:
            p = self._params[param]
            p.value = max(p.min_val, min(p.max_val, float(value)))

    def start(self) -> None:
        if not self._running:
            self._running = True
            loop = asyncio.get_event_loop()
            self._task = loop.create_task(self._loop())

    def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None

    # ── 内部ループ ────────────────────────────────────────────────────

    async def _loop(self) -> None:
        while self._running:
            # speed 0.0 → 約10秒間隔、speed 1.0 → 約0.5秒間隔
            interval = (1.0 - self._speed) * 9.5 + 0.5
            await asyncio.sleep(interval)
            if not self._running:
                break
            await self._tick()

    async def _tick(self) -> None:
        updates: dict[str, float] = {}
        for key, p in self._params.items():
            new_val = self._next_value(p)
            p.value = new_val
            updates[key] = new_val
            self._send_osc(p.osc_address, [p.osc_arg, new_val])

        # ブラウザのスライダーも更新する
        await self._broadcast({"type": "autonomous_update", "params": updates})

        # Tidal: N tick ごとにコード進行を1ステップ進める
        self._tidal_counter += 1
        if self._tidal_counter >= self._tidal_change_interval:
            self._tidal_counter = 0
            await self._tidal_tick()

    async def _tidal_tick(self) -> None:
        """コード進行を1ステップ進め、アルペジオパターンを更新する。"""
        if not self._tidal_auto or self._tidal is None:
            return
        if not self._tidal.is_running:
            return

        progression = PROGRESSIONS.get(
            self._progression_name, PROGRESSIONS["ambient_minor"]
        )
        self._chord_step = (self._chord_step + 1) % len(progression)
        root, chord = progression[self._chord_step]

        synth = self._tidal.state.get("synth", "superpiano")
        octave = int(self._tidal.state.get("octave", 4))
        amp = float(self._tidal.state.get("amp", 0.5))

        # コードを鳴らす（d1）
        chord_code = make_chord_pattern(1, synth, root, chord, octave, amp * 0.8)
        self._tidal.evaluate(chord_code)

        # アルペジオ（d2）: randomモードならリズムも変える
        if self._mode == "random":
            self._arp_rhythm_index = random.randrange(len(ARP_RHYTHMS))  # noqa: S311
        degrees = ARP_RHYTHMS[self._arp_rhythm_index]
        scale = self._tidal.state.get("scale", "minor")
        arp_code = make_scale_pattern(
            2, synth, root, scale, degrees, octave, amp * 0.5
        )
        self._tidal.evaluate(arp_code)

        # ブラウザへ現在のコードステップを通知する
        await self._broadcast({
            "type": "tidal_auto_step",
            "root": root,
            "chord": chord,
            "progression": self._progression_name,
            "step": self._chord_step,
        })

    def _next_value(self, p: _ParamState) -> float:
        """モードに応じて次の値を計算する。新モードはここに追加する。"""
        if self._mode == "random":
            return self._random_walk(p)
        elif self._mode == "directed":
            return self._directed_walk(p)
        return p.value

    def _random_walk(self, p: _ParamState) -> float:
        """現在値から小さくランダムに動く（酔っ払いの歩み）。

        speed が大きいほどステップが大きく、レンジの最大 15% まで動く。
        """
        span = p.max_val - p.min_val
        step = span * self._speed * 0.15 * (random.random() * 2.0 - 1.0)
        return max(p.min_val, min(p.max_val, p.value + step))

    def _directed_walk(self, p: _ParamState) -> float:
        """目標値に向かって少しずつ近づく。

        speed が大きいほど速く近づく（残り距離の最大 30% ずつ）。
        目標にほぼ到達したら止まる。
        """
        diff = p.target - p.value
        if abs(diff) < 0.001:
            return p.target
        step = diff * self._speed * 0.3
        return max(p.min_val, min(p.max_val, p.value + step))
