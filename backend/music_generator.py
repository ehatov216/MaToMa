"""Multi-timescale Music Generator
====================================
3層構造でTidalコードを連続生成するアルゴリズム音楽生成エンジン。

UpperLayer  (~60-120秒): Markovによるスケール遷移
MiddleLayer (~4-8秒):   GravityMatrixによるコード度数選択
LowerLayer  (~1-2秒):   TidalコードをSCへ送信

SCENE DNAがシーンごとの音楽的性格を定義し、
Sonic Anatomyデータが初期スケール・音程・リズムをシードとして提供する。
"""

import asyncio
import logging
import math
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Protocol

from sonic_anatomy_bridge import (
    ROOT_TO_SEMITONE,
    SonicAnatomyRecord,
    pitch_class_to_freqs,
)
from tidal_controller import TidalController

log = logging.getLogger(__name__)


# ── スケール定義 ───────────────────────────────────────────────────────────

# スケール音程（ルート音からの半音数）
SCALE_INTERVALS: dict[str, list[int]] = {
    "major":    [0, 2, 4, 5, 7, 9, 11],
    "minor":    [0, 2, 3, 5, 7, 8, 10],
    "dorian":   [0, 2, 3, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
}

# ルート音のリスト（UpperLayerのランダム選択に使用）
ROOTS: list[str] = [
    "C", "Db", "D", "Eb", "E", "F", "Fs", "G", "Ab", "A", "Bb", "B"
]


# ── コード度数テーブル ──────────────────────────────────────────────────────

# 度数 → ルートからの半音オフセット
DEGREE_SEMITONES: dict[str, int] = {
    "I": 0, "II": 2, "III": 4, "IV": 5,
    "V": 7, "VI": 9, "VII": 11, "other": 3,
}

# GravityMatrix: シーンの引力タイプ → 度数の選択確率
GRAVITY: dict[str, dict[str, float]] = {
    "tonic": {
        "I":  0.25,
        "IV": 0.35,
        "V":  0.30,
        "VI": 0.10,
    },
    # V・VII・IIに引力 → 解決しない緊張感（lost/peakシーン用）
    # I度を避けることでトニックに帰着せず浮遊感が持続する
    "dominant": {
        "V":   0.45,
        "VII": 0.25,
        "II":  0.20,
        "IV":  0.10,
    },
}


# ── ユークリッドリズムテーブル ─────────────────────────────────────────────

# onset_density → (hits, steps) のマッピング
# density_threshold 未満なら対応する(hits, steps)を使用
# 各閾値で異なる (hits, steps) を割り当て、densityが変わるとリズムが変化する
_EUCLID_TABLE: list[tuple[float, int, int]] = [
    (0.15, 2, 16),   # 非常に疎: 16ステップに2打 → euclid 2 16
    (0.30, 3, 16),   # 疎:       16ステップに3打 → euclid 3 16
    (0.50, 3, 8),    # やや疎:   8ステップに3打  → euclid 3 8
    (0.65, 5, 16),   # 中:       16ステップに5打 → euclid 5 16
    (0.80, 5, 8),    # やや密:   8ステップに5打  → euclid 5 8
    (0.95, 7, 8),    # 密:       8ステップに7打  → euclid 7 8
    (1.01, 8, 8),    # 最密:     8ステップに8打  → euclid 8 8
]

# Markov遷移行列: 前の度数 → 次の度数の音楽的な自然遷移確率
# 各コードの "次にどこへ行くか" という調性機能上の傾向を定義する
DEGREE_TRANSITIONS: dict[str, dict[str, float]] = {
    "I":   {"IV": 0.35, "V": 0.30, "VI": 0.20, "II": 0.10, "I": 0.05},
    "II":  {"V": 0.50, "VII": 0.20, "IV": 0.15, "I": 0.15},
    "III": {"VI": 0.40, "IV": 0.30, "II": 0.20, "I": 0.10},
    "IV":  {"V": 0.35, "I": 0.30, "VI": 0.20, "II": 0.15},
    "V":   {"I": 0.50, "VI": 0.20, "IV": 0.15, "II": 0.15},
    "VI":  {"II": 0.30, "IV": 0.30, "V": 0.25, "I": 0.15},
    "VII": {"I": 0.55, "V": 0.25, "II": 0.20},
}

# ローマ数字の正規化: 大文字に統一・品質サフィックスを除去・括弧コードを"other"に
_ROMAN_QUALITY_STRIP = str.maketrans("", "", "majminaugdim+°")
_VALID_DEGREES = {"I", "II", "III", "IV", "V", "VI", "VII"}


def _normalize_roman(roman: str) -> str:
    """SAコード進行のローマ数字を標準7度数に正規化する。

    - 括弧コード "(F#)maj" → "other"（調外音はアーティスト特有の逸脱）
    - "IIImaj" → "III", "ivmaj" → "IV" など品質・ケースを除去
    """
    if roman.startswith("("):
        return "other"
    # 大文字化→品質サフィックス除去
    upper = roman.upper().translate(_ROMAN_QUALITY_STRIP).strip()
    return upper if upper in _VALID_DEGREES else "other"


def _build_sa_transition_matrix(
    chord_progression: list[dict],
) -> dict[str, dict[str, float]]:
    """SAコード進行データからMarkov遷移行列を構築する。

    chord_progression内の連続コードペアをカウントし、行ごとに正規化して
    確率分布を返す。"other"はカウントに含まれるが行列キーとしても使われる。

    Returns:
        {from_degree: {to_degree: probability}}
        空データや単一コードの場合は空の dict を返す。
    """
    # ローマ数字を正規化して連続ペアをカウント
    degrees = [
        _normalize_roman(c.get("roman", "I")) for c in chord_progression
    ]
    counts: dict[str, dict[str, float]] = {}
    for i in range(len(degrees) - 1):
        src, dst = degrees[i], degrees[i + 1]
        if src not in counts:
            counts[src] = {}
        counts[src][dst] = counts[src].get(dst, 0.0) + 1.0

    # 行ごとに正規化
    matrix: dict[str, dict[str, float]] = {}
    for src, dsts in counts.items():
        total = sum(dsts.values())
        matrix[src] = {d: v / total for d, v in dsts.items()}

    return matrix


# ── ヘルパー関数 ────────────────────────────────────────────────────────────

def quantize(midi_note: int, root_semi: int, mode: str) -> int:
    """MIDI音をスケール内の最近音にスナップする。

    Args:
        midi_note: 入力MIDI音番号 (0-127)
        root_semi: ルート音の半音数 (0=C, 3=Eb, ...)
        mode: "major" / "minor" / "dorian" / "phrygian"

    Returns:
        スケール内に補正されたMIDI音番号
    """
    intervals = SCALE_INTERVALS.get(mode, SCALE_INTERVALS["minor"])
    scale_pcs = [(root_semi + iv) % 12 for iv in intervals]
    pc = midi_note % 12

    def _pc_dist(a: int, b: int) -> int:
        d = abs(a - b)
        return min(d, 12 - d)

    closest_pc = min(scale_pcs, key=lambda s: _pc_dist(pc, s))
    octave = midi_note // 12
    candidate = octave * 12 + closest_pc

    # オクターブ調整（6半音以上離れていれば近い方へ寄せる）
    if candidate - midi_note > 6:
        candidate -= 12
    elif midi_note - candidate > 6:
        candidate += 12
    return candidate


def _select_euclid(density: float) -> tuple[int, int]:
    """onset_densityからユークリッドリズムの(hits, steps)を返す。"""
    for threshold, hits, steps in _EUCLID_TABLE:
        if density < threshold:
            return hits, steps
    return 8, 8


def _freqs_to_tidal_str(freqs: list[float]) -> str:
    """周波数リストをTidal記法の文字列に変換する。

    単一値: "155.6"
    複数値: '"<155.6 185.0 233.1>"'  ← Tidal角括弧パターン（引用符含む）
    """
    if not freqs:
        return "440.0"
    if len(freqs) == 1:
        return f"{freqs[0]:.1f}"
    inner = " ".join(f"{f:.1f}" for f in freqs)
    return f'"<{inner}>"'


def _hz_to_midi(hz: float) -> int:
    """Hzを最近いMIDI音番号に変換する（A4=440Hz=69）。"""
    if hz <= 0:
        return 60
    return round(69 + 12 * math.log2(hz / 440.0))


def _midi_to_hz(midi: int) -> float:
    """MIDI音番号をHz周波数に変換する。"""
    return 440.0 * (2 ** ((midi - 69) / 12.0))


def _apply_degree_shift(freqs: list[float], degree: str) -> list[float]:
    """コード度数に応じて周波数を半音シフトする。"""
    semitones = DEGREE_SEMITONES.get(degree, 0)
    if semitones == 0:
        return freqs
    ratio = 2 ** (semitones / 12.0)
    return [f * ratio for f in freqs]


def _rhythm_pattern_to_tidal(pattern: list[int]) -> str:
    """16ステップの0/1リズムパターンをTidal struct記法の文字列に変換する。

    例: [1,0,0,1,0,1,0,0,...] → '"t ~ ~ t ~ t ~ ~ ..."'
    """
    tokens = ["t" if step else "~" for step in pattern]
    return '"' + " ".join(tokens) + '"'


def _pitch_affinity(root: str, mode: str, pcd: list[float]) -> float:
    """スケール（root+mode）とpitch_class_distributionの親和度スコアを返す。

    スケール構成音のpcd値の合計を返す。
    値が大きいほど、そのキーは分析された楽曲の音使いと親和性が高い。
    """
    root_semi = ROOT_TO_SEMITONE.get(root, 0)
    intervals = SCALE_INTERVALS.get(mode, SCALE_INTERVALS["minor"])
    scale_pcs = [(root_semi + iv) % 12 for iv in intervals]
    return sum(pcd[pc] for pc in scale_pcs if pc < len(pcd))


def _compute_sa_activity_multiplier(
    onset_density: float, sa_seq: list[str]
) -> float:
    """SAデータの活動量から3層メロディ制御の緩和倍率を計算する。

    ドローン的なSA（onset_density低・コード多様性低）ほど大きな値を返し、
    MiddleLayer / UpperLayer / arc_speed の動きを比例的に抑制する。

    Returns:
        1.0: 通常（活動的なSA）
        最大 8.0: ドローン的なSA（コード変更をほぼ停止）
    """
    # onset_density: 0.0 → 4.0、0.3 → 1.0、0.4+ → 1.0
    density_factor = max(1.0, 4.0 - onset_density * 10.0)

    # コード多様性: ユニーク度数の種類数
    unique_degrees = len(set(sa_seq)) if sa_seq else 0
    if unique_degrees == 0:
        chord_factor = 4.0   # コード進行なし → 最大抑制
    elif unique_degrees == 1:
        chord_factor = 2.0   # 1種類のみ → 半分の速度
    elif unique_degrees == 2:
        chord_factor = 1.5   # 2種類 → やや抑制
    else:
        chord_factor = 1.0   # 3種類以上 → 通常

    return min(8.0, max(density_factor, chord_factor))


def _build_rhythmic_lines(
    synth_a: str,
    synth_b: str,
    density: float,
    degrade: float,
    amp_main: float,
    freq_str: str,
    tidal_slow: int = 4,
    rhythm_str: Optional[str] = None,
) -> list[str]:
    """d1 / d2 のリズム系Tidalコードを生成する（モジュールレベル関数）。

    SAリズムパターンがある場合は struct を使い、ない場合は euclid を使う。
    d2 の slow はシーンの tidal_slow に連動する。
    """
    hits, steps = _select_euclid(density)
    d2_slow = max(1, tidal_slow // 2)
    d2_degrade = min(degrade + 0.15, 0.92)
    d2_amp = amp_main * 0.6
    d1_rhythm = f"struct {rhythm_str}" if rhythm_str else f"euclid {hits} {steps}"
    return [
        f'd1 $ degradeBy {degrade:.2f} $ {d1_rhythm} '
        f'$ s "{synth_a}" # freq {freq_str} # amp {amp_main:.2f}',
        f'd2 $ slow {d2_slow} $ degradeBy {d2_degrade:.2f} '
        f'$ s "{synth_b}" # freq {freq_str} # amp {d2_amp:.2f}',
    ]


def _build_pad_lines(
    synth_a: str,
    synth_b: str,
    tidal_slow: int,
    amp_pad: float,
    chord_str: str,
    onset_density: float = 0.4,
) -> list[str]:
    """d5 / d6 のスロー系（パッド）Tidalコードを生成する（モジュールレベル関数）。"""
    very_slow = tidal_slow * 2
    d6_amp = amp_pad * 0.7
    d6_degrade = max(0.2, min(0.8, 0.8 - onset_density * 0.4))
    return [
        f'd5 $ slow {tidal_slow} $ s "{synth_a}" '
        f'# freq {chord_str} # amp {amp_pad:.2f}',
        f'd6 $ degradeBy {d6_degrade:.2f} $ slow {very_slow} '
        f'$ s "{synth_b}" # freq {chord_str} # amp {d6_amp:.2f}',
    ]


def _shape_melodic_contour(freqs: list[float], arc_phase: float) -> list[float]:
    """arc_phase に基づいてメロディ輪郭を形成する（Layer 5 - Melodic Contour）。

    Tidal の角括弧パターン内の周波数順が輪郭の方向性を決定する。
    arc_phase 0.00-0.33: ascending  (低→高, 緊張の積み上げ)
    arc_phase 0.33-0.67: arch       (中→高→低, エネルギーの弧)
    arc_phase 0.67-1.00: descending (高→低, 解決・落下)
    """
    if len(freqs) <= 1:
        return freqs
    asc = sorted(freqs)
    if arc_phase < 0.33:
        return asc
    if arc_phase < 0.67:
        # arch: 最低音 → 最高音 → 中音 (頂点経由)
        if len(asc) >= 3:
            return [asc[0], asc[-1], asc[1]]
        return [asc[-1], asc[0]]
    return list(reversed(asc))


def _build_expression_lines(
    synth_a: str,
    synth_b: str,
    tidal_slow: int,
    amp_exp: float,
    freq_str: str,
    arc_phase: float,
) -> list[str]:
    """d3 / d4 の表情層 Tidal コードを生成する（Layer 6 - Articulation）。

    d3: メロディ表情（arc_phase 連動パンニング + 振幅変調パターン）
    d4: ミクロダイナミクス（超スロー、対称パン、超低振幅フェード）
    """
    pan_d3 = round(0.2 + arc_phase * 0.6, 2)
    pan_d4 = round(0.8 - arc_phase * 0.6, 2)
    a0 = f"{amp_exp:.2f}"
    a1 = f"{amp_exp * 0.7:.2f}"
    a2 = f"{min(0.7, amp_exp * 1.3):.2f}"
    a3 = f"{amp_exp * 0.5:.2f}"
    amp_pat = f'"<{a0} {a1} {a2} {a3}>"'
    d4_slow = max(tidal_slow * 3, 6)
    d4_amp = round(amp_exp * 0.4, 2)
    return [
        f'd3 $ slow 2 $ degradeBy 0.4 $ s "{synth_a}" '
        f'# freq {freq_str} # amp {amp_pat} # pan {pan_d3}',
        f'd4 $ slow {d4_slow} $ degradeBy 0.7 '
        f'$ s "{synth_b}" # freq {freq_str} # amp {d4_amp} # pan {pan_d4}',
    ]


# ── データクラス ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Scale:
    """現在のスケール状態（イミュータブル）。"""
    root: str   # "C", "Eb" 等（ROOT_TO_SEMITONE と互換）
    mode: str   # "major" / "minor" / "dorian" / "phrygian"

    @property
    def root_semitone(self) -> int:
        return ROOT_TO_SEMITONE.get(self.root, 0)

    @property
    def sa_mode(self) -> str:
        """pitch_class_to_freqs 用にmajor/minorに丸める。"""
        return "major" if self.mode == "major" else "minor"


def _build_diatonic_voicing(
    degree: str, scale: Scale, octave: int = 3
) -> list[float]:
    """度数のダイアトニック3和音（ルート＋3度＋5度）をHz周波数リストで返す。

    スケール内音のみを使うため、調性から外れない。
    例: C minor + IV → F3-Ab3-C4

    Args:
        degree: "I" / "IV" / "V" / "VII" 等
        scale:  現在のスケール
        octave: ルート音のオクターブ（default 3 = C3周辺）

    Returns:
        [root_hz, third_hz, fifth_hz]
    """
    _DEGREE_TO_IDX: dict[str, int] = {
        "I": 0, "II": 1, "III": 2, "IV": 3,
        "V": 4, "VI": 5, "VII": 6, "other": 2,
    }

    intervals = SCALE_INTERVALS.get(scale.mode, SCALE_INTERVALS["minor"])
    root_semi = scale.root_semitone

    # スケールのピッチクラスリスト
    scale_pcs = [(root_semi + iv) % 12 for iv in intervals]

    # 度数名 → スケールインデックス（ダイアトニック音を直接使う）
    deg_idx = _DEGREE_TO_IDX.get(degree, 0) % len(scale_pcs)

    # 3度と5度（スケール内で +2, +4 ステップ）
    third_pc = scale_pcs[(deg_idx + 2) % len(scale_pcs)]
    fifth_pc = scale_pcs[(deg_idx + 4) % len(scale_pcs)]

    # 上向きスタッキングでMIDIノートに変換
    def _pc_above(pc: int, ref_midi: int) -> int:
        """pc を ref_midi 以上の最近い MIDI 番号に変換する（上向き）。"""
        ref_pc = ref_midi % 12
        midi = ref_midi - ref_pc + pc
        if midi < ref_midi:
            midi += 12
        return midi

    root_midi = octave * 12 + scale_pcs[deg_idx]
    third_midi = _pc_above(third_pc, root_midi)
    fifth_midi = _pc_above(fifth_pc, third_midi)

    return [
        _midi_to_hz(root_midi),
        _midi_to_hz(third_midi),
        _midi_to_hz(fifth_midi),
    ]


def _minimize_voice_leading(
    prev_voicing: list[float],
    next_voicing: list[float],
) -> list[float]:
    """前回ボイシングから次回ボイシングへの総セミトーン移動量を最小化する。

    各音を ±12 半音（1オクターブ）の範囲で最寄りの位置に動かし、
    前回との距離の合計が最小になるよう音を並び替えて返す。

    Args:
        prev_voicing: 前回コードのHz周波数リスト（空の場合は next_voicing そのまま）
        next_voicing: 今回コードのHz周波数リスト

    Returns:
        voice leading 最適化後のHz周波数リスト（要素数は next_voicing と同じ）
    """
    if not prev_voicing or not next_voicing:
        return list(next_voicing)

    prev_midi = [_hz_to_midi(f) for f in prev_voicing]
    next_midi = [_hz_to_midi(f) for f in next_voicing]

    # 各 next 音を prev の各音に最も近いオクターブへ移動させた候補を作る
    def _closest(src: float, target: float) -> float:
        """target を src に最も近いオクターブに移動させた MIDI 値を返す。"""
        diff = (target - src + 6) % 12 - 6  # -6 〜 +5 に丸める
        return src + diff

    # 貪欲に prev の各音に最も近い next 音を割り当てる（簡易最適化）
    used = [False] * len(next_midi)
    result_midi: list[float] = []
    for p in prev_midi:
        best_idx = -1
        best_dist = float("inf")
        for i, n in enumerate(next_midi):
            if used[i]:
                continue
            candidate = _closest(p, n)
            dist = abs(candidate - p)
            if dist < best_dist:
                best_dist = dist
                best_idx = i
        if best_idx >= 0:
            used[best_idx] = True
            result_midi.append(_closest(p, next_midi[best_idx]))
        # prev 音に対応できなかった場合はスキップ（次の処理で補完）

    # next 側に余りがあれば末尾に追加
    for i, n in enumerate(next_midi):
        if not used[i]:
            result_midi.append(float(n))

    return [_midi_to_hz(m) for m in result_midi]


@dataclass
class GlobalClock:
    """スケール状態をTidalサイクル境界で安全に切り替える。"""
    current_scale: Scale = field(
        default_factory=lambda: Scale(root="C", mode="minor")
    )
    pending_scale: Optional[Scale] = None

    def request_scale_change(self, scale: Scale) -> None:
        """次のサイクル境界でスケールを切り替えるためキューに入れる。"""
        self.pending_scale = scale

    def on_cycle_boundary(self) -> bool:
        """Tidalサイクル境界でペンディングのスケール変更を適用する。

        Returns:
            True: スケールが変更された
        """
        if self.pending_scale is not None:
            self.current_scale = self.pending_scale
            self.pending_scale = None
            log.info(
                f"スケール変更: root={self.current_scale.root} "
                f"mode={self.current_scale.mode}"
            )
            return True
        return False


# ── Strategyパターン ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MiddleLayerContext:
    """MiddleLayerStrategy.tick() に渡す入力（イミュータブル）。"""
    dna: dict
    current_degree: str
    sa_chord_sequence: tuple  # tuple[str, ...]
    sa_chord_idx: int
    # Phase 1: SA遷移行列とのブレンド率（0.0=理論Markov, 1.0=SA派生）
    divergence_rate: float = 0.0
    # Phase 1: SA由来の遷移行列（frozenのためtuple of tuples で格納）
    # 例: (("I", (("IV", 0.5), ("V", 0.5))), ...)
    sa_transition_matrix: tuple = ()


@dataclass(frozen=True)
class MiddleLayerResult:
    """MiddleLayerStrategy.tick() の返り値。"""
    degree: str
    sa_chord_idx: int


@dataclass(frozen=True)
class LowerLayerContext:
    """LowerLayerStrategy.generate() に渡す入力（イミュータブル）。"""
    scale: Scale
    dna: dict
    seed: Optional[SonicAnatomyRecord]
    current_degree: str
    arc_phase: float
    synth_a: str
    synth_b: str
    # Phase 2: 前のコードボイシング（Hzリスト）、ボイスリーディング最小化に使用
    prev_voicing: tuple = ()  # tuple[float, ...]


class MiddleLayerStrategy(Protocol):
    """MiddleLayerのアルゴリズムインターフェース。"""

    def tick(self, ctx: MiddleLayerContext) -> MiddleLayerResult: ...


class LowerLayerStrategy(Protocol):
    """LowerLayerのアルゴリズムインターフェース。"""

    def generate(self, ctx: LowerLayerContext, include_pads: bool) -> list[str]: ...


class GravityMarkovStrategy:
    """Gravity Matrix + Markov 遷移によるコード度数選択（デフォルト MiddleLayer）。

    混合比率: GravityMatrix 40% + Markov遷移 60% + SAコード進行 +40%ブースト
    """

    def tick(self, ctx: MiddleLayerContext) -> MiddleLayerResult:
        all_degrees = ["I", "II", "III", "IV", "V", "VI", "VII"]
        dna = ctx.dna
        sa_seq = list(ctx.sa_chord_sequence)
        sa_idx = ctx.sa_chord_idx
        divergence_rate = ctx.divergence_rate

        gravity_type = dna.get("chord_gravity", "tonic")
        gravity_map = GRAVITY.get(gravity_type, GRAVITY["tonic"])
        gravity_raw = {d: gravity_map.get(d, 0.0) for d in all_degrees}

        # Phase 1: divergence_rate で DEGREE_TRANSITIONS と SA遷移行列をブレンド
        # 0.0 = 純粋な音楽理論Markov, 1.0 = SA由来の遷移行列
        theory_map = DEGREE_TRANSITIONS.get(ctx.current_degree, {})
        theory_raw = {d: theory_map.get(d, 0.0) for d in all_degrees}

        if divergence_rate > 0.0 and ctx.sa_transition_matrix:
            # tuple of tuples → dict に復元
            sa_matrix = {
                src: dict(dsts)
                for src, dsts in ctx.sa_transition_matrix
            }
            sa_map = sa_matrix.get(ctx.current_degree, {})
            sa_markov_raw = {d: sa_map.get(d, 0.0) for d in all_degrees}

            sa_total = sum(sa_markov_raw.values())
            if sa_total > 0:
                sw = {d: sa_markov_raw[d] / sa_total for d in all_degrees}
            else:
                sw = {d: 1.0 / len(all_degrees) for d in all_degrees}

            t_total = sum(theory_raw.values())
            uniform_t = 1.0 / len(all_degrees)
            tw = (
                {d: theory_raw[d] / t_total for d in all_degrees}
                if t_total > 0 else {d: uniform_t for d in all_degrees}
            )
            # 線形ブレンド: (1 - rate) × 理論 + rate × SA
            markov_raw = {
                d: (1.0 - divergence_rate) * tw[d] + divergence_rate * sw[d]
                for d in all_degrees
            }
        else:
            markov_raw = theory_raw

        uniform = 1.0 / len(all_degrees)
        g_total = sum(gravity_raw.values())
        m_total = sum(markov_raw.values())
        gw = (
            {d: gravity_raw[d] / g_total for d in all_degrees}
            if g_total > 0 else {d: uniform for d in all_degrees}
        )
        mw = (
            {d: markov_raw[d] / m_total for d in all_degrees}
            if m_total > 0 else {d: uniform for d in all_degrees}
        )
        blended = {d: 0.4 * gw[d] + 0.6 * mw[d] for d in all_degrees}

        sa_degree: str | None = None
        if sa_seq:
            sa_degree = sa_seq[sa_idx % len(sa_seq)]
            if sa_degree in blended:
                blended[sa_degree] *= 1.4

        total = sum(blended.values())
        weights = [blended[d] / total for d in all_degrees]
        chosen = random.choices(all_degrees, weights=weights, k=1)[0]
        new_idx = (sa_idx + 1) % len(sa_seq) if sa_seq else 0

        log.debug(
            "MiddleLayer[GravityMarkov]: コード度数 → %s "
            "(SA引力点=%s, Markov元=%s, divergence=%.2f)",
            chosen, sa_degree or "none", ctx.current_degree, divergence_rate,
        )
        return MiddleLayerResult(degree=chosen, sa_chord_idx=new_idx)


class EuclidTemplateStrategy:
    """ユークリッドリズム + Tidalテンプレートによる LowerLayer デフォルト実装。"""

    def generate(self, ctx: LowerLayerContext, include_pads: bool) -> list[str]:
        scale = ctx.scale
        dna = ctx.dna
        seed = ctx.seed
        degree = ctx.current_degree

        onset_density = (
            seed.onset_density if seed
            else dna.get("onset_density_target", 0.4)
        )
        tidal_slow = dna.get("tidal_slow", 4)

        amp_main = min(0.7, max(0.1,
            0.3 + onset_density * 0.4 + random.gauss(0, 0.03)
        ))
        amp_pad = min(0.4, max(0.05,
            0.1 + onset_density * 0.2 + random.gauss(0, 0.02)
        ))
        degrade = max(0.05, min(0.95,
            0.9 - onset_density + random.gauss(0, 0.04)
        ))

        melody_octave = 5 if ctx.arc_phase > 0.6 else 4

        if seed:
            raw_main = pitch_class_to_freqs(
                seed.pitch_class_distribution,
                scale.root, scale.sa_mode,
                top_n=3, octave=melody_octave,
            )
        else:
            root_hz = _midi_to_hz(melody_octave * 12 + scale.root_semitone)
            raw_main = [root_hz, root_hz * 1.498]

        raw_chord_hz = _build_diatonic_voicing(degree, scale, octave=3)
        # Phase 2: voice leading — 前回コードへの移動量を最小化
        chord_hz = _minimize_voice_leading(list(ctx.prev_voicing), raw_chord_hz)
        shifted_main = _apply_degree_shift(raw_main, degree)
        root_s = scale.root_semitone
        quantized_main = [
            _midi_to_hz(quantize(_hz_to_midi(f), root_s, scale.mode))
            for f in shifted_main if f > 0
        ]
        # Layer 5: Melodic Contour — arc_phase で輪郭方向を整形
        contoured = _shape_melodic_contour(quantized_main[:3], ctx.arc_phase)
        freq_str = _freqs_to_tidal_str(contoured)
        chord_str = _freqs_to_tidal_str(chord_hz)

        rhythm_str: Optional[str] = None
        if seed and seed.rhythm_pattern:
            rhythm_str = _rhythm_pattern_to_tidal(seed.rhythm_pattern)

        lines = _build_rhythmic_lines(
            ctx.synth_a, ctx.synth_b,
            onset_density, degrade, amp_main, freq_str,
            tidal_slow=tidal_slow, rhythm_str=rhythm_str,
        )
        if include_pads:
            lines += _build_pad_lines(
                ctx.synth_a, ctx.synth_b,
                tidal_slow, amp_pad, chord_str,
                onset_density=onset_density,
            )
            # Layer 6: Articulation — d3/d4 で表情・ミクロダイナミクス
            lines += _build_expression_lines(
                ctx.synth_a, ctx.synth_b,
                tidal_slow, amp_pad, freq_str, ctx.arc_phase,
            )
        return lines


class LSystemStrategy:
    """L-System（Lindenmayerシステム）による自己相似的リズム生成 LowerLayer 実装。

    公理 "F" / "G" から書き換えルールを反復適用してリズム文字列を生成し、
    Tidal の struct パターンに変換する。
    onset_density が深度を決定し、高密度ほど複雑な自己相似構造を生成する。

    RAG: design_multiscale_generation.md — 下位レイヤー=Lシステム（ミクロモチーフ）
    """

    # onset_density < 0.5: 疎・広がり / >= 0.5: 密・緊張
    _RULE_SETS: dict[str, dict[str, str]] = {
        "sparse": {"F": "F-F", "G": "F--G"},
        "dense":  {"F": "FF-F", "G": "FGF"},
    }

    def _evolve(self, axiom: str, rules: dict[str, str], depth: int) -> str:
        """L-System 文字列置換を depth 世代分適用する。"""
        current = axiom
        for _ in range(depth):
            current = "".join(rules.get(c, c) for c in current)
            if len(current) > 256:  # 爆発防止
                break
        return current

    def _to_rhythm_pattern(self, lstring: str, steps: int = 16) -> list[int]:
        """L-System 文字列を steps 個の 0/1 リズムパターンに変換する。

        F → 1 (音あり), - → 0 (休符), それ以外は無視
        """
        raw: list[int] = [
            1 if ch == "F" else 0
            for ch in lstring if ch in ("F", "-")
        ]
        if not raw:
            return [1] + [0] * (steps - 1)
        if len(raw) >= steps:
            indices = [int(i * len(raw) / steps) for i in range(steps)]
            return [raw[i] for i in indices]
        return [raw[i % len(raw)] for i in range(steps)]

    def generate(self, ctx: LowerLayerContext, include_pads: bool) -> list[str]:
        scale = ctx.scale
        dna = ctx.dna
        seed = ctx.seed
        degree = ctx.current_degree

        onset_density = (
            seed.onset_density if seed
            else dna.get("onset_density_target", 0.4)
        )
        tidal_slow = dna.get("tidal_slow", 4)

        # 深度: onset_density 高いほど複雑 (1〜4)
        depth = max(1, min(4, round(1 + onset_density * 4)))

        rules = (
            self._RULE_SETS["dense"] if onset_density >= 0.5
            else self._RULE_SETS["sparse"]
        )
        axiom = random.choice(["F", "G"])
        lstring = self._evolve(axiom, rules, depth)
        rhythm_16 = self._to_rhythm_pattern(lstring, steps=16)
        if sum(rhythm_16) == 0:
            rhythm_16[0] = 1

        rhythm_str = _rhythm_pattern_to_tidal(rhythm_16)

        raw_amp = 0.3 + onset_density * 0.4 + random.gauss(0, 0.03)
        amp_main = min(0.7, max(0.1, raw_amp))
        raw_pad = 0.1 + onset_density * 0.2 + random.gauss(0, 0.02)
        amp_pad = min(0.4, max(0.05, raw_pad))
        raw_deg = 0.9 - onset_density + random.gauss(0, 0.04)
        degrade = max(0.05, min(0.95, raw_deg))

        melody_octave = 5 if ctx.arc_phase > 0.6 else 4

        if seed:
            raw_main = pitch_class_to_freqs(
                seed.pitch_class_distribution,
                scale.root, scale.sa_mode,
                top_n=3, octave=melody_octave,
            )
        else:
            root_hz = _midi_to_hz(melody_octave * 12 + scale.root_semitone)
            raw_main = [root_hz, root_hz * 1.498]

        raw_chord_hz = _build_diatonic_voicing(degree, scale, octave=3)
        # Phase 2: voice leading — 前回コードへの移動量を最小化
        chord_hz = _minimize_voice_leading(list(ctx.prev_voicing), raw_chord_hz)
        shifted_main = _apply_degree_shift(raw_main, degree)
        root_s = scale.root_semitone
        quantized_main = [
            _midi_to_hz(quantize(_hz_to_midi(f), root_s, scale.mode))
            for f in shifted_main if f > 0
        ]
        # Layer 5: Melodic Contour — arc_phase で輪郭方向を整形
        contoured = _shape_melodic_contour(quantized_main[:3], ctx.arc_phase)
        freq_str = _freqs_to_tidal_str(contoured)
        chord_str = _freqs_to_tidal_str(chord_hz)

        lines = _build_rhythmic_lines(
            ctx.synth_a, ctx.synth_b,
            onset_density, degrade, amp_main, freq_str,
            tidal_slow=tidal_slow, rhythm_str=rhythm_str,
        )
        if include_pads:
            lines += _build_pad_lines(
                ctx.synth_a, ctx.synth_b,
                tidal_slow, amp_pad, chord_str,
                onset_density=onset_density,
            )
            # Layer 6: Articulation — d3/d4 で表情・ミクロダイナミクス
            lines += _build_expression_lines(
                ctx.synth_a, ctx.synth_b,
                tidal_slow, amp_pad, freq_str, ctx.arc_phase,
            )

        log.debug(
            "LSystemStrategy: depth=%d axiom=%s pattern=%s hits=%d/16",
            depth, axiom, lstring[:24], sum(rhythm_16),
        )
        return lines


# 利用可能なStrategyのレジストリ
_MIDDLE_STRATEGIES: dict[str, MiddleLayerStrategy] = {
    "gravity_markov": GravityMarkovStrategy(),
}

_LOWER_STRATEGIES: dict[str, LowerLayerStrategy] = {
    "euclid_template": EuclidTemplateStrategy(),
    "l_system": LSystemStrategy(),
}


# ── メイン生成エンジン ─────────────────────────────────────────────────────

class MusicGenerator:
    """Multi-timescale Algorithm の実装。

    3層（Upper / Middle / Lower）が協調してTidalコードを生成する。
    TidalController.evaluate() を通じてTidalへ送信する。

    Usage:
        gen = MusicGenerator(tidal_controller)
        gen.set_scene(SCENE_DNA["void"])
        gen.set_seed(sonic_anatomy_record)
        gen.start()
        # ... 実行中 ...
        gen.stop()
    """

    # Tidalシンセ名（d1-d6チャンネル用）
    _SYNTH_A = "matoma_rhythmic_spring"
    _SYNTH_B = "matoma_rhythmic_grain"

    def __init__(
        self,
        tidal: TidalController,
        broadcast=None,
        send_osc=None,
    ) -> None:
        self._tidal = tidal
        self._broadcast = broadcast  # async broadcast(dict) → WebSocket全体配信
        self._send_osc = send_osc   # _send_osc(address, args) → SC OSC送信
        self._loop: Optional[object] = None  # メインイベントループ（start()時に取得）
        self._clock = GlobalClock()
        self._scene_dna: dict = {}
        self._seed: Optional[SonicAnatomyRecord] = None
        self._current_degree: str = "I"
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        # MiddleLayer変更フラグ（パッド音源の再送信判断に使用）
        self._pad_dirty = True
        # 和声リズム: BPM連動のコード変更タイミング
        self._bpm: float = 120.0
        self._harmonic_bars: int = 4
        self._secs_since_chord_change: float = 0.0
        # メロディアーク: フレーズ輪郭の緩やかな上下（0.0〜1.0の三角波）
        self._arc_phase: float = 0.0
        self._arc_direction: int = 1   # +1=上昇中, -1=下降中
        self._arc_speed: float = 0.02  # 1 tick あたりの進行速度
        # SA由来のコード進行シーケンス（MiddleLayerの引力点）
        self._sa_chord_sequence: list[str] = []
        self._sa_chord_idx: int = 0
        # SAデータの活動量に基づく3層制御の緩和倍率（1.0=通常、最大8.0=ドローン）
        self._sa_activity_multiplier: float = 1.0
        # Phase 1: divergence_rate（0.0=理論Markov, 1.0=SA派生行列）
        self._divergence_rate: float = 0.0
        # Phase 1: SAコード進行から構築したMarkov遷移行列
        self._sa_transition_matrix: dict[str, dict[str, float]] = {}
        # Phase 2: 前のコードボイシング（ボイスリーディング最小化用）
        self._prev_voicing: list[float] = []
        # 交換可能なStrategy（実行時に set_middle_strategy / set_lower_strategy で変更可）
        self._middle_strategy: MiddleLayerStrategy = GravityMarkovStrategy()
        self._lower_strategy: LowerLayerStrategy = EuclidTemplateStrategy()
        # 最後に送信したTidalコード（UIでの可視化用）
        self._last_tidal_lines: list[str] = []
        # UpperLayerの次のスケール変更まで残り tick 数（UI表示用）
        self._upper_tick_counter: int = 0
        self._upper_every: int = 30
        # ユーザー固定override（Noneの場合はSAやDNAに従う）
        self._density_override: Optional[float] = None

    # ── 公開API ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """生成ループを開始する（既に実行中なら無視）。"""
        if self._running:
            return
        # メインイベントループを保存（async コンテキストから呼ばれる想定）
        try:
            self._loop = asyncio.get_event_loop()
        except RuntimeError:
            self._loop = None
        self._running = True
        self._thread = threading.Thread(
            target=self._generation_loop, daemon=True, name="MusicGenerator"
        )
        self._thread.start()
        log.info("MusicGenerator 開始")

    def stop(self) -> None:
        """生成ループを停止する。"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None
        log.info("MusicGenerator 停止")

    def set_seed(self, record: SonicAnatomyRecord) -> None:
        """Sonic Anatomyデータをシードとして設定する。

        SAのキー情報から初期スケールを設定し、
        次のサイクル境界でスケールが適用される。
        chord_progression をMiddleLayerの引力点シーケンスとして展開する。
        """
        # コード進行シーケンスを展開（duration_beatsに応じて繰り返す）
        sa_seq: list[str] = []
        for chord in record.chord_progression:
            roman = chord.get("roman", "I")
            # 4拍=1コマ、8拍=2コマとして展開
            repeats = max(1, round(chord.get("duration_beats", 4) / 4))
            sa_seq.extend([roman] * repeats)

        multiplier = _compute_sa_activity_multiplier(
            record.onset_density, sa_seq
        )
        # Phase 1: SA遷移行列を構築（divergence_rate > 0 のときに使われる）
        sa_matrix = _build_sa_transition_matrix(record.chord_progression)

        with self._lock:
            self._seed = record
            self._pad_dirty = True
            self._bpm = max(40.0, record.bpm)  # 下限40BPMでガード
            self._sa_chord_sequence = sa_seq
            self._sa_chord_idx = 0
            self._sa_activity_multiplier = multiplier
            self._sa_transition_matrix = sa_matrix

        mode = (
            record.key_mode if record.key_mode in SCALE_INTERVALS else "minor"
        )
        new_scale = Scale(root=record.key_root, mode=mode)
        self._clock.request_scale_change(new_scale)
        log.info(
            f"SA シード設定: bpm={record.bpm:.1f} "
            f"key={record.key_root}/{record.key_mode} "
            f"onset={record.onset_density:.2f} "
            f"chord_seq={sa_seq} "
            f"activity_multiplier={multiplier:.2f}"
        )

    def set_scene(self, dna: dict) -> None:
        """SCENE DNAを適用する。

        Args:
            dna: SCENE_DNA の1エントリ
                 {"scale_change_prob": 0.02, "preferred_modes": [...], ...}
        """
        with self._lock:
            self._scene_dna = dna
            self._pad_dirty = True
            self._harmonic_bars = dna.get("harmonic_bars", 4)
            self._arc_speed = dna.get("arc_speed", 0.02)
        log.info(
            f"SCENE DNA 適用: gravity={dna.get('chord_gravity')} "
            f"density_target={dna.get('onset_density_target')} "
            f"harmonic_bars={dna.get('harmonic_bars', 4)}"
        )

    # ── 調性OSC送信 ─────────────────────────────────────────────────────────

    # ドローン用オクターブ（C2 = 65.41Hz、低域ドローンに適した音域）
    _DRONE_OCTAVE = 2

    def _compute_harm(self) -> dict:
        """現在のLayer1/2状態からharm辞書を計算する。

        Returns:
            {root, mode, rootHz, degree, degreeHz}
            rootHz / degreeHz はドローン用オクターブ（C2≈65Hz基準）のHz値。
        """
        with self._lock:
            scale = self._clock.current_scale
            degree = self._current_degree

        root_semi = ROOT_TO_SEMITONE.get(scale.root, 0)
        degree_semi = DEGREE_SEMITONES.get(degree, 0)

        # ドローンオクターブ（MIDI 36 = C2 = 65.41Hz）
        root_midi = self._DRONE_OCTAVE * 12 + root_semi
        degree_midi = root_midi + degree_semi

        return {
            "root":     scale.root,
            "mode":     scale.mode,
            "rootHz":   round(_midi_to_hz(root_midi), 3),
            "degree":   degree,
            "degreeHz": round(_midi_to_hz(degree_midi), 3),
        }

    def _send_harm(self) -> None:
        """SCへ /matoma/harm/update を送信する。

        Layer1（スケール変更）またはLayer2（コード度数変更）後に呼ぶ。
        SCの~harmが更新され、ドローンとgran_synthのfreqが即座に追従する。
        """
        if self._send_osc is None:
            return
        h = self._compute_harm()
        self._send_osc("/matoma/harm/update", [
            h["root"], h["mode"], h["rootHz"],
            h["degree"], h["degreeHz"],
        ])
        log.info(
            "harm送信: %s %s %s → rootHz=%.2f degreeHz=%.2f",
            h["root"], h["mode"], h["degree"], h["rootHz"], h["degreeHz"],
        )

    def set_root(self, root: str) -> None:
        """ルート音を即座に変更する（例: "C", "Eb", "G"）。"""
        mode = self._clock.current_scale.mode
        self._clock.request_scale_change(Scale(root=root, mode=mode))
        self._clock.on_cycle_boundary()  # 即座に反映
        self._send_harm()
        log.info("UpperLayer override: root=%s", root)

    def set_scale(self, mode: str) -> None:
        """スケール（モード）を即座に変更する（例: "minor", "dorian"）。"""
        if mode not in SCALE_INTERVALS:
            log.warning("未知のスケール: %s", mode)
            return
        root = self._clock.current_scale.root
        self._clock.request_scale_change(Scale(root=root, mode=mode))
        self._clock.on_cycle_boundary()  # 即座に反映
        self._send_harm()
        log.info("UpperLayer override: mode=%s", mode)

    def set_density(self, density: float) -> None:
        """onset_density を上書きする（0.0〜1.0）。Noneで解除。"""
        with self._lock:
            self._density_override = (
                max(0.0, min(1.0, density))
                if density is not None else None
            )
        log.info("LowerLayer density override: %s", self._density_override)

    def set_divergence(self, rate: float) -> None:
        """divergence_rate を設定する（0.0〜1.0）。

        0.0 = 純粋な音楽理論Markov遷移（DEGREE_TRANSITIONS のみ使用）
        1.0 = SAコード進行由来の遷移行列のみ使用
        中間値は線形ブレンド。
        """
        clamped = max(0.0, min(1.0, rate))
        with self._lock:
            self._divergence_rate = clamped
        log.info("MiddleLayer divergence_rate → %.2f", clamped)

    def get_state(self) -> dict:
        """UI向けの現在状態スナップショットを返す。"""
        with self._lock:
            scale = self._clock.current_scale
            degree = self._current_degree
            arc = self._arc_phase
            bpm = self._bpm
            bars = self._harmonic_bars
            secs = self._secs_since_chord_change
            sa_mult = self._sa_activity_multiplier
            upper_tick = self._upper_tick_counter
            upper_every = self._upper_every
            lines = list(self._last_tidal_lines)
            density = self._density_override
            divergence_rate = self._divergence_rate
            mid_name = type(self._middle_strategy).__name__
            low_name = type(self._lower_strategy).__name__

        bar_secs = (60.0 / bpm) * 4 if bpm > 0 else 2.0
        chord_interval = bar_secs * bars * sa_mult
        chord_remaining = max(0.0, chord_interval - secs)

        tick_interval = 2.0
        upper_remaining = max(0.0, (upper_every - upper_tick) * tick_interval)

        # harm計算（UI表示用）
        root_semi = ROOT_TO_SEMITONE.get(scale.root, 0)
        degree_semi = DEGREE_SEMITONES.get(degree, 0)
        root_midi = self._DRONE_OCTAVE * 12 + root_semi
        root_hz = round(_midi_to_hz(root_midi), 2)
        degree_hz = round(_midi_to_hz(root_midi + degree_semi), 2)

        return {
            "type": "score_state",
            "running": self._running,
            # Layer 1（上位・スケール）
            "root": scale.root,
            "mode": scale.mode,
            "upper_remaining_secs": round(upper_remaining, 1),
            # Layer 2（中位・コード度数）
            "degree": degree,
            "chord_remaining_secs": round(chord_remaining, 1),
            # harm周波数（SCへの実反映値）
            "rootHz": root_hz,
            "degreeHz": degree_hz,
            # Layer 3（下位・Tidalコード）
            "tidal_lines": lines,
            # メタ
            "arc_phase": round(arc, 2),
            "density_override": density,
            "divergence_rate": round(divergence_rate, 2),
            "middle_strategy": mid_name,
            "lower_strategy": low_name,
        }

    def set_middle_strategy(self, name: str) -> None:
        """MiddleLayerのアルゴリズムを実行時に切り替える。

        Args:
            name: 利用可能な戦略名（"gravity_markov" など）
        """
        strategy = _MIDDLE_STRATEGIES.get(name)
        if strategy is None:
            log.warning(
                "MiddleLayer strategy 不明: %s (利用可能: %s)",
                name, list(_MIDDLE_STRATEGIES.keys()),
            )
            return
        with self._lock:
            self._middle_strategy = strategy
        log.info("MiddleLayer strategy → %s", name)

    def set_lower_strategy(self, name: str) -> None:
        """LowerLayerのアルゴリズムを実行時に切り替える。

        Args:
            name: 利用可能な戦略名（"euclid_template" など）
        """
        strategy = _LOWER_STRATEGIES.get(name)
        if strategy is None:
            log.warning(
                "LowerLayer strategy 不明: %s (利用可能: %s)",
                name, list(_LOWER_STRATEGIES.keys()),
            )
            return
        with self._lock:
            self._lower_strategy = strategy
        log.info("LowerLayer strategy → %s", name)

    # ── 内部レイヤー処理 ────────────────────────────────────────────────────

    def _upper_layer_tick(self) -> None:
        """UpperLayer: Markovによるスケール遷移チェック（~60-120秒周期）。

        pitch_class_distribution が利用可能なら親和度で重み付け選択する。
        """
        with self._lock:
            dna = self._scene_dna
            seed = self._seed
            sa_multiplier = self._sa_activity_multiplier

        if not dna:
            return

        # SA活動量が低い（ドローン的）ほど確率を下げる
        prob = dna.get("scale_change_prob", 0.02) / sa_multiplier
        if random.random() < prob:
            modes = dna.get("preferred_modes", ["minor"])
            new_mode = random.choice(modes)

            # SAの pitch_class_distribution で親和度スコアを計算し重み付け選択する
            # （純ランダムではなく、元の曲の音使いに親和するキーへ遷移しやすくなる）
            if seed and seed.pitch_class_distribution:
                pcd = seed.pitch_class_distribution
                scores = [_pitch_affinity(r, new_mode, pcd) for r in ROOTS]
                total = sum(scores)
                weights = [s / total for s in scores] if total > 0 else None
                new_root = random.choices(ROOTS, weights=weights, k=1)[0]
            else:
                new_root = random.choice(ROOTS)

            self._clock.request_scale_change(
                Scale(root=new_root, mode=new_mode)
            )
            log.info(
                f"UpperLayer: スケール変更予約 root={new_root} mode={new_mode}"
            )
            # スケール変更予約と同時にharmを先行送信（ドローン追従を早める）
            self._send_harm()

    def _middle_layer_tick(self) -> None:
        """MiddleLayer: 現在の _middle_strategy に委譲してコード度数を選択する（~4-8秒）。

        デフォルトは GravityMarkovStrategy（Gravity+Markov+SAブレンド）。
        set_middle_strategy() で実行時に切り替え可能。
        """
        with self._lock:
            dna = self._scene_dna
            current_degree = self._current_degree
            sa_seq = tuple(self._sa_chord_sequence)
            sa_idx = self._sa_chord_idx
            strategy = self._middle_strategy
            divergence_rate = self._divergence_rate
            # SA遷移行列を frozen な tuple of tuples に変換して Context へ渡す
            sa_matrix_tuple = tuple(
                (src, tuple(dsts.items()))
                for src, dsts in self._sa_transition_matrix.items()
            )

        if not dna:
            return

        ctx = MiddleLayerContext(
            dna=dna,
            current_degree=current_degree,
            sa_chord_sequence=sa_seq,
            sa_chord_idx=sa_idx,
            divergence_rate=divergence_rate,
            sa_transition_matrix=sa_matrix_tuple,
        )
        result = strategy.tick(ctx)
        with self._lock:
            self._current_degree = result.degree
            self._pad_dirty = True
            self._sa_chord_idx = result.sa_chord_idx
        # コード度数変更 → 全シンセのpitchをharm経由で即更新
        self._send_harm()

    def _generate_tidal_code(self, include_pads: bool = True) -> list[str]:
        """現在の状態からTidalコード行リストを生成する。

        現在の _lower_strategy に委譲する。
        デフォルトは EuclidTemplateStrategy（euclid/struct + Gaussianノイズ）。
        set_lower_strategy() で実行時に切り替え可能。
        """
        with self._lock:
            scale = self._clock.current_scale
            dna = dict(self._scene_dna)
            seed = self._seed
            degree = self._current_degree
            arc_phase = self._arc_phase
            strategy = self._lower_strategy
            density_override = self._density_override
            prev_voicing = list(self._prev_voicing)  # Phase 2: コピーして渡す

        if not dna:
            return []

        # density_override が設定されていれば DNA の onset_density_target を上書き
        if density_override is not None:
            dna["onset_density_target"] = density_override

        ctx = LowerLayerContext(
            scale=scale,
            dna=dna,
            seed=seed,
            current_degree=degree,
            arc_phase=arc_phase,
            synth_a=self._SYNTH_A,
            synth_b=self._SYNTH_B,
            prev_voicing=tuple(prev_voicing),  # Phase 2
        )
        lines = strategy.generate(ctx, include_pads)

        # Phase 2: 生成後、今回のコードボイシングを保存（次 tick のベースに使う）
        new_chord = _build_diatonic_voicing(degree, scale, octave=3)
        with self._lock:
            self._prev_voicing = new_chord

        return lines

    # ── 生成ループ ───────────────────────────────────────────────────────────

    def _generation_loop(self) -> None:
        """バックグラウンドでTidalコードを生成し続けるメインループ。

        各tick (~2秒) でLowerLayerが実行される。
        MiddleLayer: BPM連動の和声リズム（harmonic_bars × 1小節の秒数）
        UpperLayer:  30tick毎 (~60秒)
        """
        tick_interval = 2.0
        upper_every = 30
        self._upper_every = upper_every
        tick = 0

        # 最初のパッド送信は確実に行う
        self._pad_dirty = True

        while self._running:
            time.sleep(tick_interval)
            if not self._running:
                break

            # サイクル境界処理（スケール変更の適用）
            scale_changed = self._clock.on_cycle_boundary()
            if scale_changed:
                with self._lock:
                    self._pad_dirty = True

            # UpperLayer チェック
            with self._lock:
                self._upper_tick_counter = tick % upper_every
            if tick > 0 and tick % upper_every == 0:
                self._upper_layer_tick()

            # MiddleLayer: BPM連動の和声リズムでコード度数を変える
            # 1小節 = (60秒/BPM) × 4拍、harmonic_bars 小節ごとに変更
            # SA活動量が低い（ドローン的）ほど sa_activity_multiplier が大きくなり
            # コード変更間隔がさらに長くなる
            with self._lock:
                bpm = self._bpm
                harmonic_bars = self._harmonic_bars
                sa_multiplier = self._sa_activity_multiplier
            bar_secs = (60.0 / bpm) * 4
            chord_interval = bar_secs * harmonic_bars * sa_multiplier
            self._secs_since_chord_change += tick_interval
            if self._secs_since_chord_change >= chord_interval:
                self._secs_since_chord_change = 0.0
                self._middle_layer_tick()

            # メロディアーク更新（フレーズ輪郭の三角波）
            # SA活動量が低いほど arc_speed を下げ、オクターブシフトも緩やかにする
            with self._lock:
                arc_speed = self._arc_speed / sa_multiplier
            new_arc = self._arc_phase + self._arc_direction * arc_speed
            self._arc_phase = max(0.0, min(1.0, new_arc))
            if self._arc_phase >= 1.0:
                self._arc_direction = -1
            elif self._arc_phase <= 0.0:
                self._arc_direction = 1

            # Tidal未起動なら送信スキップ
            if not self._tidal.is_running:
                tick += 1
                continue

            # LowerLayer: Tidalコード生成・送信
            with self._lock:
                include_pads = self._pad_dirty
                self._pad_dirty = False

            lines = self._generate_tidal_code(include_pads=include_pads)
            if lines:
                self._tidal.evaluate("\n".join(lines))
                with self._lock:
                    self._last_tidal_lines = list(lines)
                log.debug(
                    f"Tidal 送信 (tick={tick}, pads={include_pads}, "
                    f"arc={self._arc_phase:.2f}):\n" + "\n".join(lines)
                )

            # UI向けに現在状態をブロードキャスト（スレッドセーフ）
            if self._broadcast is not None and self._loop is not None:
                try:
                    state = self.get_state()
                    asyncio.run_coroutine_threadsafe(
                        self._broadcast(state),
                        self._loop,
                    )
                except Exception as e:
                    log.debug("broadcast エラー（無視）: %s", e)

            tick += 1
