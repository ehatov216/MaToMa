"""
MusicalControl のユニットテスト
================================
固定モード・自律モードの動作、Tidal コード生成、
BoundedWalk / Dejavu の計算ロジックをテストする。
OSC通信・asyncioループは使わず純粋な計算ロジックをテストする。
"""

import asyncio
import pytest
from collections import deque
from unittest.mock import AsyncMock, MagicMock, patch


# ── ヘルパー ───────────────────────────────────────────────────────────────

def make_musical(
    key_mode: str = "fixed",
    chord_mode: str = "fixed",
    chord_interval: float = 8.0,
    markov_state: str = "medium",
):
    from musical_control import MusicalControl, KEYS

    tidal = MagicMock()
    tidal.is_running = True
    broadcast = AsyncMock()
    get_markov_state = MagicMock(return_value=markov_state)

    mc = MusicalControl(tidal, broadcast, get_markov_state, chord_interval=chord_interval)
    mc.set_key_mode(key_mode)
    mc.set_chord_mode(chord_mode)
    return mc, tidal, broadcast


# ── 固定モード: キー ───────────────────────────────────────────────────────

def test_fixed_key_default():
    """デフォルトは C minor に固定されているか。"""
    mc, _, _ = make_musical()
    state = mc.get_state()
    assert state["key"] == "c"
    assert state["scale"] == "minor"
    assert state["key_mode"] == "fixed"


def test_set_fixed_key_valid():
    """set_fixed_key() が有効なキー・スケールを設定するか。"""
    mc, _, _ = make_musical()
    mc.set_fixed_key("g", "dorian")
    state = mc.get_state()
    assert state["key"] == "g"
    assert state["scale"] == "dorian"


def test_set_fixed_key_invalid_ignored():
    """不正なキーは無視されるか。"""
    mc, _, _ = make_musical()
    mc.set_fixed_key("x")   # 存在しないキー
    state = mc.get_state()
    assert state["key"] == "c"  # 変化しない


def test_set_fixed_key_scale_none():
    """scale=None のとき既存スケールが保たれるか。"""
    mc, _, _ = make_musical()
    mc.set_fixed_key("a", "phrygian")
    mc.set_fixed_key("d")   # scale 未指定
    state = mc.get_state()
    assert state["key"] == "d"
    assert state["scale"] == "phrygian"


# ── 固定モード: コード ─────────────────────────────────────────────────────

def test_fixed_chords_default():
    """デフォルトのコード進行は [0, 3, 4, 0] か。"""
    mc, _, _ = make_musical()
    state = mc.get_state()
    assert state["fixed_chords"] == [0, 3, 4, 0]


def test_set_fixed_chords():
    """set_fixed_chords() がコード進行を更新するか。"""
    mc, _, _ = make_musical()
    mc.set_fixed_chords([0, 4, 5, 3])
    state = mc.get_state()
    assert state["fixed_chords"] == [0, 4, 5, 3]


def test_fixed_chord_index_advances_on_tick():
    """_tick() のたびに固定コード進行が1ステップ進むか。"""
    mc, _, _ = make_musical(chord_mode="fixed")
    mc.set_fixed_chords([0, 3, 4, 0])

    initial_idx = mc._fixed_chord_index
    asyncio.get_event_loop().run_until_complete(mc._tick())
    assert mc._fixed_chord_index == (initial_idx + 1) % 4


def test_fixed_chord_wraps_around():
    """固定コード進行がループするか。"""
    mc, _, _ = make_musical(chord_mode="fixed")
    mc.set_fixed_chords([0, 3])

    for _ in range(4):
        asyncio.get_event_loop().run_until_complete(mc._tick())

    # 4回ステップ → インデックスは 0 に戻る
    assert mc._fixed_chord_index % 2 == 0


# ── 自律モード: キー ───────────────────────────────────────────────────────

def test_auto_key_mode_state_reports_auto():
    """自律モードで get_state() が key_mode=="auto" を返すか。"""
    mc, _, _ = make_musical(key_mode="auto")
    state = mc.get_state()
    assert state["key_mode"] == "auto"


def test_auto_key_always_valid():
    """_auto_update_key() 後のキーが常に有効なキーか（100回）。"""
    from musical_control import KEYS
    mc, _, _ = make_musical(key_mode="auto", markov_state="intense")

    for _ in range(100):
        mc._auto_update_key("intense")
        assert mc._current_key in KEYS


def test_auto_key_changes_to_neighbor():
    """_auto_update_key() がキーを五度圏の隣接キーに変える（prob=1で強制）。"""
    from musical_control import KEY_NEIGHBORS
    mc, _, _ = make_musical(key_mode="auto")
    initial_key = mc._current_key

    with patch("random.random", return_value=0.0):   # 確率 < any prob → 必ず変化
        mc._auto_update_key("intense")

    assert mc._current_key in KEY_NEIGHBORS[initial_key]


# ── 自律モード: コードBoundedWalk ─────────────────────────────────────────

