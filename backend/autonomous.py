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
import logging
import random
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Awaitable, Callable

if TYPE_CHECKING:
    from tidal_controller import TidalController

from tidal_patterns import PRESETS, get_preset

logger = logging.getLogger(__name__)

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
    "drone_chaos":  ("/matoma/drone/param", "chaos",  0.0,   1.0,    0.3),
    "drone_room":   ("/matoma/drone/param", "room",   0.0,   1.0,    0.6),
}


@dataclass
class _ParamState:
    osc_address: str
    osc_arg: str
    min_val: float
    max_val: float
    value: float    # 現在値
    target: float   # directed モード用の目標値

    def with_value(self, new_value: float) -> "_ParamState":
        """valueだけ変えた新インスタンスを返す（イミュータブル更新）。"""
        return _ParamState(
            osc_address=self.osc_address,
            osc_arg=self.osc_arg,
            min_val=self.min_val,
            max_val=self.max_val,
            value=new_value,
            target=self.target,
        )

    def with_target(self, new_target: float) -> "_ParamState":
        """targetだけ変えた新インスタンスを返す（イミュータブル更新）。"""
        return _ParamState(
            osc_address=self.osc_address,
            osc_arg=self.osc_arg,
            min_val=self.min_val,
            max_val=self.max_val,
            value=self.value,
            target=new_target,
        )


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

        # ── 2020 Beat-Machine: TRIG（確率トリガー）─────────────────────
        # 各ステップで各パラメーターが実際に変化する確率。
        # 1.0 = 毎回変化（従来の挙動）、0.5 = 半分の確率で変化
        # 低い値にすると「鳴ったり鳴らなかったり」する予測不能なパターンに
        self._trig_prob: float = 0.7

        # ── 2020 Beat-Machine: Dejavu（履歴再生）────────────────────────
        # 最大32世代の履歴を保持し、過去の状態を確率で再現する。
        # dejavu_prob = 0.0 → 常に新しい値を生成
        # dejavu_prob = 1.0 → 常に履歴から再生（固定シーケンサーになる）
        self._history: deque[dict[str, float]] = deque(maxlen=32)
        self._dejavu_prob: float = 0.0
        self._dejavu_len: int = 8   # 何ステップ前まで参照するか（1-32）

        # ── Tidal 自律制御 ──────────────────────────────────────────────
        self._tidal: TidalController | None = None
        self._tidal_auto: bool = False
        # プリセットをN tick ごとに1ステップ自動送信するサイクル
        self._preset_cycle: list[str] = list(PRESETS.keys())
        self._preset_index: int = 0
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
            clamped = max(p.min_val, min(p.max_val, float(value)))
            self._params[param] = p.with_target(clamped)

    def set_tidal(self, tidal: "TidalController") -> None:
        """TidalControllerへの参照を渡す（bridge.py 起動時に呼ぶ）。"""
        self._tidal = tidal

    def set_tidal_auto(self, enabled: bool) -> None:
        """Tidal自律モードのON/OFFを切り替える。"""
        self._tidal_auto = enabled

    def set_trig_prob(self, prob: float) -> None:
        """各パラメーターが変化する確率を設定する（2020 TRIG に相当）。"""
        self._trig_prob = max(0.0, min(1.0, float(prob)))

    def set_dejavu_prob(self, prob: float) -> None:
        """履歴から再生する確率を設定する（2020 DJV に相当）。"""
        self._dejavu_prob = max(0.0, min(1.0, float(prob)))

    def set_dejavu_len(self, length: int) -> None:
        """参照する履歴の深さを設定する（2020 LEN に相当、1-32）。"""
        self._dejavu_len = max(1, min(32, int(length)))

    def set_progression(self, name: str) -> None:
        """自律プリセットを固定する（旧コード進行変更と同じWSアドレスを流用）。"""
        if name in PRESETS:
            self._preset_cycle = [name]
            self._preset_index = 0
            self._tidal_counter = 0

    def sync_current(self, param: str, value: float) -> None:
        """スライダー操作時などに現在値を外部から同期する。
        手動操作を自律ループに反映させて、急な飛びを防ぐ。
        """
        if param in self._params:
            p = self._params[param]
            clamped = max(p.min_val, min(p.max_val, float(value)))
            self._params[param] = p.with_value(clamped)

    def start(self) -> None:
        if not self._running:
            self._running = True
            self._task = asyncio.get_running_loop().create_task(self._loop())

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
            # 2020 TRIG: trig_prob の確率でスキップ（パラメーターが変化しない）
            if random.random() > self._trig_prob:  # noqa: S311
                updates[key] = p.value
                continue

            new_val = self._next_value(p, key)
            self._params[key] = p.with_value(new_val)
            updates[key] = new_val
            self._send_osc(p.osc_address, [p.osc_arg, new_val])

        # 現在の全パラメーター状態を Dejavu 履歴に保存
        self._history.append({k: p.value for k, p in self._params.items()})

        # ブラウザのスライダーも更新する
        await self._broadcast({"type": "autonomous_update", "params": updates})

        # Tidal: N tick ごとにコード進行を1ステップ進める
        self._tidal_counter += 1
        if self._tidal_counter >= self._tidal_change_interval:
            self._tidal_counter = 0
            await self._tidal_tick()

    async def _tidal_tick(self) -> None:
        """プリセットを1ステップ進め、TidalCycles へ送る。"""
        if not self._tidal_auto or self._tidal is None:
            return
        if not self._tidal.is_running:
            return

        if self._mode == "random":
            self._preset_index = random.randrange(len(self._preset_cycle))  # noqa: S311
        else:
            self._preset_index = (self._preset_index + 1) % len(self._preset_cycle)

        name = self._preset_cycle[self._preset_index]
        codes = get_preset(name)
        for code in codes:
            self._tidal.evaluate(code)

        await self._broadcast({
            "type": "tidal_auto_step",
            "preset": name,
            "step": self._preset_index,
        })

    def _next_value(self, p: _ParamState, key: str) -> float:
        """モードに応じて次の値を計算する。新モードはここに追加する。

        2020 Dejavu: dejavu_prob の確率で履歴から値を取り出す。
        履歴がない場合や確率に外れた場合は通常のランダムウォーク。
        """
        # Dejavu: 確率で過去の状態を再現（2020 DJV / LEN）
        if (
            self._dejavu_prob > 0
            and len(self._history) > 0
            and random.random() < self._dejavu_prob  # noqa: S311
        ):
            available = list(self._history)[-self._dejavu_len:]
            return random.choice(available)[key]  # noqa: S311

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

