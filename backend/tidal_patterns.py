"""
Tidalパターン生成ヘルパー
========================
GUIのパラメーターからTidal Cyclesのコードを生成する。
"""

# ── 自律モード用コード進行プリセット ──────────────────────────────────
# 各エントリは (ルートノート, コードタイプ) のリスト
# コードタイプは CHORD_MAP のキーを使う
PROGRESSIONS: dict[str, list[tuple[str, str]]] = {
    "ambient_minor": [
        ("C", "minor 7"), ("Ab", "major 7"), ("Eb", "major 7"), ("Bb", "major 7"),
    ],
    "dark_drone": [
        ("A", "minor"), ("F", "major"), ("G", "minor"), ("E", "minor"),
    ],
    "minimal_shift": [
        ("C", "minor 7"), ("F", "minor 7"),
    ],
    "alva_noto": [
        ("C", "minor"), ("Ab", "major"), ("Eb", "major"), ("Bb", "major"),
        ("F", "minor"), ("C", "minor"),
    ],
    "bright_drift": [
        ("C", "major 7"), ("G", "major 7"), ("Am", "minor 7"), ("F", "major 7"),
    ],
}

# ── 自律モード用アルペジオリズムパターン ──────────────────────────────
# スケールの度数を表す文字列。Tidalの scale 関数に渡す
ARP_RHYTHMS: list[str] = [
    "0 1 2 3 4 5 6 7",      # 上昇
    "7 6 5 4 3 2 1 0",      # 下降
    "0 2 4 7 4 2 0 2",      # 折り返し
    "0 1 3 5 3 1 0 1",      # 波状
    "0 4 7 4 0 4 7 4",      # ペンデュラム
    "0 0 2 4 0 0 2 7",      # アクセント付き
]

# スケール名の対応表（GUI表示名 → Tidal名）
SCALE_MAP: dict[str, str] = {
    "major": "major",
    "minor": "minor",
    "dorian": "dorian",
    "phrygian": "phrygian",
    "lydian": "lydian",
    "mixolydian": "mixolydian",
    "locrian": "locrian",
    "pentatonic": "minPent",
    "major pentatonic": "majPent",
    "whole tone": "wholetone",
    "chromatic": "chromatic",
}

# コードタイプの対応表（GUI表示名 → Tidal名）
CHORD_MAP: dict[str, str] = {
    "major": "maj",
    "minor": "min",
    "diminished": "dim",
    "augmented": "aug",
    "major 7": "maj7",
    "minor 7": "min7",
    "dominant 7": "dom7",
    "suspended 2": "sus2",
    "suspended 4": "sus4",
}

# ルートノートのMIDIノート番号（オクターブ4 = C4=60）
ROOT_MIDI: dict[str, int] = {
    "C": 60, "C#": 61, "Db": 61,
    "D": 62, "D#": 63, "Eb": 63,
    "E": 64,
    "F": 65, "F#": 66, "Gb": 66,
    "G": 67, "G#": 68, "Ab": 68,
    "A": 69, "A#": 70, "Bb": 70,
    "B": 71,
}

# 利用可能なシンセ一覧
SYNTHS = [
    "superpiano",
    "supersaw",
    "supersquare",
    "superpwm",
    "superpad",
    "superchip",
]


def tempo_to_cps(bpm: float, beats_per_cycle: int = 4) -> float:
    """BPMをTidalのCPS（Cycles Per Second）に変換する。"""
    return bpm / 60 / beats_per_cycle


def make_tempo_code(bpm: float, beats_per_cycle: int = 4) -> str:
    """テンポ設定コードを生成する。"""
    cps = tempo_to_cps(bpm, beats_per_cycle)
    return f"setcps {cps:.4f}  -- {bpm:.0f} BPM"


def make_chord_pattern(
    track: int,
    synth: str,
    root: str,
    chord: str,
    octave: int = 4,
    amp: float = 0.5,
) -> str:
    """コードパターンを生成する。
    例: d1 $ n (chord "min" + 60) # s "superpiano" # amp 0.5
    """
    tidal_chord = CHORD_MAP.get(chord, "min")
    root_midi = ROOT_MIDI.get(root, 60) + (octave - 4) * 12
    return (
        f'd{track} $ n (chord "{tidal_chord}" + {root_midi}) '
        f'# s "{synth}" # amp {amp:.2f}'
    )


