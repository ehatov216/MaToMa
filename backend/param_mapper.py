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


def chaos_to_internal(chaos: float) -> list[tuple[str, list]]:
    """CHAOS (0.0〜1.0) → 内部 OSC コマンドリスト。

    マッピング:
        feedback_amt = 0.1 + chaos * 0.55  → フィードバックが増えて音が複雑化
        shimmer      = chaos * 0.9          → シマーが増えて浮遊感が出る
        granular spray = chaos * 0.8        → グレインが散らばり音が揺れる
    """
    c = max(0.0, min(1.0, float(chaos)))
    feedback = 0.1 + c * 0.55   # 0.1〜0.65
    shimmer  = c * 0.9           # 0.0〜0.9
    spray    = c * 0.8           # 0.0〜0.8

    return [
        ("/matoma/drone/param",      ["feedback_amt", feedback]),
        ("/matoma/drone/param",      ["shimmer",       shimmer]),
        ("/matoma/granular/param",   ["spray",         spray]),
        ("/matoma/gran_synth/param", ["chaos",         c]),
    ]


def density_to_internal(density: float) -> list[tuple[str, list]]:
    """DENSITY (0.0〜1.0) → 内部 OSC コマンドリスト。

    マッピング（設計書 セクション6 笛②）:
        Granular grain数   = 10 + density * 190   grains/sec
        Rhythmic event prob = 0.1 + density * 0.7  → sequencer.set_trig_prob
        (Drone oscillator数は Synth 制御のため OSC 非対象)
    """
    d = max(0.0, min(1.0, float(density)))
    grain_density = 10.0 + d * 190.0   # 10〜200 grains/sec

    gran_synth_density = 10.0 + d * 50.0   # 10〜60 grains/sec

    return [
        ("/matoma/granular/param",   ["density", grain_density]),
        ("/matoma/gran_synth/param", ["density", gran_synth_density]),
    ]


def tension_to_internal(tension: float) -> list[tuple[str, list]]:
    """TENSION (0.0〜1.0) → 内部 OSC コマンドリスト。

    マッピング:
        freq       = 30 + tension * 90   Hz（低→高。低TENSIONは地を這う音）
        brightness = 0.2 + tension * 0.6  （暗い→明るい。RLPFのcutoff制御）
        room       = 0.7 - tension * 0.5  （広い→狭い。高TENSIONはドライ）
        granular spray = tension * 0.5    （グレインを散らして緊張感）
    """
    t = max(0.0, min(1.0, float(tension)))
    freq       = 30.0 + t * 90.0    # 30〜120 Hz
    brightness = 0.2  + t * 0.6    # 0.2〜0.8
    room       = 0.7  - t * 0.5    # 0.2〜0.7（高TENSION = ドライ）
    spray      = t * 0.5            # 0.0〜0.5

    return [
        ("/matoma/drone/param",    ["freq",       freq]),
        ("/matoma/drone/param",    ["brightness", brightness]),
        ("/matoma/drone/param",    ["room",       room]),
        ("/matoma/granular/param", ["spray",      spray]),
    ]


def mutation_prob_from_chaos(chaos: float) -> float:
    """CHAOS → TuringGene.mutation_prob の計算式（設計書 セクション6 笛①）。

    OSC コマンドではなく数値で返す（呼び出し元が gene.set_mutation_prob() に渡す）。
    """
    c = max(0.0, min(1.0, float(chaos)))
    return 0.01 + c * 0.29


def trig_prob_from_density(density: float) -> float:
    """DENSITY → sequencer.set_trig_prob() の計算式（設計書 セクション6 笛②）。

    OSC コマンドではなく数値で返す（呼び出し元が sequencer.set_trig_prob() に渡す）。
    """
    d = max(0.0, min(1.0, float(density)))
    return 0.1 + d * 0.7


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
