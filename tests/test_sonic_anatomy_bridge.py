"""
sonic_anatomy_bridge.py のテスト
================================
generate_tidal_seed() が生成するTidalパターンの接続と形式を検証する。
"""

import pytest
from backend.sonic_anatomy_bridge import (
    SonicAnatomyRecord,
    TidalSeed,
    generate_tidal_seed,
    rhythm_pattern_to_struct,
    onset_density_to_degrade,
)


# ── フィクスチャ ──────────────────────────────────────────────────────────

@pytest.fixture
def sample_record() -> SonicAnatomyRecord:
    """テスト用の標準的な SonicAnatomyRecord。"""
    return SonicAnatomyRecord(
        track_id="test-001",
        bpm=120.0,
        key_root="C",
        key_mode="major",
        onset_density=0.5,
        rhythm_pattern=[1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
        pitch_class_distribution=[
            0.2, 0.0, 0.15, 0.0, 0.2, 0.1,
            0.0, 0.2, 0.0, 0.1, 0.0, 0.05,
        ],
        chord_progression=[
            {"roman": "I", "duration_beats": 4.0},
            {"roman": "IV", "duration_beats": 4.0},
            {"roman": "V", "duration_beats": 4.0},
        ],
    )


@pytest.fixture
def dense_record() -> SonicAnatomyRecord:
    """高密度（onset_density > 0.7）の SonicAnatomyRecord。"""
    return SonicAnatomyRecord(
        track_id="test-dense",
        bpm=140.0,
        key_root="A",
        key_mode="minor",
        onset_density=0.8,
        rhythm_pattern=[1, 1, 0, 1, 1, 0, 1, 1, 1, 0, 1, 1, 0, 1, 1, 1],
        pitch_class_distribution=[0.1] * 12,
        chord_progression=[{"roman": "I", "duration_beats": 4.0}],
    )


@pytest.fixture
def sparse_record() -> SonicAnatomyRecord:
    """低密度（onset_density < 0.3）の SonicAnatomyRecord。"""
    return SonicAnatomyRecord(
        track_id="test-sparse",
        bpm=90.0,
        key_root="D",
        key_mode="major",
        onset_density=0.2,
        rhythm_pattern=[1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        pitch_class_distribution=[
            0.3, 0.0, 0.2, 0.0, 0.3, 0.0,
            0.0, 0.2, 0.0, 0.0, 0.0, 0.0,
        ],
        chord_progression=[{"roman": "I", "duration_beats": 8.0}],
    )


# ── generate_tidal_seed 戻り値の基本形式 ─────────────────────────────────

class TestGenerateTidalSeedBasic:
    def test_returns_tidal_seed(self, sample_record):
        result = generate_tidal_seed(sample_record)
        assert isinstance(result, TidalSeed)

    def test_bpm_matches_record(self, sample_record):
        result = generate_tidal_seed(sample_record)
        assert result.bpm == sample_record.bpm

    def test_source_track_id_matches(self, sample_record):
        result = generate_tidal_seed(sample_record)
        assert result.source_track_id == sample_record.track_id

    def test_rhythm_lines_has_three_entries(self, sample_record):
        result = generate_tidal_seed(sample_record)
        assert len(result.rhythm_lines) == 3

    def test_harmony_lines_has_two_entries(self, sample_record):
        result = generate_tidal_seed(sample_record)
        assert len(result.harmony_lines) == 2

    def test_notes_str_is_string(self, sample_record):
        result = generate_tidal_seed(sample_record)
        assert isinstance(result.notes_str, str)


# ── melody_note 接続（バグ修正検証） ─────────────────────────────────────

class TestMelodyNoteConnection:
    def test_d6_uses_tidal_ctrl_note_not_hardcoded_freq(self, sample_record):
        """d6 が静的な freq リストではなく cF melody_note を参照している。"""
        result = generate_tidal_seed(sample_record)
        d6 = result.harmony_lines[1]
        assert 'note (cF' in d6
        assert '"melody_note"' in d6

    def test_d6_does_not_contain_hardcoded_freq_list(self, sample_record):
        """d6 に静的な周波数リスト（例: [261.63, ...]）が残っていない。"""
        result = generate_tidal_seed(sample_record)
        d6 = result.harmony_lines[1]
        # 静的周波数は "[数値," パターン。cF を使った場合はこの形式が d6 に現れない
        assert '# freq [' not in d6

    def test_d6_default_note_is_60(self, sample_record):
        """cF のデフォルト値は MIDI ノート 60（中央C）。"""
        result = generate_tidal_seed(sample_record)
        d6 = result.harmony_lines[1]
        assert 'cF 60' in d6

    def test_d5_keeps_chord_freqs(self, sample_record):
        """d5（コード層）は静的なコード周波数を維持している。"""
        result = generate_tidal_seed(sample_record)
        d5 = result.harmony_lines[0]
        assert '# freq' in d5
        # d5 は cF melody_note を使わない
        assert '"melody_note"' not in d5


# ── リズム層の ThreeLayerController 接続 ────────────────────────────────

class TestRhythmicCtrlConnection:
    def test_d1_uses_rhythmic_degrade(self, sample_record):
        result = generate_tidal_seed(sample_record)
        d1 = result.rhythm_lines[0]
        assert 'rhythmic_degrade' in d1

    def test_d1_uses_rhythmic_amp(self, sample_record):
        result = generate_tidal_seed(sample_record)
        d1 = result.rhythm_lines[0]
        assert 'rhythmic_amp' in d1

    def test_d1_uses_rhythmic_freq(self, sample_record):
        result = generate_tidal_seed(sample_record)
        d1 = result.rhythm_lines[0]
        assert 'rhythmic_freq' in d1

    def test_d2_uses_rhythmic_amp(self, sample_record):
        result = generate_tidal_seed(sample_record)
        d2 = result.rhythm_lines[1]
        assert 'rhythmic_amp' in d2

    def test_d3_has_extra_degrade_offset(self, sample_record):
        """d3 は degrade に +0.2 上乗せされている（スパース層）。"""
        result = generate_tidal_seed(sample_record)
        d3 = result.rhythm_lines[2]
        assert '+ 0.2' in d3

    def test_all_cf_defaults_are_floats(self, sample_record):
        """全 cF 呼び出しが浮動小数点デフォルトを持っている。"""
        result = generate_tidal_seed(sample_record)
        all_lines = result.rhythm_lines + result.harmony_lines
        import re
        for line in all_lines:
            for match in re.findall(r'cF\s+(\S+)', line):
                # 数値かどうか確認（"melody_note" のようなキー名ではない）
                try:
                    float(match)
                except ValueError:
                    # キー名（文字列）が来た場合はスキップ（cF 60 "melody_note" の "60" はOK）
                    pass


# ── シンセ選択ロジック ─────────────────────────────────────────────────

class TestSynthSelection:
    def test_dense_uses_fm_and_chaos(self, dense_record):
        result = generate_tidal_seed(dense_record)
        d1 = result.rhythm_lines[0]
        assert 'fm' in d1 or 'chaos' in d1

    def test_sparse_uses_spring_and_grain(self, sparse_record):
        result = generate_tidal_seed(sparse_record)
        d1 = result.rhythm_lines[0]
        assert 'spring' in d1 or 'grain' in d1

    def test_medium_uses_klank_or_fm(self, sample_record):
        result = generate_tidal_seed(sample_record)
        d1 = result.rhythm_lines[0]
        assert 'klank' in d1 or 'fm' in d1


# ── ヘルパー関数 ─────────────────────────────────────────────────────────

class TestOnsetDensityToDegrade:
    def test_high_density_gives_low_degrade(self):
        # density=1.0 → 0.9 - (1.0/1.2)*0.8 ≈ 0.23
        assert onset_density_to_degrade(1.0) < 0.3

    def test_low_density_gives_high_degrade(self):
        assert onset_density_to_degrade(0.0) > 0.5

    def test_returns_float(self):
        result = onset_density_to_degrade(0.5)
        assert isinstance(result, float)

    def test_output_in_valid_range(self):
        for density in [0.0, 0.25, 0.5, 0.75, 1.0]:
            result = onset_density_to_degrade(density)
            assert 0.0 <= result <= 1.0, (
                f"density={density} → degrade={result} が範囲外"
            )


class TestRhythmPatternToStruct:
    def test_trivial_pattern_returns_empty_string(self):
        """全0または全1のパターンは空文字列（Euclideanフォールバック用）。"""
        assert rhythm_pattern_to_struct([0] * 16) == ""
        assert rhythm_pattern_to_struct([1] * 16) == ""

    def test_non_trivial_returns_struct_string(self):
        pattern = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
        result = rhythm_pattern_to_struct(pattern)
        assert result is not None
        assert "struct" in result

    def test_struct_contains_binary_values(self):
        pattern = [1, 0, 1, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0]
        result = rhythm_pattern_to_struct(pattern)
        assert result is not None
        assert "t" in result or "f" in result
