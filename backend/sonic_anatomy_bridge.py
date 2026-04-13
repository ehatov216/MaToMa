"""
Sonic Anatomy → MaToMa ブリッジ
================================
Sonic Anatomy の分析データ（BPM・キー・リズム密度・和音進行）を
TidalCycles パターンコードに変換して MaToMa の生成シードとして使う。

データフロー:
  SA の SQLite DB → load_record() → SonicAnatomyRecord
  → generate_tidal_seed() → TidalSeed
  → seed_to_dict() → WebSocket JSON → ブラウザ
  → bridge.py が tidal.evaluate(code) / tidal.set_tempo(bpm) に渡す

【Sonic Anatomy DB スキーマ（利用フィールド）】
  bpm                    : float  — テンポ（70〜155程度）
  key_root               : str    — キーのルート音 ("C", "Eb", "Bb" など)
  key_mode               : str    — "major" | "minor"
  onset_density          : float  — リズム密度（0.0〜1.2程度）
  rhythm_pattern         : JSON   — 16ステップ 0/1 配列
  pitch_class_distribution : JSON — 12要素 float 配列（ピッチクラス確率）
  chord_progression      : JSON   — [{roman: str, duration_beats: float}, ...]
"""

import json
import logging
import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tidal_patterns import (
    SYNTH_CHAOS, SYNTH_FM, SYNTH_GRAIN, SYNTH_KLANK, SYNTH_SPRING,
    make_melody_pattern,
)

log = logging.getLogger(__name__)

SA_DB_PATH = (
    "/Users/yusuke.kawakami/dev/Sonic Anatomy/projects/sonic_anatomy_catalog.db"
)

# ── ノート変換テーブル ─────────────────────────────────────────────────

# pitch class インデックス（0=C, 1=C#, ..., 11=B）→ Tidal ノート名
PITCH_CLASSES: list[str] = [
    "c", "cs", "d", "ds", "e", "f", "fs", "g", "gs", "a", "as", "b",
]

# キーのルート音 → 半音数
ROOT_TO_SEMITONE: dict[str, int] = {
    "C": 0, "Cs": 1, "Db": 1, "D": 2, "Ds": 3, "Eb": 3,
    "E": 4, "F": 5, "Fs": 6, "Gb": 6, "G": 7, "Gs": 8,
    "Ab": 8, "A": 9, "As": 10, "Bb": 10, "B": 11,
}

# メジャー・マイナースケールの半音インターバル（1度基準）
MAJOR_INTERVALS: list[int] = [0, 2, 4, 5, 7, 9, 11]
MINOR_INTERVALS: list[int] = [0, 2, 3, 5, 7, 8, 10]

# ローマ数字 → スケール度数（1-indexed）、長いものを先にして誤マッチを防ぐ
ROMAN_DEGREE: dict[str, int] = {
    "VII": 7, "VI": 6, "IV": 4, "V": 5, "III": 3, "II": 2, "I": 1,
}


# ── データクラス ──────────────────────────────────────────────────────

@dataclass
class SonicAnatomyRecord:
    """Sonic Anatomy の1トラック分の分析データ。"""
    track_id: str
    bpm: float
    key_root: str
    key_mode: str             # "major" | "minor"
    onset_density: float
    rhythm_pattern: list[int]           # 16要素 0/1
    pitch_class_distribution: list[float]  # 12要素、合計≈1
    chord_progression: list[dict]       # [{roman, duration_beats}, ...]


@dataclass
class TidalSeed:
    """generate_tidal_seed() の戻り値。Tidal に送るコード群。"""
    bpm: float
    rhythm_lines: list[str]   # d1〜d3
    harmony_lines: list[str]  # d5〜d6（スロー・ハーモニック）
    melody_lines: list[str]   # d8（Phase 1: matoma_lead メロディー）
    notes_str: str            # UI表示用ノート名列（例: "eb3 g3 bb3"）
    source_track_id: str


# ── DB 読み込み ───────────────────────────────────────────────────────

