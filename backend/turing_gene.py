"""MaToMa Layer B: チューリング遺伝子（Turing Gene / Shift Register）
====================================================================
シフトレジスタによる変異型ピッチシーケンサー。

設計:
  - step_count ビットの循環レジスタ（シーンごとに異なる長さ）
  - 各ティックで mutation_prob の確率で先頭ビットを反転（Turing Machine 変異）
  - レジスタの全ビットをバイナリ数値として解釈 → シーンの scale にマッピング
  - mutation_bars 小節ごとに BPM 連動でティック（シーンDNAで速さが決まる）
  - 生成したピッチを OSC /matoma/drone/param freq <hz> で SC に送信
    → Layer A（呼吸する有機体）がこの周波数を中心に揺れる（centerVal）

5シーンの DNA プロファイル（autonomous_evolution.md セクション7と一致）:
  warm: mutationProb=0.03, scale=[0,2,3,5,7,8],     mutation_bars=8
  void: mutationProb=0.10, scale=[0,1,5,6,10],       mutation_bars=6
  vast: mutationProb=0.05, scale=[0,2,4,7,9],         mutation_bars=8
  lost: mutationProb=0.08, scale=[0,2,3,7,8],         mutation_bars=6
  peak: mutationProb=0.25, scale=[0,1,3,5,6,8,10],   mutation_bars=2

参照: synthesis_turing_machine.md
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Awaitable, Callable

log = logging.getLogger(__name__)


def _midi_to_hz(midi: float) -> float:
    """MIDIノート番号 → Hz（A4 = 440Hz 基準）。"""
    return 440.0 * (2.0 ** ((midi - 69.0) / 12.0))


@dataclass(frozen=True)
class TuringGeneDNA:
    """シーンごとの DNA プロファイル（不変オブジェクト）。

    Attributes:
        mutation_prob: ビット反転確率（0.0〜1.0）
        scale:         音程オフセット（半音単位、ルートからの距離）
        step_count:    シフトレジスタのステップ数
        mutation_bars: 何小節に1回ティックするか（BPMと連動）
        root_midi:     ルートノート（MIDIノート番号）
    """

    mutation_prob: float
    scale: tuple[int, ...]
    step_count: int
    mutation_bars: int
    root_midi: int = 41  # デフォルト: F2 ≈ 87Hz（低重心）


# ── 5シーンの DNA プロファイル ────────────────────────────────────────────────
# autonomous_evolution.md セクション7 の DNA 値と一致させる。
SCENE_DNA: dict[str, TuringGeneDNA] = {
    "warm": TuringGeneDNA(
        mutation_prob=0.03,
        scale=(0, 2, 3, 5, 7, 8),    # Dナチュラルマイナー（温かみ・低重心）
        step_count=8,
        mutation_bars=8,
        root_midi=41,   # F2: warm, low foundation
    ),
    "void": TuringGeneDNA(
        mutation_prob=0.10,
        scale=(0, 1, 5, 6, 10),      # 不安定・空虚な音程（Alva Noto的）
        step_count=10,
        mutation_bars=6,
        root_midi=44,   # GS2: mid-low, isolated
    ),
    "vast": TuringGeneDNA(
        mutation_prob=0.05,
        scale=(0, 2, 4, 7, 9),       # ペンタトニック（荘厳・広大）
        step_count=8,
        mutation_bars=8,
        root_midi=38,   # Db2: very low, cathedral-like
    ),
    "lost": TuringGeneDNA(
        mutation_prob=0.08,
        scale=(0, 2, 3, 7, 8),       # 孤独な短調（Burial的）
        step_count=12,
        mutation_bars=6,
        root_midi=40,   # E2: drifting, lonely
    ),
    "peak": TuringGeneDNA(
        mutation_prob=0.25,
        scale=(0, 1, 3, 5, 6, 8, 10),  # 7音スケール（複雑・高揚・Autechre的）
        step_count=16,
        mutation_bars=2,
        root_midi=53,   # F3: brighter root for energy peak
    ),
}


class TuringGene:
    """チューリング遺伝子シフトレジスタ（Layer B の実装）。

    外部コードから start()/stop()/set_bpm()/set_scene_dna() を呼び出す。
    ティックごとに OSC でピッチを SC に送信し、ブラウザへ状態を通知する。

    使い方:
        gene = TuringGene(sc_client.send_message, broadcast)
        gene.set_scene_dna("warm")
        gene.set_bpm(80.0)
        gene.start()
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

        self._bpm: float = 80.0
        self._dna: TuringGeneDNA = SCENE_DNA["warm"]

        # ランダム初期レジスタ
        self._register: list[int] = _random_register(self._dna.step_count)
        self._current_hz: float = _midi_to_hz(self._dna.root_midi)

    # ── 外部 API ─────────────────────────────────────────────────────────

    def start(self) -> None:
        """チューリング遺伝子のティックループを開始する。"""
        if not self._running:
            self._running = True
            self._task = asyncio.get_running_loop().create_task(self._loop())
            log.info("TuringGene: 開始")

    def stop(self) -> None:
        """ティックループを停止する。"""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        log.info("TuringGene: 停止")

    def set_bpm(self, bpm: float) -> None:
        """BPM を更新する。次のティック間隔に反映される。"""
        self._bpm = max(20.0, min(300.0, float(bpm)))

    def set_mutation_prob(self, prob: float) -> None:
        """CHAOS スライダーによる変異確率の上書き。

        シーン DNA の base 値を保持しつつ、リアルタイムに変異確率を変える。
        """
        clamped = max(0.0, min(1.0, float(prob)))
        # frozen dataclass は直接変更できないので、新インスタンスで差し替える
        self._dna = TuringGeneDNA(
            mutation_prob=clamped,
            scale=self._dna.scale,
            step_count=self._dna.step_count,
            mutation_bars=self._dna.mutation_bars,
            root_midi=self._dna.root_midi,
        )

    def set_mutation_bars(self, bars: int) -> None:
        """GUIから変異ティック間隔を上書きする。

        mutation_bars が小さいほど速くシフトレジスタが変化する。
        公式: interval = (60/BPM) * 4 * mutation_bars
        """
        clamped = max(1, min(32, int(bars)))
        self._dna = TuringGeneDNA(
            mutation_prob=self._dna.mutation_prob,
            scale=self._dna.scale,
            step_count=self._dna.step_count,
            mutation_bars=clamped,
            root_midi=self._dna.root_midi,
        )

    def set_scene_dna(self, scene_name: str) -> None:
        """シーン切替時に DNA を更新する。

        レジスタの状態は引き継ぐ（断絶せず有機的に移行する）。
        登録されていない scene_name の場合はスキップ。
        """
        dna = SCENE_DNA.get(scene_name)
        if dna is None:
            # 既存システムのシーン名（深淵/浮遊など）は無視し、現在の DNA を維持
            log.debug(f"TuringGene: '{scene_name}' は DNA 未登録。現在の DNA を維持")
            return

        old_len = self._dna.step_count
        self._dna = dna

        # レジスタ長を調整（切り詰め or ランダム延長）
        if dna.step_count > old_len:
            extra = _random_register(dna.step_count - old_len)
            self._register = self._register + extra
        else:
            self._register = self._register[: dna.step_count]

        log.info(
            f"TuringGene: DNA切替 → {scene_name} "
            f"(mutation_prob={dna.mutation_prob}, "
            f"mutation_bars={dna.mutation_bars})"
        )

    def get_state(self) -> dict:
        """現在の状態を辞書で返す（ブラウザ表示・デバッグ用）。"""
        return {
            "running": self._running,
            "register": list(self._register),
            "current_hz": round(self._current_hz, 2),
            "mutation_prob": self._dna.mutation_prob,
            "step_count": self._dna.step_count,
            "mutation_bars": self._dna.mutation_bars,
            "root_midi": self._dna.root_midi,
        }

    # ── 内部処理 ──────────────────────────────────────────────────────────

    def _clock_interval_sec(self) -> float:
        """mutation_bars 小節に対応するティック間隔（秒）を計算する。

        公式: interval = (60 / BPM) * 4 * mutation_bars
        """
        beats_per_bar = 4  # 4/4 拍子固定
        seconds_per_beat = 60.0 / self._bpm
        return seconds_per_beat * beats_per_bar * self._dna.mutation_bars

    def _tick(self) -> float:
        """1ティック進める。

        1. 先頭ビットを mutation_prob の確率で反転
        2. レジスタを循環シフト（末尾 → 先頭）
        3. レジスタ全体をバイナリ数値として解釈 → scale インデックス → Hz を返す
        """
        # 変異: 先頭ビットを確率的に反転
        if random.random() < self._dna.mutation_prob:  # noqa: S311
            self._register[0] ^= 1

        # 循環シフト（Turing Machine の特徴的な操作）
        self._register = [self._register[-1]] + self._register[:-1]

        # レジスタ値をスケール音程に変換
        reg_value = int("".join(str(b) for b in self._register), 2)
        scale = self._dna.scale
        semitone_offset = scale[reg_value % len(scale)]
        self._current_hz = _midi_to_hz(self._dna.root_midi + semitone_offset)

        return self._current_hz

    async def _loop(self) -> None:
        while self._running:
            interval = self._clock_interval_sec()
            await asyncio.sleep(interval)
            if not self._running:
                break

            hz = self._tick()

            # SC へ: ドローンのベース周波数を更新（Layer A がここを中心に揺れる）
            self._send_osc("/matoma/drone/param", ["freq", hz])

            # ブラウザへ通知（可視化パネル用）
            await self._broadcast(
                {
                    "type": "turing_tick",
                    "hz": round(hz, 2),
                    "register": list(self._register),
                    "mutation_prob": self._dna.mutation_prob,
                    "mutation_bars": self._dna.mutation_bars,
                }
            )

            log.debug(
                f"TuringGene tick: {hz:.1f}Hz | register={self._register}"
            )


# ── モジュール内ユーティリティ ────────────────────────────────────────────────

def _random_register(length: int) -> list[int]:
    """長さ length のランダムビット列を生成する。"""
    return [random.randint(0, 1) for _ in range(length)]  # noqa: S311
