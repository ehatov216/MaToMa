"""
tidal_patterns.py のテスト
===========================
Tidal パターン生成関数の出力形式と値を検証する。
"""

import pytest
from backend.tidal_patterns import (
    tempo_to_cps,
    make_tempo_code,
    make_euclidean,
    make_fibonacci_pattern,
    make_phase_trio,
    make_mathematical_grid,
    make_probabilistic,
    make_sparse_breathing,
    get_preset,
    hush_all,
    PRESETS,
    ALL_SYNTHS,
    SYNTH_KLANK,
    SYNTH_FM,
    SYNTH_SPRING,
    SYNTH_CHAOS,
    SYNTH_GRAIN,
    FIBONACCI,
)


# ── 定数 ──────────────────────────────────────────────────────────────────────

class TestConstants:
    def test_all_synths_has_six_entries(self):
        assert len(ALL_SYNTHS) == 6

    def test_all_synths_contains_expected(self):
        assert SYNTH_KLANK in ALL_SYNTHS
        assert SYNTH_FM in ALL_SYNTHS
        assert SYNTH_SPRING in ALL_SYNTHS
        assert SYNTH_CHAOS in ALL_SYNTHS
        assert SYNTH_GRAIN in ALL_SYNTHS
        assert "matoma_lead" in ALL_SYNTHS

    def test_fibonacci_starts_correctly(self):
        assert FIBONACCI[:5] == [1, 1, 2, 3, 5]

    def test_fibonacci_is_monotonically_increasing_after_second(self):
        for i in range(2, len(FIBONACCI)):
            assert FIBONACCI[i] == FIBONACCI[i - 1] + FIBONACCI[i - 2]


# ── tempo_to_cps ───────────────────────────────────────────────────────────────

class TestTempoToCps:
    def test_120bpm_4beats(self):
        # 120 / 60 / 4 = 0.5
        assert tempo_to_cps(120.0) == pytest.approx(0.5)

    def test_60bpm_4beats(self):
        # 60 / 60 / 4 = 0.25
        assert tempo_to_cps(60.0) == pytest.approx(0.25)

    def test_custom_beats_per_cycle(self):
        # 120 / 60 / 1 = 2.0
        assert tempo_to_cps(120.0, beats_per_cycle=1) == pytest.approx(2.0)

    def test_result_is_positive(self):
        assert tempo_to_cps(80.0) > 0


# ── make_tempo_code ────────────────────────────────────────────────────────────

class TestMakeTempoCode:
    def test_contains_setcps(self):
        code = make_tempo_code(120.0)
        assert "setcps" in code

    def test_contains_bpm_comment(self):
        code = make_tempo_code(120.0)
        assert "120" in code

    def test_format(self):
        code = make_tempo_code(120.0)
        # "setcps X.XXXX  -- 120 BPM相当" の形式
        assert code.startswith("setcps ")
        assert "BPM" in code


# ── make_euclidean ─────────────────────────────────────────────────────────────

class TestMakeEuclidean:
    def test_contains_euclid(self):
        code = make_euclidean(1)
        assert "euclid" in code

    def test_contains_track_number(self):
        code = make_euclidean(3)
        assert "d3" in code

    def test_contains_synth_name(self):
        code = make_euclidean(1, synth=SYNTH_FM)
        assert SYNTH_FM in code

    def test_contains_hits_and_steps(self):
        code = make_euclidean(1, hits=5, steps=16)
        assert "5" in code
        assert "16" in code

    def test_contains_freq_and_amp(self):
        code = make_euclidean(1, freq=220.0, amp=0.8)
        assert "220.0" in code
        assert "0.80" in code

    def test_default_synth_is_klank(self):
        code = make_euclidean(1)
        assert SYNTH_KLANK in code

    def test_returns_string(self):
        assert isinstance(make_euclidean(1), str)


# ── make_fibonacci_pattern ────────────────────────────────────────────────────

class TestMakeFibonacciPattern:
    def test_contains_slow(self):
        code = make_fibonacci_pattern(1)
        assert "slow" in code

    def test_contains_track_number(self):
        code = make_fibonacci_pattern(2)
        assert "d2" in code

    def test_depth_controls_fib_count(self):
        code = make_fibonacci_pattern(1, depth=3)
        # 最初の3フィボナッチ数: 1 1 2
        assert '"1 1 2"' in code

    def test_depth_minimum_is_two(self):
        code = make_fibonacci_pattern(1, depth=1)
        # depth=1でも最低2つは使う
        assert '"1 1"' in code

    def test_contains_freq_and_amp(self):
        code = make_fibonacci_pattern(1, freq=330.0, amp=0.5)
        assert "330.0" in code
        assert "0.50" in code


