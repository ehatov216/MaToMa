"""ランダマイズモデル — ChaosEngineが使用する4つのパラメーター更新戦略。

各モデルは next_value(value, attractor, floor, ceiling, range_val, speed, history) → float
というインターフェースを実装する。
"""
from __future__ import annotations

import math
import random
from collections import deque
from typing import Protocol


# ---------------------------------------------------------------------------
# プロトコル定義
# ---------------------------------------------------------------------------

class RandomizeModel(Protocol):
    def next_value(
        self,
        value: float,
        attractor: float,
        floor: float,
        ceiling: float,
        range_val: float,
        speed: float,
        history: deque[float],
    ) -> float:
        """次の値を計算して返す。"""
        ...


# ---------------------------------------------------------------------------
# BoundedWalkModel — 引力点へのドリフト + ランダム摂動
# ---------------------------------------------------------------------------

class BoundedWalkModel:
    """ChaosEngine._next_value の旧BoundedWalk部分を切り出したもの。"""

    def next_value(
        self,
        value: float,
        attractor: float,
        floor: float,
        ceiling: float,
        range_val: float,
        speed: float,
        history: deque[float],  # noqa: ARG002 — 使わないが統一シグネチャ
    ) -> float:
        attraction = (attractor - value) * 0.1
        perturbation = range_val * speed * (random.random() * 2.0 - 1.0)
        new_val = value + attraction + perturbation
        return max(floor, min(ceiling, new_val))


# ---------------------------------------------------------------------------
# DejavuModel — 過去状態への確率的スナップバック
# ---------------------------------------------------------------------------

class DejavuModel:
    """Tom Whitwell の Dejavu パターン — 一定確率で過去値に戻る。

    snap_prob: 過去値へスナップする確率（0.0〜1.0）。
    残り確率では BoundedWalk を実行する。
    """

    def __init__(self, snap_prob: float = 0.3) -> None:
        self.snap_prob = snap_prob
        self._bounded_walk = BoundedWalkModel()

    def set_snap_prob(self, prob: float) -> None:
        self.snap_prob = max(0.0, min(1.0, prob))

    def next_value(
        self,
        value: float,
        attractor: float,
        floor: float,
        ceiling: float,
        range_val: float,
        speed: float,
        history: deque[float],
    ) -> float:
        if history and random.random() < self.snap_prob:
            return random.choice(list(history))
        return self._bounded_walk.next_value(
            value, attractor, floor, ceiling, range_val, speed, history
        )


# ---------------------------------------------------------------------------
# FractalModel — 1/fノイズ（ピンクノイズ）による有機的テクスチャ
# ---------------------------------------------------------------------------

# 各オクターブ: (周波数倍率, 振幅)  — 高周波ほど振幅が小さい
_OCTAVES: list[tuple[float, float]] = [
    (1.0, 1.0),
    (2.0, 0.5),
    (4.0, 0.25),
    (8.0, 0.125),
    (16.0, 0.0625),
]

# 全オクターブの振幅合計（正規化用）
_OCTAVE_SUM: float = sum(amp for _, amp in _OCTAVES)

# 基本周波数: 1サイクル ≈ 125 ticks（0.1s/tick × 125 ≈ 12.5s）
_BASE_FREQ: float = 0.008


class FractalModel:
    """1/fノイズで delta を生成し、引力点方向へのドリフトと重ね合わせる。

    全パラメーターで同じオシレーター群を共有することで
    「同じ宇宙の中で一緒に揺れる」有機的な相関を生む。
    """

    def __init__(self) -> None:
        # 各オクターブの位相をランダム初期化
        self._phases: list[float] = [
            random.random() * 2.0 * math.pi for _ in _OCTAVES
        ]

    def _tick(self) -> float:
        """1ステップ進めて正規化済みノイズ値（−1〜+1）を返す。"""
        total = 0.0
        for i, (freq_mult, amp) in enumerate(_OCTAVES):
            self._phases[i] += 2.0 * math.pi * _BASE_FREQ * freq_mult
            total += amp * math.sin(self._phases[i])
        return total / _OCTAVE_SUM

    def next_value(
        self,
        value: float,
        attractor: float,
        floor: float,
        ceiling: float,
        range_val: float,
        speed: float,
        history: deque[float],  # noqa: ARG002
    ) -> float:
        noise = self._tick()  # −1〜+1
        attraction = (attractor - value) * 0.1
        perturbation = range_val * speed * noise
        new_val = value + attraction + perturbation
        return max(floor, min(ceiling, new_val))