def make_scale_pattern(
    track: int,
    synth: str,
    root: str,
    scale: str,
    degrees: str = "0 1 2 3 4 5 6 7",
    octave: int = 4,
    amp: float = 0.5,
) -> str:
    """スケールパターンを生成する。
    例: d2 $ note (scale "minor" "0 1 2 3 4 5 6 7" + 60) # s "superpiano" # amp 0.5
    """
    tidal_scale = SCALE_MAP.get(scale, "minor")
    root_midi = ROOT_MIDI.get(root, 60) + (octave - 4) * 12
    return (
        f'd{track} $ note (scale "{tidal_scale}" "{degrees}" + {root_midi}) '
        f'# s "{synth}" # amp {amp:.2f}'
    )


def make_arp_pattern(
    track: int,
    synth: str,
    root: str,
    scale: str,
    steps: int = 8,
    octave: int = 4,
    amp: float = 0.5,
) -> str:
    """アルペジオパターンを生成する。
    例: d2 $ note (scale "minor" (run 8) + 60) # s "superpiano" # amp 0.5
    """
    tidal_scale = SCALE_MAP.get(scale, "minor")
    root_midi = ROOT_MIDI.get(root, 60) + (octave - 4) * 12
    return (
        f'd{track} $ note (scale "{tidal_scale}" (run {steps}) + {root_midi}) '
        f'# s "{synth}" # amp {amp:.2f}'
    )


# ── ドラムパターンプリセット ─────────────────────────────────────────
# Autechre 的なリズムに近づくためのパターン群
# ?x = 確率 x でトリガー、*n = n 分割、~ = 休符、! = 繰り返し
DRUM_PRESETS: dict[str, dict[str, str]] = {
    "minimal": {
        "kick":  '"bd ~ ~ bd"',
        "snare": '"~ ~ sd ~"',
        "hat":   '"hh ~ hh ~"',
    },
    "polyrhythm": {
        "kick":  '"bd ~ bd ~ ~" # slow 1.33',
        "snare": '"~ sd ~ ~"',
        "hat":   '"hh*3 ~ hh*2"',
    },
    "glitch": {
        "kick":  '"bd?0.6 ~ bd?0.4 ~ bd?0.3 ~"',
        "snare": '"~ sd?0.5 ~ ~ sd?0.3"',
        "hat":   '"hh?0.8 hh*2?0.5 ~ hh?0.7"',
    },
    "euclidean": {
        "kick":  '"bd" # euclid 3 8',
        "snare": '"sd" # euclid 2 8',
        "hat":   '"hh" # euclid 5 8',
    },
    "fragment": {
        "kick":  '"bd?0.3 ~ ~ ~ bd?0.2 ~ ~ ~"',
        "snare": '"~ ~ ~ sd?0.25 ~ ~ ~ ~"',
        "hat":   '"hh?0.4 ~ hh?0.3 ~"',
    },
    "autechre": {
        "kick":  '"bd ~ bd?0.5 ~ ~ bd?0.3 bd ~" # slow 1.5',
        "snare": '"~ sd?0.6 ~ ~ ~ sd?0.4 ~"',
        "hat":   '"hh*2?0.7 ~ hh?0.5 hh*3?0.4 ~ hh?0.6"',
    },
}


def make_drum_pattern(
    kick_track: int,
    snare_track: int,
    hat_track: int,
    preset: str = "minimal",
    kick_gain: float = 0.9,
    snare_gain: float = 0.7,
    hat_gain: float = 0.5,
    speed: float = 1.0,
) -> list[str]:
    """ドラムパターンを生成する。3トラック分のコードリストを返す。

    Args:
        kick_track: キックのTidalトラック番号（d3 等）
        snare_track: スネアのトラック番号
        hat_track: ハットのトラック番号
        preset: DRUM_PRESETS のキー
        kick_gain, snare_gain, hat_gain: 各音量
        speed: テンポ倍率（0.5=半速、2.0=倍速）
    """
    p = DRUM_PRESETS.get(preset, DRUM_PRESETS["minimal"])
    speed_suffix = f" # fast {speed:.2f}" if speed != 1.0 else ""

    def track(n: int, pattern: str, gain: float) -> str:
        return f'd{n} $ s {pattern} # gain {gain:.2f}{speed_suffix}'

    return [
        track(kick_track,  p["kick"],  kick_gain),
        track(snare_track, p["snare"], snare_gain),
        track(hat_track,   p["hat"],   hat_gain),
    ]