def load_record(
    track_id: Optional[str] = None,
) -> Optional[SonicAnatomyRecord]:
    """
    Sonic Anatomy の分析レコードを1件返す。

    Args:
        track_id: 指定した場合はそのIDのレコードを取得。
                  None のときは有効データを持つレコードをランダムに1件選ぶ。
    Returns:
        SonicAnatomyRecord、またはDBが見つからない/データなし時は None。
    """
    db_path = Path(SA_DB_PATH)
    if not db_path.exists():
        log.error(f"Sonic Anatomy DB が見つかりません: {db_path}")
        return None

    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            if track_id:
                row = conn.execute(
                    "SELECT * FROM analysis_records WHERE track_id = ?",
                    (track_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    """SELECT * FROM analysis_records
                       WHERE bpm IS NOT NULL
                         AND onset_density IS NOT NULL
                         AND pitch_class_distribution IS NOT NULL
                       ORDER BY RANDOM()
                       LIMIT 1""",
                ).fetchone()

            if row is None:
                log.warning("Sonic Anatomy: 対象レコードが見つかりません")
                return None

            return SonicAnatomyRecord(
                track_id=str(row["track_id"]),
                bpm=float(row["bpm"] or 120.0),
                key_root=str(row["key_root"] or "C"),
                key_mode=str(row["key_mode"] or "major"),
                onset_density=float(row["onset_density"] or 0.5),
                rhythm_pattern=_parse_json_list(
                    row["rhythm_pattern"], [1] * 16
                ),
                pitch_class_distribution=_parse_json_list(
                    row["pitch_class_distribution"], [1 / 12] * 12
                ),
                chord_progression=_parse_json_list(
                    row["chord_progression"], []
                ),
            )
    except sqlite3.Error as exc:
        log.error(f"Sonic Anatomy DB エラー: {exc}")
        return None


def list_records(limit: int = 50) -> list[dict]:
    """
    SA DB のトラック一覧をカタログUI向けに返す。

    Returns:
        [{"track_id": str, "bpm": float, "key": str, "density": float}, ...]
        DB が見つからない or エラー時は空リスト。
    """
    db_path = Path(SA_DB_PATH)
    if not db_path.exists():
        log.error(f"Sonic Anatomy DB が見つかりません: {db_path}")
        return []
    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT track_id, bpm, key_root, key_mode, onset_density
                   FROM analysis_records
                   WHERE bpm IS NOT NULL AND onset_density IS NOT NULL
                   ORDER BY track_id
                   LIMIT ?""",
                (limit,),
            ).fetchall()
            return [
                {
                    "track_id": str(r["track_id"]),
                    "bpm": round(float(r["bpm"] or 0), 1),
                    "key": f"{r['key_root'] or '?'} {r['key_mode'] or '?'}",
                    "density": round(float(r["onset_density"] or 0), 2),
                }
                for r in rows
            ]
    except sqlite3.Error as exc:
        log.error(f"Sonic Anatomy カタログ取得エラー: {exc}")
        return []


def _parse_json_list(raw: Optional[str], default: list) -> list:
    """SQLite の JSON 文字列を list にパースする。失敗時は default。"""
    if not raw:
        return default
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else default
    except json.JSONDecodeError:
        return default


# ── パターン変換関数 ──────────────────────────────────────────────────

def onset_density_to_degrade(density: float) -> float:
    """
    onset_density → Tidal degradeBy 値（0.1〜0.9）。

    密度が高い（音が多い）ほど degradeBy を小さく（欠落を少なく）する。
    密度が低い（音が少ない）ほど degradeBy を大きく（欠落を多く）する。
    """
    # density を [0, 1.2] → [0, 1] にクランプして線形変換
    clamped = min(1.0, density / 1.2)
    return round(0.9 - clamped * 0.8, 2)  # 0.9（疎）→ 0.1（密）


def rhythm_pattern_to_struct(pattern: list[int]) -> str:
    """
    16ステップの 0/1 リスト → Tidal struct 文字列。

    全ステップが同じ値（全1または全0）のときは空文字を返す
    （SA DB の rhythm_pattern が trivial な場合の回避策）。

    Returns:
        'struct "x ~ ~ x ..."' または "" (trivial の場合)
    """
    if all(s == 1 for s in pattern) or all(s == 0 for s in pattern):
        return ""
    steps = ["x" if s else "~" for s in pattern]
    return f'struct "{" ".join(steps)}"'


def pitch_class_to_freqs(
    distribution: list[float],
    key_root: str,
    key_mode: str,
    top_n: int = 3,
    octave: int = 4,
) -> list[float]:
    """
    12要素の pitch_class_distribution → スケール音上位 top_n の周波数リスト。

    キーのスケール音に含まれるピッチクラスを優先し、
    分布値が高いものから top_n 個を選ぶ。
    """
    root_semi = ROOT_TO_SEMITONE.get(key_root, 0)
    intervals = MINOR_INTERVALS if key_mode == "minor" else MAJOR_INTERVALS
    scale_pcs = {(root_semi + iv) % 12 for iv in intervals}

    # スケール音のみスコアを付ける（スケール外は 0）
    scored = sorted(
        ((i, distribution[i] if i in scale_pcs else 0.0) for i in range(12)),
        key=lambda x: x[1],
        reverse=True,
    )
    top_pcs = [pc for pc, val in scored[:top_n] if val > 0.0]

    # スケール内に有効なピッチがなければフォールバック
    if not top_pcs:
        top_pcs = [pc for pc, _ in scored[:top_n]]

    return [_pc_to_freq(pc, octave) for pc in sorted(top_pcs)]


def chord_progression_to_freqs(
    chords: list[dict],
    key_root: str,
    key_mode: str,
    octave: int = 3,
    max_chords: int = 6,
) -> list[float]:
    """
    chord_progression リスト → 各コードのルート音周波数リスト。

    重複するローマ数字を除外し、最大 max_chords 件に制限する。
    SA DB では同じ進行が繰り返し記録されることがあるため、
    unique なコードのみ使う。

    Args:
        chords: [{"roman": "IIImaj", "duration_beats": 2.57}, ...]
    Returns:
        周波数リスト（Hz）。例: [311.1, 185.0, 233.1]
    """
    if not chords:
        return [_pc_to_freq(ROOT_TO_SEMITONE.get(key_root, 0), octave)]

    root_semi = ROOT_TO_SEMITONE.get(key_root, 0)
    intervals = MINOR_INTERVALS if key_mode == "minor" else MAJOR_INTERVALS

    freqs: list[float] = []
    seen_semis: set[int] = set()

    for chord in chords:
        if len(freqs) >= max_chords:
            break
        roman_str = chord.get("roman", "I")
        semi = _roman_to_semitone(roman_str, root_semi, intervals)
        if semi is not None and semi not in seen_semis:
            freqs.append(_pc_to_freq(semi, octave))
            seen_semis.add(semi)

    return freqs if freqs else [_pc_to_freq(root_semi, octave)]


def _roman_to_semitone(
    roman_str: str, root_semi: int, intervals: list[int]
) -> Optional[int]:
    """
    ローマ数字文字列（"IIImaj", "Vmin" など） → 絶対半音数。

    長いローマ数字（VII, III, etc.）から順に試合してマッチさせる。
    """
    upper = roman_str.upper()
    for roman, degree in ROMAN_DEGREE.items():
        if upper.startswith(roman):
            return (root_semi + intervals[degree - 1]) % 12
    return None


def _pc_to_freq(pc: int, octave: int) -> float:
    """ピッチクラス + オクターブ → Hz（平均律）。C4 = 261.63 Hz。"""
    midi = (octave + 1) * 12 + pc  # C4 = MIDI 60 → (4+1)*12+0 = 60 ✓
    return round(440.0 * (2.0 ** ((midi - 69) / 12)), 2)


def _freqs_to_tidal(freqs: list[float]) -> str:
    """
    周波数リスト → Tidal angle-bracket cycle pattern 文字列。

    例: [311.1, 185.0] → '"<311.1 185.0>"'
    Tidal では <> で囲んだ値を1サイクルに1つずつ順番に使う。
    """
    return '"<' + " ".join(f"{f:.1f}" for f in freqs) + '>"'


def _pc_from_freq(freq: float) -> int:
    """周波数 → pitch class (0-11)。ノート名表示用。"""
    midi = round(69 + 12 * math.log2(max(freq, 8.0) / 440.0))
    return midi % 12


# ── メイン API ───────────────────────────────────────────────────────

def generate_tidal_seed(record: SonicAnatomyRecord) -> TidalSeed:
    """
    SonicAnatomyRecord → TidalSeed。

    【リズムトラック選択ロジック（onset_density ベース）】
      density > 0.7 : FM × Chaos （Autechre 的・高密度）
      density < 0.3 : Spring × Grain（OPN 的・疎）
      それ以外       : Klank × FM  （Alva Noto 的・数学的）

    【rhythm_pattern の使い方】
      trivial（全1 or 全0）→ Euclidean で代替
      non-trivial → struct で直接適用
    """
    degrade = onset_density_to_degrade(record.onset_density)
    struct_pat = rhythm_pattern_to_struct(record.rhythm_pattern)

    # シンセ選択
    if record.onset_density > 0.7:
        primary_synth, sub_synth = SYNTH_FM, SYNTH_CHAOS
    elif record.onset_density < 0.3:
        primary_synth, sub_synth = SYNTH_SPRING, SYNTH_GRAIN
    else:
        primary_synth, sub_synth = SYNTH_KLANK, SYNTH_FM

    # ハーモニー：コード進行 + ピッチクラス分布から周波数を算出
    # （d1-d3 の freq にも使うため先に計算する）
    chord_freqs = chord_progression_to_freqs(
        record.chord_progression, record.key_root, record.key_mode, octave=3
    )
    # メロディー用：スケール音上位4音（オクターブ4）
    melody_freqs = pitch_class_to_freqs(
        record.pitch_class_distribution, record.key_root, record.key_mode,
        top_n=4, octave=4,
    )
    chord_freq_pat = _freqs_to_tidal(chord_freqs)

    # d1: メインリズム（cF コントロールチャンネル経由で ThreeLayerController と連動）
    ref_freq = f'{chord_freqs[0]:.1f}' if chord_freqs else '130.8'
    if struct_pat:
        d1 = (
            f'd1 $ degradeBy (cF "rhythmic_degrade" {degrade:.2f}) $ {struct_pat}'
            f' $ s "{primary_synth}"'
            f' # amp (cF "rhythmic_amp" 0.5)'
            f' # freq (cF "rhythmic_freq" {ref_freq})'
        )
    else:
        hits = max(1, min(7, round(record.onset_density * 8)))
        d1 = (
            f'd1 $ degradeBy (cF "rhythmic_degrade" {degrade:.2f}) $ euclid {hits} 8'
            f' $ s "{primary_synth}"'
            f' # amp (cF "rhythmic_amp" 0.5)'
            f' # freq (cF "rhythmic_freq" {ref_freq})'
        )

    # d2: サブリズム（7ステップ Euclidean — 4/4 と位相がずれる）
    hits2 = max(1, min(5, round(record.onset_density * 6) + 1))
    d2 = (
        f'd2 $ euclid {hits2} 7 $ s "{sub_synth}"'
        f' # amp (cF "rhythmic_amp" 0.35)'
        f' # freq {chord_freq_pat}'
    )

    # d3: スパース呼吸層（SPRING をゆっくり、degrade に +0.2 上乗せ）
    d3 = (
        f'd3 $ degradeBy (cF "rhythmic_degrade" {degrade:.2f} + 0.2) $ slow 3'
        f' $ s "{SYNTH_SPRING}"'
        f' # amp 0.28'
        f' # freq {chord_freq_pat}'
    )

    rhythm_lines = [d1, d2, d3]

    harmony_lines = [
        (
            f'd5 $ slow 8 $ s "{SYNTH_SPRING}"'
            f' # freq {chord_freq_pat} # amp 0.35'
        ),
        (
            f'd6 $ degradeBy 0.4 $ slow 12 $ s "{SYNTH_GRAIN}"'
            f' # note (cF 60 "melody_note") # amp 0.25'
        ),
    ]

    # Phase 1: メロディーライン（d8 に matoma_lead でスケール音を演奏）
    # BPMが高い曲は slow 2 を入れてメロディーを落ち着かせる
    melody_slow = 2.0 if record.bpm > 120 else 1.0
    melody_lines = [
        make_melody_pattern(track=8, freqs=melody_freqs, slow_factor=melody_slow),
    ]

    # UI表示用ノート名（コード進行のルート音を使う）
    notes_str = " ".join(
        f"{PITCH_CLASSES[_pc_from_freq(f)]}{3}" for f in chord_freqs[:4]
    )

    return TidalSeed(
        bpm=record.bpm,
        rhythm_lines=rhythm_lines,
        harmony_lines=harmony_lines,
        melody_lines=melody_lines,
        notes_str=notes_str,
        source_track_id=record.track_id,
    )


def seed_to_dict(seed: TidalSeed) -> dict:
    """TidalSeed → WebSocket 送信用 JSON-serializable dict。"""
    return {
        "type": "sonic_anatomy_seed",
        "track_id": seed.source_track_id,
        "bpm": seed.bpm,
        "rhythm_lines": seed.rhythm_lines,
        "harmony_lines": seed.harmony_lines,
        "melody_lines": seed.melody_lines,
        "notes": seed.notes_str,
        "all_lines": seed.rhythm_lines + seed.harmony_lines + seed.melody_lines,
    }