# ---------------------------------------------------------------------------
# LSystemModel — 短いフレーズ記憶 + ルール変換で次の値を予測
# ---------------------------------------------------------------------------

PHRASE_LEN: int = 6    # 「フレーズ」として参照する直近の値の個数
RULE_PROB: float = 0.25  # トレンド反転を起こす確率（完全な繰り返しを避ける）


class LSystemModel:
    """直近N個の値を「フレーズ」として保持し、傾向を検出して次の値を予測する。

    - フレーズの平均 → attractor として使用
    - フレーズの傾き（線形回帰）で継続/反転を確率的に決定
    - RULE_PROB でトレンドを反転させてモチーフに発展性を持たせる
    """

    def next_value(
        self,
        value: float,
        attractor: float,
        floor: float,
        ceiling: float,
        range_val: float,
        speed: float,
        history: deque[float],
    ) -> float:
        phrase = list(history)[-PHRASE_LEN:]

        if len(phrase) < 2:
            # フレーズが短すぎる場合は BoundedWalk にフォールバック
            attraction = (attractor - value) * 0.1
            perturbation = range_val * speed * (random.random() * 2.0 - 1.0)
            new_val = value + attraction + perturbation
            return max(floor, min(ceiling, new_val))

        # フレーズの傾き（簡易線形回帰: y = a*x + b の a）
        n = len(phrase)
        x_mean = (n - 1) / 2.0
        y_mean = sum(phrase) / n
        num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(phrase))
        den = sum((i - x_mean) ** 2 for i in range(n))
        slope = num / den if den != 0.0 else 0.0

        # フレーズ平均を引力点として使いつつ、現在の引力点とブレンド
        phrase_attractor = y_mean
        blended_attractor = 0.5 * phrase_attractor + 0.5 * attractor

        # RULE_PROB でトレンド反転（Lシステムの「ルール変換」に相当）
        direction = -slope if random.random() < RULE_PROB else slope

        attraction = (blended_attractor - value) * 0.1
        perturbation = range_val * speed * (direction / (range_val + 1e-9))
        perturbation = max(-range_val * speed, min(range_val * speed, perturbation))

        new_val = value + attraction + perturbation
        return max(floor, min(ceiling, new_val))


# ---------------------------------------------------------------------------
# 動的ブレンドモデル — 反復↔カオス比率を実行時に変更可能
# ---------------------------------------------------------------------------

class DynamicBlendLower:
    """下位レイヤー用: Dejavu (繰り返し) ↔ BoundedWalk (カオス) を動的ブレンド。

    ratio=0.0 → pure Dejavu（繰り返し重視）
    ratio=1.0 → pure BoundedWalk（カオス重視）

    Markov の set_dejavu_prob() は内部 DejavuModel に委譲される。
    """

    def __init__(self, ratio: float = 0.5) -> None:
        self._dejavu = DejavuModel()
        self._bw = BoundedWalkModel()
        self.ratio = max(0.0, min(1.0, ratio))

    def set_ratio(self, ratio: float) -> None:
        self.ratio = max(0.0, min(1.0, ratio))

    def set_snap_prob(self, prob: float) -> None:
        """Markov からの snap_prob 更新を内部 DejavuModel に委譲する。"""
        self._dejavu.set_snap_prob(prob)

    def next_value(
        self,
        value: float,
        attractor: float,
        floor: float,
        ceiling: float,
        range_val: float,
        speed: float,
        history: deque[float],
    ) -> float:
        return blend(
            [self._dejavu, self._bw],
            [1.0 - self.ratio, self.ratio],
            value, attractor, floor, ceiling, range_val, speed, history,
        )