# ── make_phase_trio ────────────────────────────────────────────────────────────

class TestMakePhaseTrio:
    def test_returns_list_of_three(self):
        result = make_phase_trio()
        assert len(result) == 3

    def test_each_line_contains_slow(self):
        result = make_phase_trio()
        for line in result:
            assert "slow" in line

    def test_tracks_appear_in_output(self):
        result = make_phase_trio(tracks=(4, 5, 6))
        assert any("d4" in line for line in result)
        assert any("d5" in line for line in result)
        assert any("d6" in line for line in result)

    def test_custom_periods(self):
        result = make_phase_trio(periods=(7, 11, 13))
        assert any("7" in line for line in result)
        assert any("11" in line for line in result)
        assert any("13" in line for line in result)

    def test_returns_strings(self):
        result = make_phase_trio()
        for line in result:
            assert isinstance(line, str)


# ── make_mathematical_grid ────────────────────────────────────────────────────

class TestMakeMathematicalGrid:
    def test_contains_subdivision(self):
        code = make_mathematical_grid(1, subdivisions=7)
        assert "7" in code

    def test_contains_track_number(self):
        code = make_mathematical_grid(2)
        assert "d2" in code

    def test_contains_freq_and_amp(self):
        code = make_mathematical_grid(1, freq=500.0, amp=0.3)
        assert "500.0" in code
        assert "0.30" in code

    def test_returns_string(self):
        assert isinstance(make_mathematical_grid(1), str)


# ── make_probabilistic ────────────────────────────────────────────────────────

class TestMakeProbabilistic:
    def test_contains_degrade_by(self):
        code = make_probabilistic(1, density=0.5)
        assert "degradeBy" in code

    def test_density_one_means_low_drop(self):
        code = make_probabilistic(1, density=1.0)
        # drop_prob = 1 - 1.0 = 0.0 → degradeBy 0.00
        assert "0.00" in code

    def test_density_zero_means_high_drop(self):
        code = make_probabilistic(1, density=0.0)
        # drop_prob = min(0.99, 1.0 - 0.0) = 0.99 → degradeBy 0.99
        assert "0.99" in code

    def test_custom_period_adds_slow(self):
        code = make_probabilistic(1, period=2.0)
        assert "slow" in code

    def test_period_one_no_slow(self):
        code = make_probabilistic(1, period=1.0)
        assert "slow" not in code

    def test_contains_track_number(self):
        code = make_probabilistic(3)
        assert "d3" in code

    def test_returns_string(self):
        assert isinstance(make_probabilistic(1), str)


# ── make_sparse_breathing ──────────────────────────────────────────────────────

class TestMakeSparseBreathing:
    def test_contains_slow(self):
        code = make_sparse_breathing(1)
        assert "slow" in code

    def test_contains_degrade_by(self):
        code = make_sparse_breathing(1)
        assert "degradeBy" in code

    def test_contains_track_number(self):
        code = make_sparse_breathing(4)
        assert "d4" in code

    def test_custom_slow_factor(self):
        code = make_sparse_breathing(1, slow_factor=32.0)
        assert "32.0" in code

    def test_returns_string(self):
        assert isinstance(make_sparse_breathing(1), str)


# ── get_preset ─────────────────────────────────────────────────────────────────

class TestGetPreset:
    def test_returns_list(self):
        result = get_preset("alva_euclidean")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_all_defined_presets_accessible(self):
        for name in PRESETS:
            result = get_preset(name)
            assert isinstance(result, list)
            assert len(result) > 0

    def test_unknown_name_returns_minimal_klank(self):
        result = get_preset("存在しないプリセット")
        expected = PRESETS["minimal_klank"]
        assert result == expected

    def test_alva_euclidean_has_euclid(self):
        result = get_preset("alva_euclidean")
        assert any("euclid" in line for line in result)

    def test_opn_sparse_has_degrade(self):
        result = get_preset("opn_sparse")
        assert any("degradeBy" in line for line in result)


# ── hush_all ──────────────────────────────────────────────────────────────────

class TestHushAll:
    def test_returns_list(self):
        assert isinstance(hush_all(), list)

    def test_contains_hush(self):
        result = hush_all()
        assert "hush" in result

    def test_default_returns_one_hush(self):
        result = hush_all()
        assert len(result) == 1

    def test_custom_num_tracks_still_returns_hush(self):
        result = hush_all(num_tracks=16)
        assert "hush" in result
