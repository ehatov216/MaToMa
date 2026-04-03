"""
MaToMa Tidal パターン生成
==========================
TidalCycles から MaToMa の SuperCollider シンセを叩くための
パターンコードを生成する。

【シンセ名（SC側 rhythmic.scd で定義）】
  matoma_rhythmic_klank  : Klank 金属共鳴（Alva Noto的）
  matoma_rhythmic_fm     : FM Percussion（Autechre的）
  matoma_rhythmic_spring : Spring + Ringz（有機的）
  matoma_rhythmic_chaos  : カオス写像（異物感）
  matoma_rhythmic_grain  : GrainBuf（グラニュラー打撃）

【OSCメッセージ形式（BootTidal_matoma.hs で定義）】
  /matoma/rhythmic/trigger <s:string> <freq:float> <amp:float>

【リズム設計哲学（rhythm_methodology.md より）】
  Alva Noto 的（数学的骨格）: ユークリッド・フィボナッチ・位相差
  OPN 的（呼吸的筋肉）     : 確率・スロー・ランダム密度
  BPM の概念は使わない。時間を「比率・秒・確率」で表現する。
"""


# ── MaToMa シンセ名 ────────────────────────────────────────────────
SYNTH_KLANK = "matoma_rhythmic_klank"   # Alva Noto的・金属グリッド
SYNTH_FM = "matoma_rhythmic_fm"         # Autechre的・予測不能
SYNTH_SPRING = "matoma_rhythmic_spring" # 有機的・金属的共鳴
SYNTH_CHAOS = "matoma_rhythmic_chaos"   # 機械が壊れる感覚
SYNTH_GRAIN = "matoma_rhythmic_grain"   # グラニュラー打撃

# 全シンセ名のリスト（UIなどで参照用）
ALL_SYNTHS: list[str] = [
    SYNTH_KLANK, SYNTH_FM, SYNTH_SPRING, SYNTH_CHAOS, SYNTH_GRAIN,
]


# ── フィボナッチ列 ─────────────────────────────────────────────────
# Alva Noto 的な数学的配置に使う
FIBONACCI: list[int] = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89]


def tempo_to_cps(bpm: float, beats_per_cycle: int = 4) -> float:
    """BPMをTidalのCPS（Cycles Per Second）に変換する。"""
    return bpm / 60 / beats_per_cycle


def make_tempo_code(bpm: float, beats_per_cycle: int = 4) -> str:
    """テンポ設定コードを生成する。"""
    cps = tempo_to_cps(bpm, beats_per_cycle)
    return f"setcps {cps:.4f}  -- {bpm:.0f} BPM相当"


# ── Alva Noto 的パターン（数学的骨格） ───────────────────────────────

def make_euclidean(
    track: int,
    synth: str = SYNTH_KLANK,
    hits: int = 3,
    steps: int = 8,
    freq: float = 440.0,
    amp: float = 0.6,
) -> str:
    """ユークリッドリズムパターンを生成する。

    例: euclid 3 8 → 8ステップ中3回、最も均等に配置
    Alva Noto 的な数学的グリッド。
    """
    return (
        f'd{track} $ euclid {hits} {steps} $ s "{synth}"'
        f' # freq {freq:.1f} # amp {amp:.2f}'
    )


def make_fibonacci_pattern(
    track: int,
    synth: str = SYNTH_KLANK,
    depth: int = 6,
    freq: float = 440.0,
    amp: float = 0.6,
) -> str:
    """フィボナッチ列に基づく密度パターンを生成する。

    フィボナッチ数列の値を slow に渡すことで
    「黄金比的な時間の間隔」を作る。
    Alva Noto 的な数学的配置。

    Args:
        depth: 使うフィボナッチ数の個数（2〜9）
    """
    fibs = FIBONACCI[:max(2, min(depth, len(FIBONACCI)))]
    # フィボナッチ値を Tidal のパターン文字列に変換
    # 例: slow "1 1 2 3 5 8" → それぞれの長さで同じ音を鳴らす
    fib_str = " ".join(str(f) for f in fibs)
    return (
        f'd{track} $ slow "{fib_str}" $ s "{synth}"'
        f' # freq {freq:.1f} # amp {amp:.2f}'
    )


def make_phase_trio(
    tracks: tuple[int, int, int] = (1, 2, 3),
    synths: tuple[str, str, str] = (SYNTH_KLANK, SYNTH_FM, SYNTH_CHAOS),
    periods: tuple[int, int, int] = (13, 21, 34),
    freqs: tuple[float, float, float] = (440.0, 330.0, 220.0),
    amp: float = 0.5,
) -> list[str]:
    """位相差リズム（3つの非同期パターン）を生成する。

    3つのパターンが異なる周期で走る。
    公倍数が極めて大きい → 実質的に繰り返さないパターン。
    Alva Noto 的な多重非同期グリッド。

    Args:
        periods: 各トラックの slow 値（素数や互いに素な数が効果的）
    """
    lines = []
    for t, synth, period, freq in zip(tracks, synths, periods, freqs):
        lines.append(
            f'd{t} $ slow {period} $ s "{synth}"'
            f' # freq {freq:.1f} # amp {amp:.2f}'
        )
    return lines