class DynamicBlendMiddle:
    """中位レイヤー用: LSystem (繰り返し) ↔ BoundedWalk (カオス) を動的ブレンド。

    ratio=0.0 → pure LSystem（パターン/繰り返し重視）
    ratio=1.0 → pure BoundedWalk（カオス重視）
    """

    def __init__(self, ratio: float = 0.5) -> None:
        self._lsystem = LSystemModel()
        self._bw = BoundedWalkModel()
        self.ratio = max(0.0, min(1.0, ratio))

    def set_ratio(self, ratio: float) -> None:
        self.ratio = max(0.0, min(1.0, ratio))

    def next_value(
        self,
        value: float,
        attractor: float,
        floor: float,
        ceiling: float,
        range_val: float,
        speed: float,
        history: deque[float],
    ) -> float:
        return blend(
            [self._lsystem, self._bw],
            [1.0 - self.ratio, self.ratio],
            value, attractor, floor, ceiling, range_val, speed, history,
        )


# ---------------------------------------------------------------------------
# blend — 複数モデルの重み付き平均
# ---------------------------------------------------------------------------

def blend(
    models: list[RandomizeModel],
    weights: list[float],
    value: float,
    attractor: float,
    floor: float,
    ceiling: float,
    range_val: float,
    speed: float,
    history: deque[float],
) -> float:
    """複数モデルの出力を重みつき平均で合成して返す。"""
    if not models:
        return value
    total_weight = sum(weights)
    if total_weight == 0.0:
        return value
    result = 0.0
    for model, w in zip(models, weights):
        result += w * model.next_value(
            value, attractor, floor, ceiling, range_val, speed, history
        )
    return result / total_weight


# ---------------------------------------------------------------------------
# ブレンドプリセット
# ---------------------------------------------------------------------------

class _BlendMiddle:
    """中位レイヤー用ブレンド: BoundedWalk × Fractal（50:50）。"""

    def __init__(self) -> None:
        self._bw = BoundedWalkModel()
        self._fractal = FractalModel()

    def next_value(
        self,
        value: float,
        attractor: float,
        floor: float,
        ceiling: float,
        range_val: float,
        speed: float,
        history: deque[float],
    ) -> float:
        return blend(
            [self._bw, self._fractal],
            [0.5, 0.5],
            value, attractor, floor, ceiling, range_val, speed, history,
        )


class _BlendLower:
    """下位レイヤー用ブレンド: Dejavu × LSystem（50:50）。"""

    def __init__(self) -> None:
        self._dejavu = DejavuModel()
        self._lsystem = LSystemModel()

    def next_value(
        self,
        value: float,
        attractor: float,
        floor: float,
        ceiling: float,
        range_val: float,
        speed: float,
        history: deque[float],
    ) -> float:
        return blend(
            [self._dejavu, self._lsystem],
            [0.5, 0.5],
            value, attractor, floor, ceiling, range_val, speed, history,
        )


# ---------------------------------------------------------------------------
# モデルファクトリ辞書 — UI の選択名 → インスタンスを返す関数
# ---------------------------------------------------------------------------

def _make_middle(name: str) -> RandomizeModel:
    match name:
        case "fractal":
            return FractalModel()
        case "lsystem":
            return LSystemModel()
        case "blend":
            return _BlendMiddle()
        case _:  # "bounded_walk" またはデフォルト
            return BoundedWalkModel()


def _make_lower(name: str) -> RandomizeModel:
    match name:
        case "bounded_walk":
            return BoundedWalkModel()
        case "lsystem":
            return LSystemModel()
        case "blend":
            return _BlendLower()
        case _:  # "dejavu" またはデフォルト
            return DejavuModel()


MIDDLE_MODELS: dict[str, str] = {
    "bounded_walk": "BoundedWalk",
    "fractal": "Fractal",
    "lsystem": "L-System",
    "blend": "Blend(BW×Fractal)",
}

LOWER_MODELS: dict[str, str] = {
    "dejavu": "Dejavu",
    "bounded_walk": "BoundedWalk",
    "lsystem": "L-System",
    "blend": "Blend(Dejavu×LS)",
}

make_middle_model = _make_middle
make_lower_model = _make_lower
