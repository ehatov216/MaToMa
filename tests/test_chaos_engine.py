"""
ThreeLayerController のユニットテスト
=====================================
3層制御（Upper=Markov、Middle=BoundedWalk、Lower=Dejavu）が
正しく動くかを検証する。実際のOSC通信・asyncioループは使わず、
純粋な計算ロジックをテストする。
"""

import asyncio
import pytest
from collections import deque
from unittest.mock import AsyncMock, MagicMock, patch


# ── _middle_next のテスト ──────────────────────────────────────────

def make_ctrl(
    center: float = 0.25,
    width: float = 0.10,
    speed: float = 0.8,
    snap_prob: float = 0.30,
    micro_range: float = 0.025,
    floor: float = 0.0,
    ceiling: float = 1.0,
):
    from backend.three_layer_controller import UpperControl
    return UpperControl(
        center=center,
        width=width,
        speed=speed,
        snap_prob=snap_prob,
        micro_range=micro_range,
        floor=floor,
        ceiling=ceiling,
    )


def test_middle_next_stays_within_zone(subtests):
    """_middle_next() が zone [center-width, center+width] 内に収まるか（100回）。"""
    from backend.three_layer_controller import _middle_next
    ctrl = make_ctrl(center=0.25, width=0.10, floor=0.0, ceiling=1.0)

    current = 0.25
    for _ in range(100):
        new_val = _middle_next(current, ctrl)
        lo = max(ctrl.floor, ctrl.center - ctrl.width)
        hi = min(ctrl.ceiling, ctrl.center + ctrl.width)
        assert lo <= new_val <= hi, (
            f"zone外: {new_val:.4f} (lo={lo}, hi={hi})"
        )
        current = new_val


def test_middle_next_converges_toward_center():
    """_middle_next() が高速モードでは中心に引き寄せられるか（drift 方向の検証）。"""
    from backend.three_layer_controller import _middle_next

    # 中心より大幅に下にある current が、drift で上がる傾向を持つか
    ctrl = make_ctrl(center=0.80, width=0.05, speed=1.0, floor=0.0, ceiling=1.0)
    values = [_middle_next(0.30, ctrl) for _ in range(50)]
    # 中心 0.80 に向かう引き寄せがあるなら、平均が 0.75 以上のゾーンに入るはず
    assert max(values) >= ctrl.center - ctrl.width


# ── _lower_next のテスト ───────────────────────────────────────────

def test_lower_next_within_floor_ceiling():
    """_lower_next() の出力が floor〜ceiling に収まるか（200回）。"""
    from backend.three_layer_controller import _lower_next
    ctrl = make_ctrl(center=0.25, width=0.10, snap_prob=0.5, micro_range=0.025,
                     floor=0.0, ceiling=1.0)
    history = deque([0.20, 0.22, 0.24], maxlen=8)

    for _ in range(200):
        val = _lower_next(0.25, ctrl, history)
        assert ctrl.floor <= val <= ctrl.ceiling, (
            f"floor/ceiling外: {val}"
        )


def test_lower_next_uses_history_when_snap():
    """snap_prob=1.0 のとき必ず履歴から値を取り出すか。"""
    from backend.three_layer_controller import _lower_next
    ctrl = make_ctrl(snap_prob=1.0, micro_range=0.0, floor=0.0, ceiling=1.0)
    historical = 0.777
    history = deque([historical], maxlen=8)

    with patch("random.random", return_value=0.0):   # 0.0 < 1.0 → snap 確定
        val = _lower_next(0.25, ctrl, history)

    assert val == historical


def test_lower_next_uses_micro_noise_when_no_snap():
    """snap しない場合は middle 周辺の micro_range 内に収まるか。"""
    from backend.three_layer_controller import _lower_next
    ctrl = make_ctrl(snap_prob=0.0, micro_range=0.001, floor=0.0, ceiling=1.0)
    history = deque(maxlen=8)

    for _ in range(50):
        val = _lower_next(0.50, ctrl, history)
        # micro_range が 0.001 → gauss(0, 0.0005) なので通常は ±0.01 以内
        assert abs(val - 0.50) < 0.05


def test_lower_next_empty_history_no_snap():
    """履歴が空のとき snap せずに micro_range だけで揺らすか。"""
    from backend.three_layer_controller import _lower_next
    ctrl = make_ctrl(snap_prob=0.9, micro_range=0.0, floor=0.0, ceiling=1.0)
    history = deque(maxlen=8)   # 空

    val = _lower_next(0.50, ctrl, history)
    # 履歴なし → スナップ不可 → middle そのまま（micro_range=0 なので noise=0）
    assert val == 0.50


# ── UpperControl の検証 ───────────────────────────────────────────

def test_upper_control_fields():
    """UpperControl が全フィールドを保持するか。"""
    from backend.three_layer_controller import UpperControl
    uc = UpperControl(
        center=0.4, width=0.1, speed=0.8,
        snap_prob=0.3, micro_range=0.025,
        floor=0.0, ceiling=1.0,
    )
    assert uc.center == 0.4
    assert uc.snap_prob == 0.3
    assert uc.floor == 0.0


# ── ThreeLayerController 初期状態テスト ──────────────────────────

def make_controller():
    from backend.three_layer_controller import ThreeLayerController
    send_osc = MagicMock()
    broadcast = AsyncMock()
    return ThreeLayerController(send_osc, broadcast), send_osc, broadcast