def test_middle_next_stays_in_zone():
    """_middle_next() がゾーン [center-width, center+width] 内に収まるか（100回）。"""
    mc, _, _ = make_musical(chord_mode="auto")
    zone = {"center": 3.5, "width": 2.5, "speed": 0.5, "snap_prob": 0.3, "micro_range": 0.3}

    current = 3.5
    for _ in range(100):
        new_val = mc._middle_next(current, zone)
        lo = max(0.0, zone["center"] - zone["width"])
        hi = min(7.0, zone["center"] + zone["width"])
        assert lo <= new_val <= hi, f"ゾーン外: {new_val:.4f}"
        current = new_val


def test_lower_next_within_range():
    """_lower_next() の出力が 0.0〜7.0 に収まるか（200回）。"""
    mc, _, _ = make_musical(chord_mode="auto")
    zone = {"center": 3.5, "width": 2.5, "speed": 0.5, "snap_prob": 0.3, "micro_range": 0.3}
    history = deque([1.0, 2.5, 4.0], maxlen=8)

    for _ in range(200):
        val = mc._lower_next(3.5, zone, history)
        assert 0.0 <= val <= 7.0, f"範囲外: {val}"


def test_lower_next_snap_uses_history():
    """snap_prob=1.0 のとき必ず履歴から値を返すか。"""
    mc, _, _ = make_musical(chord_mode="auto")
    zone = {"center": 3.5, "width": 2.5, "speed": 0.5, "snap_prob": 1.0, "micro_range": 0.0}
    history = deque([6.5], maxlen=8)

    with patch("random.random", return_value=0.0):
        val = mc._lower_next(3.5, zone, history)

    assert val == 6.5


def test_lower_next_empty_history_no_snap():
    """履歴が空のとき snap せず middle 周辺を返すか（micro_range=0 なら middle そのまま）。"""
    mc, _, _ = make_musical(chord_mode="auto")
    zone = {"center": 3.5, "width": 2.5, "speed": 0.5, "snap_prob": 1.0, "micro_range": 0.0}
    history = deque(maxlen=8)  # 空

    val = mc._lower_next(3.5, zone, history)
    assert abs(val - 3.5) < 0.01  # micro_range=0 → noise≒0


# ── Tidalコード生成 ────────────────────────────────────────────────────────

def test_generate_tidal_code_fixed_c_minor_deg0():
    """C minor, degree=0 のTidalコードが正しいか。"""
    mc, _, _ = make_musical()
    mc.set_fixed_key("c", "minor")
    mc.set_fixed_chords([0])
    mc._fixed_chord_index = 0

    code = mc._generate_tidal_code()
    assert 'd8' in code
    assert '"minor"' in code
    assert '"0 2 4"' in code
    assert '48' in code   # C4 MIDI base


def test_generate_tidal_code_g_dorian_deg3():
    """G dorian, degree=3 のTidalコードが正しいか。"""
    mc, _, _ = make_musical()
    mc.set_fixed_key("g", "dorian")
    mc.set_fixed_chords([3])
    mc._fixed_chord_index = 0

    code = mc._generate_tidal_code()
    assert '"dorian"' in code
    assert '55' in code   # G4 MIDI base


def test_apply_tidal_calls_evaluate():
    """_apply_tidal() が tidal.evaluate() を呼ぶか。"""
    mc, tidal_mock, _ = make_musical()
    tidal_mock.is_running = True

    mc._apply_tidal()

    tidal_mock.evaluate.assert_called_once()
    call_args = tidal_mock.evaluate.call_args[0][0]
    assert "d8" in call_args


def test_apply_tidal_skips_when_tidal_not_running():
    """Tidal未起動のとき _apply_tidal() は evaluate を呼ばないか。"""
    mc, tidal_mock, _ = make_musical()
    tidal_mock.is_running = False

    mc._apply_tidal()

    tidal_mock.evaluate.assert_not_called()


# ── get_state / モード切替 ─────────────────────────────────────────────────

def test_get_state_contains_all_fields():
    """get_state() に必要なフィールドが揃っているか。"""
    mc, _, _ = make_musical()
    state = mc.get_state()
    for field in ("key", "scale", "chord_degree", "chord_degree_float",
                  "key_mode", "chord_mode", "chord_interval", "fixed_chords"):
        assert field in state, f"フィールド不足: {field}"


def test_mode_switch_key():
    """set_key_mode() が有効な値のみ受け付けるか。"""
    mc, _, _ = make_musical()
    mc.set_key_mode("auto")
    assert mc._key_mode == "auto"
    mc.set_key_mode("invalid")
    assert mc._key_mode == "auto"  # 無視される


def test_mode_switch_chord():
    """set_chord_mode() が有効な値のみ受け付けるか。"""
    mc, _, _ = make_musical()
    mc.set_chord_mode("auto")
    assert mc._chord_mode == "auto"
    mc.set_chord_mode("bad")
    assert mc._chord_mode == "auto"  # 無視される


# ── start / stop ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_start_stop_flag():
    """start() / stop() が is_running を切り替えるか。"""
    mc, _, _ = make_musical()

    assert not mc.is_running
    mc.start()
    assert mc.is_running

    mc.stop()
    assert not mc.is_running
    await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_tick_broadcasts_musical_state():
    """_tick() 後にブラウザへ musical_state が送られるか。"""
    mc, _, broadcast = make_musical()

    await mc._tick()

    broadcast.assert_awaited_once()
    payload = broadcast.call_args[0][0]
    assert payload["type"] == "musical_state"
    assert "state" in payload
