"""Multi-timescale Music Generator
====================================
3層構造でTidalコードを連続生成するアルゴリズム音楽生成エンジン。

UpperLayer  (~60-120秒): Markovによるスケール遷移
MiddleLayer (~4-8秒):   GravityMatrixによるコード度数選択
LowerLayer  (~1-2秒):   TidalコードをSCへ送信

SCENE DNAがシーンごとの音楽的性格を定義し、
Sonic Anatomyデータが初期スケール・音程・リズムをシードとして提供する。
"""

import logging
import math
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

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

    def __init__(self, tidal: TidalController) -> None:
        self._tidal = tidal
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

    # ── 公開API ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """生成ループを開始する（既に実行中なら無視）。"""
        if self._running:
            return
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

        with self._lock:
            self._seed = record
            self._pad_dirty = True
            self._bpm = max(40.0, record.bpm)  # 下限40BPMでガード
            self._sa_chord_sequence = sa_seq
            self._sa_chord_idx = 0

        mode = (
            record.key_mode if record.key_mode in SCALE_INTERVALS else "minor"
        )
        new_scale = Scale(root=record.key_root, mode=mode)
        self._clock.request_scale_change(new_scale)
        log.info(
            f"SA シード設定: bpm={record.bpm:.1f} "
            f"key={record.key_root}/{record.key_mode} "
            f"onset={record.onset_density:.2f} "
            f"chord_seq={sa_seq}"
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

    # ── 内部レイヤー処理 ────────────────────────────────────────────────────

    def _upper_layer_tick(self) -> None:
        """UpperLayer: Markovによるスケール遷移チェック（~60-120秒周期）。

        pitch_class_distribution が利用可能なら親和度で重み付け選択する。
        """
        with self._lock:
            dna = self._scene_dna
            seed = self._seed

        if not dna:
            return

        prob = dna.get("scale_change_prob", 0.02)
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

    def _middle_layer_tick(self) -> None:
        """MiddleLayer: Gravity+Markov+SAコード進行のブレンドで度数選択（~4-8秒）。

        3つのソースを合成して音楽的に自然かつ偶発的な度数遷移を生成する：
          - GravityMatrix (40%): シーン性格（tonic/dominant）
          - Markov遷移  (60%): 現在度数からの音楽的自然遷移
          - SAコード進行 (+40%ブースト): 元楽曲の引力点
        """
        with self._lock:
            dna = self._scene_dna
            current_degree = self._current_degree
            sa_seq = list(self._sa_chord_sequence)
            sa_idx = self._sa_chord_idx

        if not dna:
            return

        all_degrees = ["I", "II", "III", "IV", "V", "VI", "VII"]

        # Gravity Matrixの重み（全7度数に対して分布、0.0で欠如）
        gravity_type = dna.get("chord_gravity", "tonic")
        gravity_map = GRAVITY.get(gravity_type, GRAVITY["tonic"])
        gravity_raw = {d: gravity_map.get(d, 0.0) for d in all_degrees}

        # Markov遷移重み（現在の度数からの音楽的自然遷移）
        markov_map = DEGREE_TRANSITIONS.get(current_degree, {})
        markov_raw = {d: markov_map.get(d, 0.0) for d in all_degrees}

        # 正規化
        g_total = sum(gravity_raw.values())
        m_total = sum(markov_raw.values())
        uniform = 1.0 / len(all_degrees)
        gw = (
            {d: gravity_raw[d] / g_total for d in all_degrees}
            if g_total > 0 else {d: uniform for d in all_degrees}
        )
        mw = (
            {d: markov_raw[d] / m_total for d in all_degrees}
            if m_total > 0 else {d: uniform for d in all_degrees}
        )

        # 混合重み（Gravity 40% + Markov 60%）
        blended = {d: 0.4 * gw[d] + 0.6 * mw[d] for d in all_degrees}

        # SAコード進行の次の度数に +40% ブースト（元楽曲の引力点として使用）
        sa_degree: str | None = None
        if sa_seq:
            sa_degree = sa_seq[sa_idx % len(sa_seq)]
            if sa_degree in blended:
                blended[sa_degree] *= 1.4

        # 正規化して確率的選択
        total = sum(blended.values())
        weights = [blended[d] / total for d in all_degrees]
        chosen = random.choices(all_degrees, weights=weights, k=1)[0]

        new_idx = (sa_idx + 1) % len(sa_seq) if sa_seq else 0
        with self._lock:
            self._current_degree = chosen
            self._pad_dirty = True
            self._sa_chord_idx = new_idx
        log.debug(
            f"MiddleLayer: コード度数 → {chosen} "
            f"(SA引力点={sa_degree or 'none'}, Markov元={current_degree})"
        )

    # ── Tidalコード生成 ──────────────────────────────────────────────────────

    def _build_rhythmic_lines(
        self,
        scale: Scale,
        density: float,
        degrade: float,
        amp_main: float,
        freq_str: str,
        tidal_slow: int = 4,
        rhythm_str: Optional[str] = None,
    ) -> list[str]:
        """d1 / d2 のリズム系Tidalコードを生成する。

        SAリズムパターンがある場合は struct を使い、ない場合は euclid を使う。
        d2 の slow はシーンの tidal_slow に連動する（固定値 3 を廃止）。
        """
        hits, steps = _select_euclid(density)
        # d2 は d5 の半分速度（シーン連動）
        d2_slow = max(1, tidal_slow // 2)
        d2_degrade = min(degrade + 0.15, 0.92)
        d2_amp = amp_main * 0.6

        # SAリズムパターン → struct、なければ euclid
        if rhythm_str:
            d1_rhythm = f"struct {rhythm_str}"
        else:
            d1_rhythm = f"euclid {hits} {steps}"

        return [
            f'd1 $ degradeBy {degrade:.2f} $ {d1_rhythm} '
            f'$ s "{self._SYNTH_A}" # freq {freq_str} # amp {amp_main:.2f}',
            f'd2 $ slow {d2_slow} $ degradeBy {d2_degrade:.2f} '
            f'$ s "{self._SYNTH_B}" # freq {freq_str} # amp {d2_amp:.2f}',
        ]

    def _build_pad_lines(
        self,
        tidal_slow: int,
        amp_pad: float,
        chord_str: str,
        onset_density: float = 0.4,
    ) -> list[str]:
        """d5 / d6 のスロー系（パッド）Tidalコードを生成する。

        d6 の degradeBy を onset_density に連動させる。
        密なシーン（density 高）→ 音符を間引く量を減らす（密度を維持）
        疎なシーン（density 低）→ 音符を間引く量を増やす（余白を増やす）
        """
        very_slow = tidal_slow * 2
        d6_amp = amp_pad * 0.7
        # density=0 → degrade=0.8（多く間引く）、density=1 → degrade=0.4（あまり間引かない）
        d6_degrade = max(0.2, min(0.8, 0.8 - onset_density * 0.4))

        return [
            f'd5 $ slow {tidal_slow} $ s "{self._SYNTH_A}" '
            f'# freq {chord_str} # amp {amp_pad:.2f}',
            f'd6 $ degradeBy {d6_degrade:.2f} $ slow {very_slow} '
            f'$ s "{self._SYNTH_B}" # freq {chord_str} # amp {d6_amp:.2f}',
        ]

    def _generate_tidal_code(self, include_pads: bool = True) -> list[str]:
        """現在の状態からTidalコード行リストを生成する。

        ScaleQuantizerで全音程をスケール内に補正する。
        Gaussianノイズで amp/degrade に微変動を加え、同一SAデータでも
        毎tick異なるパターンが生成されるようにする（偶発的生成の担保）。
        """
        with self._lock:
            scale = self._clock.current_scale
            dna = dict(self._scene_dna)
            seed = self._seed
            degree = self._current_degree
            arc_phase = self._arc_phase

        if not dna:
            return []

        onset_density = (
            seed.onset_density if seed
            else dna.get("onset_density_target", 0.4)
        )
        tidal_slow = dna.get("tidal_slow", 4)

        # Gaussianノイズで微変動（σ=0.03）→ 同じSAデータでも毎tick異なる値
        amp_main = min(0.7, max(0.1,
            0.3 + onset_density * 0.4 + random.gauss(0, 0.03)
        ))
        amp_pad = min(0.4, max(0.05,
            0.1 + onset_density * 0.2 + random.gauss(0, 0.02)
        ))
        degrade = max(0.05, min(0.95,
            0.9 - onset_density + random.gauss(0, 0.04)
        ))

        # アークフェーズに応じて d1/d2 のオクターブを変える（旋律輪郭制御）
        melody_octave = 5 if arc_phase > 0.6 else 4

        # 音程生成（SAデータまたはフォールバック）
        if seed:
            raw_main = pitch_class_to_freqs(
                seed.pitch_class_distribution,
                scale.root, scale.sa_mode,
                top_n=3, octave=melody_octave,
            )
        else:
            root_hz = _midi_to_hz(melody_octave * 12 + scale.root_semitone)
            raw_main = [root_hz, root_hz * 1.498]  # 完全5度

        # d5/d6 パッド: ダイアトニック3和音ボイシング（根音+3度+5度）
        chord_hz = _build_diatonic_voicing(degree, scale, octave=3)

        # d1/d2 旋律: 度数シフト → ScaleQuantize
        shifted_main = _apply_degree_shift(raw_main, degree)
        quantized_main = [
            _midi_to_hz(
                quantize(_hz_to_midi(f), scale.root_semitone, scale.mode)
            )
            for f in shifted_main if f > 0
        ]

        freq_str = _freqs_to_tidal_str(quantized_main[:3])
        chord_str = _freqs_to_tidal_str(chord_hz)

        # SAリズムパターン → Tidal struct 文字列（なければ euclid にフォールバック）
        rhythm_str: Optional[str] = None
        if seed and seed.rhythm_pattern:
            rhythm_str = _rhythm_pattern_to_tidal(seed.rhythm_pattern)

        lines = self._build_rhythmic_lines(
            scale, onset_density, degrade, amp_main, freq_str,
            tidal_slow=tidal_slow,
            rhythm_str=rhythm_str,
        )
        if include_pads:
            lines += self._build_pad_lines(
                tidal_slow, amp_pad, chord_str,
                onset_density=onset_density,
            )
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
            if tick > 0 and tick % upper_every == 0:
                self._upper_layer_tick()

            # MiddleLayer: BPM連動の和声リズムでコード度数を変える
            # 1小節 = (60秒/BPM) × 4拍、harmonic_bars 小節ごとに変更
            with self._lock:
                bpm = self._bpm
                harmonic_bars = self._harmonic_bars
            bar_secs = (60.0 / bpm) * 4
            chord_interval = bar_secs * harmonic_bars
            self._secs_since_chord_change += tick_interval
            if self._secs_since_chord_change >= chord_interval:
                self._secs_since_chord_change = 0.0
                self._middle_layer_tick()

            # メロディアーク更新（フレーズ輪郭の三角波）
            with self._lock:
                arc_speed = self._arc_speed
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
                log.debug(
                    f"Tidal 送信 (tick={tick}, pads={include_pads}, "
                    f"arc={self._arc_phase:.2f}):\n" + "\n".join(lines)
                )

            tick += 1
