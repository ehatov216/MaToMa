"""MaToMa 笛マッピング (Param Mapper)
=====================================
3本の笛（CHAOS / DENSITY / TENSION）の値から、
SC・Python 各モジュールへの内部パラメーターを計算する。

設計書: docs/design/autonomous_evolution.md セクション6「Layer 3 詳細設計」

各関数の返り値:
    list[tuple[str, list]]  — (OSCアドレス, args リスト) のリスト
    呼び出し元はこれをループして send_osc(address, args) に渡す。

使い方:
    from param_mapper import (
        chaos_to_internal,
        density_to_internal,
        tension_to_internal,
    )

    for address, args in chaos_to_internal(0.6):
        sc_client.send_message(address, args)
"""

from __future__ import annotations



# ── 音楽的変換ユーティリティ ────────────────────────────────────────────────

def lerp(a: float, b: float, t: float) -> float:
    """線形補間 (a→b を t=0〜1 で補間)。EnergyController で使う。"""
    return a + (b - a) * max(0.0, min(1.0, t))


def energy_to_breath_scale(energy: float) -> float:
    """ENERGY → Layer A 呼吸速度倍率（設計書 セクション13 内部マッピング）。

    ENERGY=0.0 → 0.6 倍（遅い）
    ENERGY=0.5 → 1.0 倍（中立）
    ENERGY=1.0 → 1.6 倍（速い）
    """
    e = max(0.0, min(1.0, float(energy)))
    if e <= 0.5:
        return lerp(0.6, 1.0, e * 2.0)
    return lerp(1.0, 1.6, (e - 0.5) * 2.0)


def clamp(value: float, lo: float, hi: float) -> float:
    """値を [lo, hi] に収める。"""
    return max(lo, min(hi, float(value)))
