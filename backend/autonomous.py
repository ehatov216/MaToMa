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

ChaosEngine:
  Dejavuパターン（Tom Whitwell考案）による記憶付きカオスドリフト。
  各パラメーターの過去8世代を記憶し、確率30%で過去に戻る。
  シーンの「引力点」と「揺れ幅」に基づいてBounded Random Walkを行う。
"""

import asyncio
import random
from collections import deque
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
        chord_code = make_chord_pattern(
            1, synth, root, chord, octave, amp * 0.8
        )
        self._tidal.evaluate(chord_code)

        # アルペジオ（d2）: randomモードならリズムも変える
        if self._mode == "random":
            self._arp_rhythm_index = random.randrange(  # noqa: S311
                len(ARP_RHYTHMS)
            )
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


# ── ChaosEngine ────────────────────────────────────────────────────────────
# Dejavuパターン（Tom Whitwell考案）による記憶付きカオスドリフト。
# 「引力点」に引き寄せられながら、確率的に過去の状態にも引き戻される。


@dataclass
class _ChaosParam:
    """ChaosEngine が管理するひとつのパラメーター状態（イミュータブル設計）。

    直接フィールドを書き換えず、with_value() / with_attractor() で
    新しいインスタンスを返す方針をとる。
    """

    value: float       # 現在値
    attractor: float   # 引力点（シーン切り替えで更新される）
    range: float       # 引力点からの最大揺れ幅
    speed: float       # 1ステップあたりの最大変化率（range に対する割合）

    def with_value(self, new_value: float) -> "_ChaosParam":
        """valueだけ変えた新インスタンスを返す。"""
        return _ChaosParam(
            value=new_value,
            attractor=self.attractor,
            range=self.range,
            speed=self.speed,
        )

    def with_attractor(
        self,
        new_attractor: float,
        new_range: float | None = None,
    ) -> "_ChaosParam":
        """attractorとrangeを変えた新インスタンスを返す。"""
        return _ChaosParam(
            value=self.value,
            attractor=new_attractor,
            range=new_range if new_range is not None else self.range,
            speed=self.speed,
        )

    @property
    def floor(self) -> float:
        """許容最小値（引力点 - 揺れ幅）。"""
        return self.attractor - self.range

    @property
    def ceiling(self) -> float:
        """許容最大値（引力点 + 揺れ幅）。"""
        return self.attractor + self.range

    def clamped(self) -> "_ChaosParam":
        """現在値を [floor, ceiling] に収めた新インスタンスを返す。"""
        clamped_val = max(self.floor, min(self.ceiling, self.value))
        if clamped_val == self.value:
            return self
        return self.with_value(clamped_val)


# パラメーターのデフォルト定義
# 構造: {layer: {param: (init_value, attractor, range, speed)}}
_LayerParams = dict[str, tuple[float, float, float, float]]
_DEFAULT_CHAOS_PARAMS: dict[str, _LayerParams] = {
    "drone": {
        # (init, attractor, range, speed)
        # freq はシーン切り替えと TURING が担当 → ChaosEngine から除外
        # feedback: 速度0.12 → 約1秒で全rangeを横断できる
        "feedback_amt": (0.25,  0.25,  0.15,  0.12),
        # shimmer: 浮遊感が数秒単位でゆっくり変化する
        "shimmer":      (0.4,   0.4,   0.3,   0.10),
        "room":         (0.7,   0.7,   0.25,  0.05),
        "amp":          (0.35,  0.35,  0.08,  0.02),
    },
    "granular": {
        # density: attractor=15, range=10 → 常に5以上を保証（負の値を防ぐ）
        "density": (15.0,  15.0,  10.0,  0.25),
        # spray: 規則↔ランダムが数秒でスイング
        "spray":   (0.5,   0.5,   0.4,   0.12),
        "pos":     (0.5,   0.5,   0.4,   0.10),
        "room":    (0.5,   0.5,   0.25,  0.05),
    },
    "rhythmic": {
        # prob: Turing Machine の変異量が1〜2分かけて緩やかに変化
        "prob": (0.3,  0.3,  0.3,  0.06),
    },
    # gran_synth は FLUTE スライダーで手動制御するため ChaosEngine から除外
    # （自動変調が 10回/秒で手動操作を上書きするため操作性が損なわれる）
}


class ChaosEngine:
    """Dejavu パターンによる記憶付きカオスドリフトエンジン。

    設計方針:
      - パラメーターは Bounded Random Walk で引力点の周りをドリフトする
      - 各パラメーターの過去8世代を記憶し、確率30%で過去の値に戻る
      - シーンの引力点が変わっても、現在値は急変せずじわじわ引き寄せられる
      - 値を直接mutateせず、新インスタンスで更新するイミュータブル設計

    使い方:
        engine = ChaosEngine(sc_client.send_message, broadcast)
        engine.start()   # 更新ループ開始（0.1秒ごと）
        engine.stop()    # 停止
        engine.set_scene("浮遊")  # シーン変更
    """

    HISTORY_LEN = 8        # 各パラメーターが記憶する世代数
    DEJAVU_PROB = 0.3      # 過去に戻る確率
    UPDATE_INTERVAL = 0.1  # 更新間隔（秒）

    def __init__(
        self,
        send_osc: Callable[[str, list], None],
        broadcast: Callable[[dict], Awaitable[None]],
    ) -> None:
        self._send_osc = send_osc
        self._broadcast = broadcast
        self._running = False
        self._task: asyncio.Task | None = None

        # パラメーター状態: {layer: {param: _ChaosParam}}
        self._params: dict[str, dict[str, _ChaosParam]] = {
            layer: {
                param: _ChaosParam(
                    value=init, attractor=att, range=rng, speed=spd
                )
                for param, (init, att, rng, spd) in params.items()
            }
            for layer, params in _DEFAULT_CHAOS_PARAMS.items()
        }

        # Dejavu 履歴: {param_path: deque(maxlen=HISTORY_LEN)}
        # param_path は "drone/freq" のような形式
        self._history: dict[str, deque[float]] = {
            f"{layer}/{param}": deque(maxlen=self.HISTORY_LEN)
            for layer, params in _DEFAULT_CHAOS_PARAMS.items()
            for param in params
        }

    # ── 外部API ──────────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        """更新ループを開始する。"""
        if not self._running:
            self._running = True
            self._task = asyncio.get_running_loop().create_task(self._loop())

    def stop(self) -> None:
        """更新ループを停止する。"""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None

    def set_attractor(
        self,
        layer: str,
        param: str,
        attractor: float,
        range_val: float | None = None,
    ) -> None:
        """特定パラメーターの引力点を手動で設定する。

        シーン切り替え以外でも人間が引力点を動かせるようにする。
        現在値は急変しない — 次の更新ループで引き寄せられていく。
        """
        if layer in self._params and param in self._params[layer]:
            p = self._params[layer][param]
            self._params[layer][param] = p.with_attractor(attractor, range_val)

    def set_scene(self, scene: dict) -> None:
        """シーン定義（引力点と揺れ幅）に合わせてパラメーターを更新する。

        現在値は急変しない。引力点と範囲だけを更新し、
        次の更新ループで自然に引き寄せられていく。
        """
        drone = scene.get("drone", {})
        granular = scene.get("granular", {})
        rhythmic = scene.get("rhythmic", {})

        # Drone パラメーター
        self._params["drone"] = self._apply_scene_layer(
            self._params["drone"],
            {
                "freq": (
                    drone.get("freq_attractor"),
                    drone.get("freq_range"),
                ),
                "feedback_amt": (drone.get("feedback_attractor"), None),
                "shimmer": (drone.get("shimmer_attractor"), None),
                "room": (drone.get("room_attractor"), None),
            },
        )

        # Granular パラメーター
        self._params["granular"] = self._apply_scene_layer(
            self._params["granular"],
            {
                "density": (
                    granular.get("density_attractor"),
                    granular.get("density_range"),
                ),
                "spray": (granular.get("spray_attractor"), None),
                "room": (granular.get("room_attractor"), None),
            },
        )

        # Rhythmic パラメーター
        self._params["rhythmic"] = self._apply_scene_layer(
            self._params["rhythmic"],
            {
                "prob": (
                    rhythmic.get("prob_attractor"),
                    rhythmic.get("prob_range"),
                ),
            },
        )

    def get_state(self) -> dict:
        """現在の全パラメーター状態を辞書で返す（UI表示用）。

        {layer: {param: {value, attractor, range}}} の形式。
        """
        return {
            layer: {
                param: {
                    "value": round(p.value, 4),
                    "attractor": round(p.attractor, 4),
                    "range": round(p.range, 4),
                }
                for param, p in params.items()
            }
            for layer, params in self._params.items()
        }

    # ── 内部実装 ────────────────────────────────────────────────────────

    @staticmethod
    def _apply_scene_layer(
        current: dict[str, _ChaosParam],
        updates: dict[str, tuple],
    ) -> dict[str, _ChaosParam]:
        """シーン定義を適用した新しいパラメーター辞書を返す（イミュータブル）。

        updates: {param: (new_attractor_or_None, new_range_or_None)}
        Noneの場合は既存の値を維持する。
        """
        result = dict(current)
        for param, (new_att, new_range) in updates.items():
            if param in result and new_att is not None:
                result[param] = result[param].with_attractor(
                    float(new_att),
                    float(new_range) if new_range is not None else None,
                )
        return result

    def _next_value(self, path: str, p: _ChaosParam) -> float:
        """Dejavu + Bounded Random Walk で次の値を計算する（イミュータブル）。

        - 確率 DEJAVU_PROB: 過去のある世代の値に戻る
        - それ以外: 引力点に引き寄せられながら小さくランダムに動く
        """
        history = self._history[path]

        # Dejavu: 履歴があれば確率的に過去の値を使う
        if history and random.random() < self.DEJAVU_PROB:  # noqa: S311
            return random.choice(list(history))  # noqa: S311

        # Bounded Random Walk: 引力点方向への引力 + ランダム摂動
        # 引力: 現在値が引力点から離れるほど引き寄せる力が強くなる
        # 0.1 に引き上げることで確率的ランダムウォークから真の引力中心への収束へ
        attraction = (p.attractor - p.value) * 0.1
        perturbation = (  # noqa: S311
            p.range * p.speed * (random.random() * 2.0 - 1.0)
        )
        new_val = p.value + attraction + perturbation

        # 境界でクランプ（引力点 ± range）
        return max(p.floor, min(p.ceiling, new_val))

    async def _loop(self) -> None:
        """UPDATE_INTERVAL ごとに全パラメーターを更新し続けるループ。"""
        while self._running:
            await asyncio.sleep(self.UPDATE_INTERVAL)
            if not self._running:
                break
            await self._tick()

    async def _tick(self) -> None:
        """1回の更新処理: 全パラメーターを計算し、OSCとWebSocketへ送る。

        各パラメーターの新値を計算してから一括で更新するため、
        計算中に self._params が変化しない（イミュータブル更新）。
        """
        new_params: dict[str, dict[str, _ChaosParam]] = {}

        for layer, params in self._params.items():
            new_layer: dict[str, _ChaosParam] = {}
            for param, p in params.items():
                path = f"{layer}/{param}"
                new_val = self._next_value(path, p)
                new_layer[param] = p.with_value(new_val)
                # 履歴を記録
                self._history[path].append(new_val)
                # OSCへ送信
                osc_address = f"/matoma/{layer}/param"
                self._send_osc(osc_address, [param, new_val])
            new_params[layer] = new_layer

        # イミュータブル更新: 全レイヤー計算後に一括で差し替え
        self._params = new_params

        # ブラウザへ状態を送信（value・attractor・range を含む）
        flat_state = {
            layer: {
                param: {
                    "value":     round(p.value, 4),
                    "attractor": round(p.attractor, 4),
                    "range":     round(p.range, 4),
                }
                for param, p in params.items()
            }
            for layer, params in self._params.items()
        }
        await self._broadcast({
            "type": "chaos_state",
            "state": flat_state,
        })