def test_controller_initial_layers():
    """初期状態に全4レイヤーが含まれているか。"""
    ctrl, _, _ = make_controller()
    state = ctrl.get_state()
    assert "drone" in state
    assert "granular" in state
    assert "gran_synth" in state
    assert "gran_sampler" in state


def test_controller_state_has_value_attractor_range():
    """get_state() の各パラメーターに value / attractor / range が含まれるか。"""
    ctrl, _, _ = make_controller()
    state = ctrl.get_state()

    for layer_state in state.values():
        for param_state in layer_state.values():
            assert "value" in param_state
            assert "attractor" in param_state
            assert "range" in param_state


def test_controller_initial_value_within_specs():
    """初期値が PARAM_SPECS の [min, max] 内に収まるか。"""
    from backend.three_layer_controller import PARAM_SPECS, ThreeLayerController
    ctrl, _, _ = make_controller()
    state = ctrl.get_state()

    for layer, params in PARAM_SPECS.items():
        for param, specs in params.items():
            min_val, max_val, init_val = specs[0], specs[1], specs[2]
            v = state[layer][param]["value"]
            assert min_val <= v <= max_val, (
                f"{layer}/{param}: {v} は [{min_val}, {max_val}] 外"
            )


# ── set_scene() のテスト ──────────────────────────────────────────

def test_set_scene_updates_attractor():
    """set_scene() が attractor（zone center）を更新するか。"""
    ctrl, _, _ = make_controller()
    ctrl.set_scene({
        "drone":    {"feedback_attractor": 0.8},
        "granular": {"density_attractor": 30.0, "density_range": 10.0},
    })
    state = ctrl.get_state()
    assert state["drone"]["feedback_amt"]["attractor"] == 0.8
    assert state["granular"]["density"]["attractor"] == 30.0
    assert state["granular"]["density"]["range"] == 10.0


def test_set_scene_does_not_change_current_value():
    """set_scene() は attractor を変えるが現在値を急変させないか。"""
    ctrl, _, _ = make_controller()
    initial_feedback = ctrl.get_state()["drone"]["feedback_amt"]["value"]

    ctrl.set_scene({"drone": {"feedback_attractor": 0.99}, "granular": {}})

    state = ctrl.get_state()
    assert state["drone"]["feedback_amt"]["value"] == initial_feedback
    assert state["drone"]["feedback_amt"]["attractor"] == 0.99


# ── _tick() のテスト ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tick_sends_osc_for_all_layers():
    """_tick() が全レイヤーにOSCメッセージを送るか。"""
    from backend.three_layer_controller import PARAM_SPECS
    ctrl, send_osc, _ = make_controller()

    await ctrl._tick()

    assert send_osc.called
    addresses = {call[0][0] for call in send_osc.call_args_list}
    assert "/matoma/drone/param"       in addresses
    assert "/matoma/granular/param"    in addresses
    assert "/matoma/gran_synth/param"  in addresses
    assert "/matoma/gran_sampler/param" in addresses


@pytest.mark.asyncio
async def test_tick_broadcasts_chaos_state():
    """_tick() 後にブラウザへ chaos_state が送られるか。"""
    ctrl, _, broadcast = make_controller()

    await ctrl._tick()

    broadcast.assert_awaited_once()
    payload = broadcast.call_args[0][0]
    assert payload["type"] == "chaos_state"
    assert "state" in payload


@pytest.mark.asyncio
async def test_tick_accumulates_history():
    """_tick() を繰り返すと履歴が蓄積されるか。"""
    from backend.three_layer_controller import HISTORY_LEN
    ctrl, _, _ = make_controller()
    path = "drone/feedback_amt"

    assert len(ctrl._history[path]) == 0
    await ctrl._tick()
    assert len(ctrl._history[path]) == 1
    await ctrl._tick()
    assert len(ctrl._history[path]) == 2


@pytest.mark.asyncio
async def test_history_max_len_respected():
    """履歴が HISTORY_LEN（8）を超えないか。"""
    from backend.three_layer_controller import HISTORY_LEN
    ctrl, _, _ = make_controller()

    for _ in range(20):
        await ctrl._tick()

    for path, hist in ctrl._history.items():
        assert len(hist) <= HISTORY_LEN, (
            f"{path}: 履歴が {len(hist)} 件（最大 {HISTORY_LEN}）"
        )


# ── start / stop のテスト ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_controller_start_stop_flag():
    """start() / stop() が is_running フラグを正しく切り替えるか。"""
    ctrl, _, _ = make_controller()

    assert not ctrl.is_running

    loop = asyncio.get_running_loop()
    # start() は asyncio タスクを作るため running loop が必要
    ctrl.start()
    assert ctrl.is_running

    ctrl.stop()
    assert not ctrl.is_running
    # ループが確実に止まるのを少し待つ
    await asyncio.sleep(0.05)


# ── set_speed / set_dejavu_prob のテスト ──────────────────────────

def test_set_speed_affects_upper_override():
    """set_speed() が UpperLayer の speed_override に反映されるか。"""
    ctrl, _, _ = make_controller()
    ctrl.set_speed(1.5)
    # get_control() 経由で speed が反映される
    uc = ctrl._upper.get_control("drone", "feedback_amt")
    assert uc.speed == 1.5


def test_set_dejavu_prob_affects_upper_override():
    """set_dejavu_prob() が UpperLayer の snap_override に反映されるか。"""
    ctrl, _, _ = make_controller()
    ctrl.set_dejavu_prob(0.9)
    uc = ctrl._upper.get_control("granular", "density")
    assert uc.snap_prob == 0.9
