"""
ChaosEngine のユニットテスト
============================
「Dejavuパターンによる記憶付きカオスドリフト」が正しく動くかを検証する。
実際のOSC通信・asyncio ループは使わず、純粋な計算ロジックをテストする。
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from collections import deque


# ── _ChaosParam のテスト ───────────────────────────────

def test_chaos_param_floor_ceiling():
    """floor と ceiling が attractor ± range で計算されるか。"""
    from backend.autonomous import _ChaosParam
    p = _ChaosParam(value=60.0, attractor=60.0, range=20.0, speed=0.02)
    assert p.floor == 40.0
    assert p.ceiling == 80.0


def test_chaos_param_with_value_is_immutable():
    """with_value() は元のインスタンスを変更しない新インスタンスを返すか。"""
    from backend.autonomous import _ChaosParam
    original = _ChaosParam(value=60.0, attractor=60.0, range=20.0, speed=0.02)
    updated = original.with_value(70.0)

    assert original.value == 60.0   # 元のインスタンスは変わらない
    assert updated.value == 70.0
    assert updated.attractor == original.attractor
    assert updated.range == original.range


def test_chaos_param_with_attractor_is_immutable():
    """with_attractor() は元のインスタンスを変更しない新インスタンスを返すか。"""
    from backend.autonomous import _ChaosParam
    original = _ChaosParam(value=60.0, attractor=60.0, range=20.0, speed=0.02)
    updated = original.with_attractor(80.0, 30.0)

    assert original.attractor == 60.0  # 元は変わらない
    assert updated.attractor == 80.0
    assert updated.range == 30.0
    assert updated.value == 60.0       # value は変わらない


def test_chaos_param_clamped():
    """clamped() が [floor, ceiling] の外に出た値を収めるか。"""
    from backend.autonomous import _ChaosParam
    p = _ChaosParam(value=100.0, attractor=60.0, range=20.0, speed=0.02)
    clamped = p.clamped()

    assert clamped.value == 80.0  # ceiling に収まる
    assert p.value == 100.0       # 元は変わらない


def test_chaos_param_clamped_returns_self_if_within_range():
    """値が範囲内のとき clamped() は同じインスタンスを返すか。"""
    from backend.autonomous import _ChaosParam
    p = _ChaosParam(value=60.0, attractor=60.0, range=20.0, speed=0.02)
    assert p.clamped() is p


# ── ChaosEngine の基本動作テスト ────────────────────────

def make_chaos_engine():
    """テスト用の ChaosEngine インスタンスを作成する。"""
    from backend.autonomous import ChaosEngine
    send_osc = MagicMock()
    broadcast = AsyncMock()
    return ChaosEngine(send_osc, broadcast), send_osc, broadcast


def test_chaos_engine_initial_state():
    """ChaosEngine の初期状態に全レイヤーが含まれているか。"""
    engine, _, _ = make_chaos_engine()
    state = engine.get_state()

    assert "drone" in state
    assert "granular" in state
    assert "rhythmic" in state


def test_chaos_engine_state_has_value_attractor_range():
    """get_state() の各パラメーターに value, attractor, range が含まれるか。"""
    engine, _, _ = make_chaos_engine()
    state = engine.get_state()

    for layer_state in state.values():
        for param_state in layer_state.values():
            assert "value" in param_state
            assert "attractor" in param_state
            assert "range" in param_state


def test_chaos_engine_set_scene_updates_attractor():
    """set_scene() がattractorを正しく更新するか。"""
    engine, _, _ = make_chaos_engine()

    scene = {
        "drone": {
            "freq_attractor": 41.0,
            "freq_range": 15.0,
            "feedback_attractor": 0.35,
            "shimmer_attractor": 0.5,
            "room_attractor": 0.92,
        },
        "granular": {
            "density_attractor": 5.0,
            "density_range": 8.0,
            "spray_attractor": 0.3,
            "room_attractor": 0.7,
        },
        "rhythmic": {
            "prob_attractor": 0.1,
            "prob_range": 0.1,
        },
    }
    engine.set_scene(scene)
    state = engine.get_state()

    assert state["drone"]["freq"]["attractor"] == 41.0
    assert state["drone"]["freq"]["range"] == 15.0
    assert state["drone"]["feedback_amt"]["attractor"] == 0.35
    assert state["granular"]["density"]["attractor"] == 5.0
    assert state["granular"]["density"]["range"] == 8.0
    assert state["rhythmic"]["prob"]["attractor"] == 0.1


def test_chaos_engine_set_scene_does_not_change_current_value():
    """set_scene() はattractorを更新するが現在値は急変しないか。"""
    engine, _, _ = make_chaos_engine()
    initial_freq_value = engine.get_state()["drone"]["freq"]["value"]

    engine.set_scene({
        "drone": {"freq_attractor": 200.0, "freq_range": 10.0},
        "granular": {},
        "rhythmic": {},
    })

    # 引力点は変わったが現在値はそのまま
    state = engine.get_state()
    assert state["drone"]["freq"]["value"] == initial_freq_value
    assert state["drone"]["freq"]["attractor"] == 200.0


# ── Dejavu ロジックのテスト ────────────────────────────

def test_next_value_stays_within_bounds():
    """_next_value() が floor〜ceiling の境界内に収まるか（100回試行）。"""
    from backend.autonomous import ChaosEngine, _ChaosParam
    engine, _, _ = make_chaos_engine()

    p = _ChaosParam(value=60.0, attractor=60.0, range=20.0, speed=0.02)
    path = "drone/freq"
    # 履歴は空の状態でテスト

    for _ in range(100):
        new_val = engine._next_value(path, p)
        assert p.floor <= new_val <= p.ceiling, \
            f"境界外: {new_val} (floor={p.floor}, ceiling={p.ceiling})"


def test_next_value_uses_history_when_available():
    """履歴がある場合に確率的に過去の値が選ばれるか（統計的検証）。"""
    from backend.autonomous import ChaosEngine, _ChaosParam
    import random

    engine, _, _ = make_chaos_engine()
    p = _ChaosParam(value=60.0, attractor=60.0, range=20.0, speed=0.02)
    path = "drone/freq"

    # 履歴に特定の値を入れる（境界内の値を使う）
    historical_value = 65.0
    engine._history[path] = deque([historical_value], maxlen=8)

    # DEJAVU_PROB=0.3 なので十分な試行で少なくとも1回は過去値が選ばれるはず
    selected_values = set()
    with patch("random.random", side_effect=[0.1] + [0.9] * 99):
        # 最初の1回は dejavu_prob 以下の乱数 → 過去値を返す
        val = engine._next_value(path, p)
        selected_values.add(val)

    assert historical_value in selected_values


# ── asyncio tick のテスト ──────────────────────────────

@pytest.mark.asyncio
async def test_tick_sends_osc_messages():
    """_tick() が全パラメーターにOSCメッセージを送るか。"""
    from backend.autonomous import ChaosEngine
    send_osc = MagicMock()
    broadcast = AsyncMock()
    engine = ChaosEngine(send_osc, broadcast)

    await engine._tick()

    # drone, granular, rhythmic の全パラメーターにOSCが送られているか
    assert send_osc.called
    calls = send_osc.call_args_list
    addresses = [call[0][0] for call in calls]
    assert "/matoma/drone/param" in addresses
    assert "/matoma/granular/param" in addresses
    assert "/matoma/rhythmic/param" in addresses


@pytest.mark.asyncio
async def test_tick_broadcasts_chaos_state():
    """_tick() 後にブラウザへ chaos_state が送られるか。"""
    from backend.autonomous import ChaosEngine
    send_osc = MagicMock()
    broadcast = AsyncMock()
    engine = ChaosEngine(send_osc, broadcast)

    await engine._tick()

    broadcast.assert_awaited_once()
    call_args = broadcast.call_args[0][0]
    assert call_args["type"] == "chaos_state"
    assert "state" in call_args


@pytest.mark.asyncio
async def test_tick_accumulates_history():
    """_tick() を繰り返すと履歴が蓄積されるか。"""
    from backend.autonomous import ChaosEngine
    send_osc = MagicMock()
    broadcast = AsyncMock()
    engine = ChaosEngine(send_osc, broadcast)

    assert len(engine._history["drone/freq"]) == 0
    await engine._tick()
    assert len(engine._history["drone/freq"]) == 1
    await engine._tick()
    assert len(engine._history["drone/freq"]) == 2


@pytest.mark.asyncio
async def test_history_max_len_is_8():
    """履歴が最大8世代を超えないか。"""
    from backend.autonomous import ChaosEngine
    send_osc = MagicMock()
    broadcast = AsyncMock()
    engine = ChaosEngine(send_osc, broadcast)

    for _ in range(20):
        await engine._tick()

    for path, history in engine._history.items():
        assert len(history) <= ChaosEngine.HISTORY_LEN, \
            f"{path}: 履歴が {len(history)} 件（最大 {ChaosEngine.HISTORY_LEN}）"


# ── start/stop のテスト ────────────────────────────────

@pytest.mark.asyncio
async def test_chaos_engine_start_stop():
    """start() / stop() が is_running フラグを正しく切り替えるか。"""
    from backend.autonomous import ChaosEngine
    send_osc = MagicMock()
    broadcast = AsyncMock()
    engine = ChaosEngine(send_osc, broadcast)

    assert not engine.is_running

    engine.start()
    assert engine.is_running

    engine.stop()
    assert not engine.is_running
    # 少し待ってループが止まっていることを確認
    await asyncio.sleep(0.05)
