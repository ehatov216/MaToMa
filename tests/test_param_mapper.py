"""
param_mapper.py のテスト
========================
音楽的変換ユーティリティ関数（lerp / energy_to_breath_scale / clamp）を検証する。
"""

import pytest
from backend.param_mapper import (
    lerp,
    energy_to_breath_scale,
    clamp,
)


# ── lerp ─────────────────────────────────────────────────────────────────────

class TestLerp:
    def test_t_zero(self):
        assert lerp(10.0, 20.0, 0.0) == pytest.approx(10.0)

    def test_t_one(self):
        assert lerp(10.0, 20.0, 1.0) == pytest.approx(20.0)

    def test_t_half(self):
        assert lerp(0.0, 1.0, 0.5) == pytest.approx(0.5)

    def test_t_clamps_above_one(self):
        assert lerp(0.0, 10.0, 2.0) == pytest.approx(10.0)

    def test_t_clamps_below_zero(self):
        assert lerp(0.0, 10.0, -1.0) == pytest.approx(0.0)

    def test_negative_range(self):
        assert lerp(-10.0, 10.0, 0.5) == pytest.approx(0.0)

    def test_identity_when_a_equals_b(self):
        assert lerp(5.0, 5.0, 0.7) == pytest.approx(5.0)


# ── energy_to_breath_scale ───────────────────────────────────────────────────

class TestEnergyToBreathScale:
    def test_energy_zero(self):
        """ENERGY=0.0 → 0.6倍（最も遅い）"""
        assert energy_to_breath_scale(0.0) == pytest.approx(0.6)

    def test_energy_half(self):
        """ENERGY=0.5 → 1.0倍（中立）"""
        assert energy_to_breath_scale(0.5) == pytest.approx(1.0)

    def test_energy_one(self):
        """ENERGY=1.0 → 1.6倍（最も速い）"""
        assert energy_to_breath_scale(1.0) == pytest.approx(1.6)

    def test_energy_quarter(self):
        """0〜0.5区間: lerp(0.6, 1.0, 0.25*2) = 0.8"""
        assert energy_to_breath_scale(0.25) == pytest.approx(0.8)

    def test_energy_three_quarter(self):
        """0.5〜1.0区間: lerp(1.0, 1.6, (0.75-0.5)*2) = 1.3"""
        assert energy_to_breath_scale(0.75) == pytest.approx(1.3)

    def test_clamps_above_one(self):
        assert energy_to_breath_scale(2.0) == pytest.approx(1.6)

    def test_clamps_below_zero(self):
        assert energy_to_breath_scale(-1.0) == pytest.approx(0.6)

    def test_result_always_positive(self):
        for e in [0.0, 0.1, 0.3, 0.5, 0.7, 1.0]:
            assert energy_to_breath_scale(e) > 0


# ── clamp ────────────────────────────────────────────────────────────────────

class TestClamp:
    def test_within_range(self):
        assert clamp(0.5, 0.0, 1.0) == pytest.approx(0.5)

    def test_below_lo(self):
        assert clamp(-1.0, 0.0, 1.0) == pytest.approx(0.0)

    def test_above_hi(self):
        assert clamp(2.0, 0.0, 1.0) == pytest.approx(1.0)

    def test_at_lo_boundary(self):
        assert clamp(0.0, 0.0, 1.0) == pytest.approx(0.0)

    def test_at_hi_boundary(self):
        assert clamp(1.0, 0.0, 1.0) == pytest.approx(1.0)

    def test_float_conversion(self):
        """int値も正しくfloatとして扱われるか"""
        assert clamp(5, 0, 10) == pytest.approx(5.0)