def make_mathematical_grid(
    track: int,
    synth: str = SYNTH_KLANK,
    subdivisions: int = 7,
    freq: float = 440.0,
    amp: float = 0.6,
) -> str:
    """非整数分割グリッドを生成する。

    4/4 拍子とは異なる「ずれたグリッド」を作る。
    例: 7分割 → 4/4 の上に 7 連符が走る。
    """
    return (
        f'd{track} $ s "{synth}" * {subdivisions}'
        f' # freq {freq:.1f} # amp {amp:.2f}'
    )


# ── OPN 的パターン（確率・密度） ──────────────────────────────────────

def make_probabilistic(
    track: int,
    synth: str = SYNTH_FM,
    density: float = 0.5,
    period: float = 1.0,
    freq: float = 330.0,
    amp: float = 0.5,
) -> str:
    """確率的打突パターンを生成する。

    OPN 的な「いつ鳴るか分からない」感覚。
    density: 発火確率（0.0〜1.0）

    Args:
        density: 発火確率（0.0=ほぼ無音、1.0=常に発火）
        period: slow 値（大きいほどゆっくり）
    """
    # degradeBy = 欠落確率 = 1 - density
    drop_prob = max(0.0, min(0.99, 1.0 - density))
    period_str = f" # slow {period:.1f}" if period != 1.0 else ""
    return (
        f'd{track} $ degradeBy {drop_prob:.2f} $ s "{synth}"'
        f' # freq {freq:.1f} # amp {amp:.2f}{period_str}'
    )


def make_sparse_breathing(
    track: int,
    synth: str = SYNTH_SPRING,
    slow_factor: float = 16.0,
    freq: float = 260.0,
    amp: float = 0.4,
) -> str:
    """呼吸的なスパースパターンを生成する。

    OPN / Tim Hecker 的な「長い間、ときどき鳴る」感覚。
    slow_factor が大きいほど密度が下がる（呼気が長い）。
    """
    return (
        f'd{track} $ slow {slow_factor:.1f} $ degradeBy 0.4 $ s "{synth}"'
        f' # freq {freq:.1f} # amp {amp:.2f}'
    )


# ── プリセット（使用シーン別） ──────────────────────────────────────

# プリセット名 → (track, pattern_code) のリスト
PRESETS: dict[str, list[str]] = {
    # Alva Noto 的：数学的・冷たい・精密
    "alva_euclidean": [
        f'd1 $ euclid 3 8 $ s "{SYNTH_KLANK}" # freq 440 # amp 0.6',
        f'd2 $ euclid 2 7 $ s "{SYNTH_FM}" # freq 220 # amp 0.4',
        f'd3 $ euclid 5 13 $ s "{SYNTH_CHAOS}" # freq 150 # amp 0.3',
    ],
    # フィボナッチ位相差：非常に長い非繰り返しパターン
    "alva_phase": [
        f'd1 $ slow 13 $ s "{SYNTH_KLANK}" # freq 440 # amp 0.6',
        f'd2 $ slow 21 $ s "{SYNTH_FM}" # freq 330 # amp 0.5',
        f'd3 $ slow 34 $ s "{SYNTH_CHAOS}" # freq 220 # amp 0.35',
    ],
    # OPN 的：確率的・温かい・不規則
    "opn_sparse": [
        f'd1 $ degradeBy 0.6 $ slow 4 $ s "{SYNTH_SPRING}"'
        ' # freq 260 # amp 0.5',
        f'd2 $ degradeBy 0.75 $ slow 8 $ s "{SYNTH_FM}"'
        ' # freq 180 # amp 0.4',
    ],
    # ミニマル：ただ1つ鳴らすだけ
    "minimal_klank": [
        f'd1 $ s "{SYNTH_KLANK}" # freq 440 # amp 0.6',
        "d2 silence",
        "d3 silence",
    ],
    # カオス崩壊：全部確率的に重なる
    "chaos_collapse": [
        f'd1 $ degradeBy 0.3 $ euclid 5 8 $ s "{SYNTH_CHAOS}"'
        ' # freq 200 # amp 0.6',
        f'd2 $ degradeBy 0.5 $ euclid 3 7 $ s "{SYNTH_FM}"'
        ' # freq 300 # amp 0.5',
        f'd3 $ degradeBy 0.4 $ slow 2 $ s "{SYNTH_KLANK}"'
        ' # freq 150 # amp 0.4',
    ],
}


def get_preset(name: str) -> list[str]:
    """プリセット名からTidalコードのリストを返す。

    Args:
        name: プリセット名（PRESETS のキー）

    Returns:
        Tidal コードのリスト。不明な名前の場合は minimal_klank。
    """
    return PRESETS.get(name, PRESETS["minimal_klank"])


def hush_all(num_tracks: int = 8) -> list[str]:
    """全トラックを停止するコードを返す。"""
    return ["hush"]
