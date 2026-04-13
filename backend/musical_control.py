"""
MusicalControl — キー・スケール・コード進行の制御
===================================================
固定モードと自律モードを独立して選択できる。

  key_mode  = "fixed"  : ユーザー指定のキー/スケールを保持
  key_mode  = "auto"   : Upper Markovの状態に連動してキーが五度圏上をドリフト
  chord_mode = "fixed" : ユーザー指定のコードシーケンスを順に再生
  chord_mode = "auto"  : Middle BoundedWalk でコードディグリーが自律的に変化

chord_interval 秒ごとに Tidal の d8 チャンネルへコードを送る。
"""

import asyncio
import logging
import random
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Awaitable, Callable

if TYPE_CHECKING:
    from tidal_controller import TidalController

log = logging.getLogger(__name__)

# ── 音楽定数 ───────────────────────────────────────────────────────────────

KEYS = ["c", "cs", "d", "ef", "e", "f", "fs", "g", "af", "a", "bf", "b"]

SCALES = ["minor", "major", "dorian", "phrygian", "lydian", "mixolydian"]

# スケール → 半音インターバル（スケール上の各音の半音数）
SCALE_INTERVALS: dict[str, list[int]] = {
    "major":      [0, 2, 4, 5, 7, 9, 11],
    "minor":      [0, 2, 3, 5, 7, 8, 10],
    "dorian":     [0, 2, 3, 5, 7, 9, 10],
    "phrygian":   [0, 1, 3, 5, 7, 8, 10],
    "lydian":     [0, 2, 4, 6, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
}

# キー → MIDIベース音（オクターブ4）
KEY_MIDI_BASE: dict[str, int] = {
    "c": 48, "cs": 49, "d": 50, "ef": 51,
    "e": 52, "f": 53, "fs": 54, "g": 55,
    "af": 56, "a": 57, "bf": 58, "b": 59,
}

# 五度圏の隣接キー（自律モードでの自然なキー移動）
KEY_NEIGHBORS: dict[str, list[str]] = {
    "c":  ["f", "g"],
    "g":  ["c", "d"],
    "d":  ["g", "a"],
    "a":  ["d", "e"],
    "e":  ["a", "b"],
    "b":  ["e", "fs"],
    "fs": ["b", "cs"],
    "cs": ["fs", "af"],
    "af": ["cs", "ef"],
    "ef": ["af", "bf"],
    "bf": ["ef", "f"],
    "f":  ["bf", "c"],
}

# Markov状態ごとのキー変更確率（自律モード、tickごと）
STATE_KEY_CHANGE_PROB: dict[str, float] = {
    "void":    0.02,
    "sparse":  0.05,
    "medium":  0.10,
    "dense":   0.15,
    "intense": 0.25,
}

# Markov状態ごとのスケール重み（自律モード）
STATE_SCALE_WEIGHTS: dict[str, dict[str, float]] = {
    "void":    {"phrygian": 0.40, "minor": 0.40, "dorian": 0.20},
    "sparse":  {"minor": 0.40, "dorian": 0.35, "phrygian": 0.25},
    "medium":  {"dorian": 0.35, "minor": 0.30, "major": 0.25, "mixolydian": 0.10},
    "dense":   {"mixolydian": 0.35, "dorian": 0.30, "major": 0.25, "lydian": 0.10},
    "intense": {"lydian": 0.40, "major": 0.35, "mixolydian": 0.25},
}

# Markov状態ごとのコードディグリーゾーン（Middle BoundedWalk 用）
# center/width: 0.0〜7.0のディグリー空間上のゾーン
STATE_CHORD_ZONES: dict[str, dict[str, float]] = {
    "void":    {"center": 0.5, "width": 0.8,  "speed": 0.2, "snap_prob": 0.60, "micro_range": 0.15},
    "sparse":  {"center": 1.0, "width": 1.5,  "speed": 0.3, "snap_prob": 0.50, "micro_range": 0.20},
    "medium":  {"center": 3.5, "width": 2.5,  "speed": 0.5, "snap_prob": 0.30, "micro_range": 0.30},
    "dense":   {"center": 4.5, "width": 3.0,  "speed": 0.8, "snap_prob": 0.15, "micro_range": 0.40},
    "intense": {"center": 5.5, "width": 3.5,  "speed": 1.2, "snap_prob": 0.05, "micro_range": 0.50},
}

# コードディグリー → 和音構成音（スケール上の音程）
CHORD_VOICING: dict[int, list[int]] = {
    0: [0, 2, 4],      # I   (tonic triad)
    1: [1, 3, 5],      # II
    2: [2, 4, 6],      # III
    3: [3, 5, 0],      # IV
    4: [4, 6, 1],      # V
    5: [5, 0, 2],      # VI
    6: [6, 1, 3],      # VII
    7: [0, 2, 4, 6],   # I7  (seventh)
}

HISTORY_LEN = 8


# ── データクラス ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MusicalState:
    key: str
    scale: str
    chord_degree: int
    key_mode: str    # "fixed" | "auto"
    chord_mode: str  # "fixed" | "auto"


# ── MusicalControl ─────────────────────────────────────────────────────────

class MusicalControl:
    """キー・スケール・コード進行の制御クラス。

    使い方:
        musical = MusicalControl(tidal, broadcast, lambda: controller._upper._state)
        musical.set_key_mode("auto")
        musical.set_chord_mode("fixed")
        musical.set_fixed_chords([0, 3, 4, 0])
        musical.start()

    chord_interval 秒ごとに Tidal d8 チャンネルへコードを送る。
    """

    def __init__(
        self,
        tidal: "TidalController",
        broadcast: Callable[[dict], Awaitable[None]],
        get_markov_state: Callable[[], str],
        chord_interval: float = 8.0,
    ) -> None:
        self._tidal = tidal
        self._broadcast = broadcast
        self._get_markov_state = get_markov_state
        self._chord_interval = chord_interval

        # モード
        self._key_mode: str = "fixed"    # "fixed" | "auto"
        self._chord_mode: str = "fixed"  # "fixed" | "auto"

        # 固定モード設定
        self._fixed_key: str = "c"
        self._fixed_scale: str = "minor"
        self._fixed_chords: list[int] = [0, 3, 4, 0]
        self._fixed_chord_index: int = 0

        # 自律モード: 現在のキー・スケール
        self._current_key: str = "c"
        self._current_scale: str = "minor"

        # 自律モード: コードディグリーのBoundedWalk（0.0〜7.0の連続値）
        self._chord_degree_float: float = 0.0

        # 自律モード: Dejavuのための履歴
        self._chord_history: deque[float] = deque(maxlen=HISTORY_LEN)

        # ループ管理
        self._running: bool = False
        self._task: asyncio.Task | None = None

    # ── 外部API ────────────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._running

    def set_key_mode(self, mode: str) -> None:
        """キー制御モードを設定する ("fixed" | "auto")。"""
        if mode in ("fixed", "auto"):
            self._key_mode = mode
            log.info("key_mode → %s", mode)

    def set_chord_mode(self, mode: str) -> None:
        """コード制御モードを設定する ("fixed" | "auto")。"""
        if mode in ("fixed", "auto"):
            self._chord_mode = mode
            log.info("chord_mode → %s", mode)

    def set_fixed_key(self, key: str, scale: str | None = None) -> None:
        """固定キーを設定する。key は KEYS の値 (例: "c", "af")。"""
        if key in KEY_MIDI_BASE:
            self._fixed_key = key
            self._current_key = key
        if scale is not None and scale in SCALES:
            self._fixed_scale = scale
            self._current_scale = scale
        log.info("fixed_key → %s %s", self._fixed_key, self._fixed_scale)

    def set_fixed_chords(self, degrees: list[int]) -> None:
        """固定コード進行を設定する (例: [0, 3, 4, 0])。"""
        if degrees:
            self._fixed_chords = [max(0, min(7, d)) for d in degrees]
            self._fixed_chord_index = 0
            log.info("fixed_chords → %s", self._fixed_chords)

    def set_chord_interval(self, seconds: float) -> None:
        """コード変更間隔を秒数で設定する。"""
        self._chord_interval = max(1.0, float(seconds))

    def get_state(self) -> dict:
        """ブラウザ送信用の現在状態を返す。"""
        degree = self._resolve_chord_degree()
        return {
            "key": self._current_key if self._key_mode == "auto" else self._fixed_key,
            "scale": self._current_scale if self._key_mode == "auto" else self._fixed_scale,
            "chord_degree": degree,
            "chord_degree_float": self._chord_degree_float,
            "key_mode": self._key_mode,
            "chord_mode": self._chord_mode,
            "chord_interval": self._chord_interval,
            "fixed_chords": self._fixed_chords,
        }

    def start(self) -> None:
        if not self._running:
            self._running = True
            self._task = asyncio.get_running_loop().create_task(self._loop())
            log.info("MusicalControl 開始")

    def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None
        log.info("MusicalControl 停止")

    # ── 内部ループ ─────────────────────────────────────────────────────────

    async def _loop(self) -> None:
        while self._running:
            await asyncio.sleep(self._chord_interval)
            if not self._running:
                break
            await self._tick()

    async def _tick(self) -> None:
        markov_state = self._get_markov_state()

        # キーの更新
        if self._key_mode == "auto":
            self._auto_update_key(markov_state)

        # コードディグリーの更新
        if self._chord_mode == "auto":
            self._auto_update_chord(markov_state)
        else:
            # 固定モード: シーケンスを1ステップ進める
            self._fixed_chord_index = (
                (self._fixed_chord_index + 1) % len(self._fixed_chords)
            )

        # Tidal へ送信
        self._apply_tidal()

        # ブラウザへ状態を通知
        await self._broadcast({"type": "musical_state", "state": self.get_state()})

    # ── 自律モード: キー制御 ───────────────────────────────────────────────

    def _auto_update_key(self, markov_state: str) -> None:
        """五度圏に沿ってキーを確率的に変化させる。"""
        prob = STATE_KEY_CHANGE_PROB.get(markov_state, 0.10)
        if random.random() < prob:  # noqa: S311
            neighbors = KEY_NEIGHBORS.get(self._current_key, [])
            if neighbors:
                self._current_key = random.choice(neighbors)  # noqa: S311
                log.debug("キー変化 → %s", self._current_key)

        # スケールも状態に応じて確率的に変化
        weights_dict = STATE_SCALE_WEIGHTS.get(markov_state, {"minor": 1.0})
        scales = list(weights_dict.keys())
        weights = list(weights_dict.values())
        self._current_scale = random.choices(scales, weights=weights, k=1)[0]  # noqa: S311

    # ── 自律モード: コード制御（Middle BoundedWalk + Lower Dejavu） ──────────

    def _auto_update_chord(self, markov_state: str) -> None:
        """BoundedWalk でコードディグリー (0.0〜7.0) を更新する。"""
        zone = STATE_CHORD_ZONES.get(markov_state, STATE_CHORD_ZONES["medium"])

        # Middle: BoundedWalk（引力点に引き寄せられながらゾーン内を移動）
        middle_val = self._middle_next(self._chord_degree_float, zone)

        # Lower: Dejavu（スナップ確率で過去の値を再使用）
        final_val = self._lower_next(middle_val, zone, self._chord_history)

        self._chord_history.append(final_val)
        self._chord_degree_float = final_val

    def _middle_next(self, current: float, zone: dict[str, float]) -> float:
        """BoundedWalk: 引力点に引き寄せられながらゾーン内をドリフトする。"""
        center = zone["center"]
        width = zone["width"]
        speed = zone["speed"]

        drift = (center - current) * speed * 0.10
        noise = random.gauss(0.0, width * speed * 0.05)  # noqa: S311
        new_val = current + drift + noise

        lo = max(0.0, center - width)
        hi = min(7.0, center + width)
        return max(lo, min(hi, new_val))

    def _lower_next(
        self,
        middle_val: float,
        zone: dict[str, float],
        history: deque,
    ) -> float:
        """Dejavu: snap_prob の確率で履歴を再使用、そうでなければ micro_range で揺らす。"""
        snap_prob = zone["snap_prob"]
        micro_range = zone["micro_range"]

        if history and random.random() < snap_prob:  # noqa: S311
            return random.choice(list(history))  # noqa: S311

        noise = random.gauss(0.0, micro_range * 0.5)  # noqa: S311
        return max(0.0, min(7.0, middle_val + noise))

    # ── 現在のコードディグリーを解決する ───────────────────────────────────

    def _resolve_chord_degree(self) -> int:
        """現在のモードに基づいてコードディグリー (int) を返す。"""
        if self._chord_mode == "fixed":
            if self._fixed_chords:
                idx = self._fixed_chord_index % len(self._fixed_chords)
                return self._fixed_chords[idx]
            return 0
        return int(round(self._chord_degree_float)) % 8

    def _resolve_key_scale(self) -> tuple[str, str]:
        """現在のモードに基づいてキー・スケールを返す。"""
        if self._key_mode == "fixed":
            return self._fixed_key, self._fixed_scale
        return self._current_key, self._current_scale

    # ── Tidal コード送信 ───────────────────────────────────────────────────

    def _apply_tidal(self) -> None:
        """Tidal d8 チャンネルへコードを送る。"""
        if not self._tidal.is_running:
            return
        code = self._generate_tidal_code()
        log.debug("Tidal d8: %s", code)
        self._tidal.evaluate(code)

    @staticmethod
    def _scale_idx_to_hz(midi_base: int, scale_name: str, idx: int) -> float:
        """スケール上のインデックスをHz値に変換する。

        idx はスケール上の位置（0=ルート、1=2度、2=3度…）。
        インデックスがスケール音数を超えた場合はオクターブを上げる。
        BootTidal_matoma.hs の ArgList は n を持たないため、
        freq を直接 Hz で渡す必要がある。
        """
        intervals = SCALE_INTERVALS.get(scale_name, SCALE_INTERVALS["minor"])
        semitone = intervals[idx % len(intervals)]
        octave_bump = (idx // len(intervals)) * 12
        midi = midi_base + semitone + octave_bump
        return 440.0 * (2 ** ((midi - 69) / 12.0))

    def _generate_tidal_code(self) -> str:
        """コードディグリー・キー・スケールから Tidal コードを生成する。

        n (scale "scale_name" "degrees") + midi_base 形式を使う。
        """
        key, scale = self._resolve_key_scale()
        degree = self._resolve_chord_degree()

        midi_base = KEY_MIDI_BASE.get(key, 48)
        voicing = CHORD_VOICING.get(degree % 8, [0, 2, 4])
        voicing_str = " ".join(str(v) for v in voicing)

        return (
            f'd8 $ n (scale "{scale}" "{voicing_str}") + {midi_base}'
            f' # s "matoma_pad" # gain 0.5'
        )
