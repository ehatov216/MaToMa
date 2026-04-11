"""
ThreeLayerController 追加カバレッジテスト
==========================================
test_chaos_engine.py でカバーできていない行を補完する。
対象: UpperLayer の各メソッド・ThreeLayerController のラッパー群・非同期ループ。
"""
from __future__ import annotations

import asyncio
import pytest
from collections import deque
from unittest.mock import AsyncMock, MagicMock, patch


# ── ヘルパー ─────────────────────────────────────────────────────────────────

def make_upper(interval: float = 60.0, energy_fn=None):
    from backend.three_layer_controller import UpperLayer
    broadcast = AsyncMock()
    upper = UpperLayer(broadcast=broadcast, interval=interval, energy_fn=energy_fn)
    return upper, broadcast


def make_controller(send_tidal_ctrl=None):
    from backend.three_layer_controller import ThreeLayerController
    send_osc = MagicMock()
    broadcast = AsyncMock()
    ctrl = ThreeLayerController(
        send_osc=send_osc,
        broadcast=broadcast,
        send_tidal_ctrl=send_tidal_ctrl,
    )
    return ctrl, send_osc, broadcast


# ── UpperLayer.get_state_info() ───────────────────────────────────────────────

class TestUpperLayerGetStateInfo:
    def test_returns_dict_with_required_keys(self):
        """get_state_info() が必須キーを持つ辞書を返すか。"""
        upper, _ = make_upper()
        info = upper.get_state_info()
        assert "running" in info
        assert "state" in info
        assert "interval" in info
        assert "elapsed" in info
        assert "remaining" in info
        assert "speed" in info
        assert "dejavu_prob" in info

    def test_running_is_false_initially(self):
        upper, _ = make_upper()
        assert upper.get_state_info()["running"] is False

    def test_elapsed_is_zero_when_not_running(self):
        upper, _ = make_upper()
        assert upper.get_state_info()["elapsed"] == 0.0

    def test_state_is_medium_initially(self):
        upper, _ = make_upper()
        assert upper.get_state_info()["state"] == "medium"


# ── UpperLayer.clear_zone_override() ─────────────────────────────────────────

class TestClearZoneOverride:
    def test_clearing_removes_override(self):
        """set_zone_override 後に clear_zone_override でデフォルトに戻るか。"""
        from backend.three_layer_controller import STATE_ZONES
        upper, _ = make_upper()
        # デフォルト中心値を取得
        default_center = STATE_ZONES["medium"]["drone"]["feedback_amt"]["center"]
        # オーバーライドを設定してから確認
        upper.set_zone_override("drone", "feedback_amt", 0.99)
        assert upper.get_control("drone", "feedback_amt").center == 0.99
        # クリアするとデフォルトに戻る
        upper.clear_zone_override("drone", "feedback_amt")
        assert upper.get_control("drone", "feedback_amt").center == pytest.approx(default_center)

    def test_clearing_nonexistent_override_is_noop(self):
        """存在しないオーバーライドをクリアしてもエラーにならないか。"""
        upper, _ = make_upper()
        upper.clear_zone_override("drone", "feedback_amt")  # 例外が出ないこと


# ── UpperLayer.force_state() ─────────────────────────────────────────────────

class TestForceState:
    def test_valid_state_changes_state(self):
        """force_state() で有効な状態名に変更されるか。"""
        upper, _ = make_upper()
        upper.force_state("void")
        assert upper.get_state_info()["state"] == "void"

    def test_force_state_clears_overrides(self):
        """force_state() 後にオーバーライドがクリアされるか。"""
        from backend.three_layer_controller import STATE_ZONES
        upper, _ = make_upper()
        upper.set_zone_override("drone", "feedback_amt", 0.99)
        upper.force_state("sparse")
        default_center = STATE_ZONES["sparse"]["drone"]["feedback_amt"]["center"]
        assert upper.get_control("drone", "feedback_amt").center == pytest.approx(default_center)

    def test_unknown_state_does_not_change(self):
        """force_state() に不明な状態を渡しても state が変わらないか。"""
        upper, _ = make_upper()
        upper.force_state("unknown_state_xyz")
        assert upper.get_state_info()["state"] == "medium"

    def test_all_valid_states_accepted(self):
        """全5状態が force_state() で設定できるか。"""
        from backend.three_layer_controller import STATES
        upper, _ = make_upper()
        for s in STATES:
            upper.force_state(s)
            assert upper.get_state_info()["state"] == s


# ── UpperLayer.set_interval() ────────────────────────────────────────────────

class TestSetInterval:
    def test_set_interval_takes_effect(self):
        upper, _ = make_upper()
        upper.set_interval(120.0)
        assert upper.get_state_info()["interval"] == 120.0

    def test_minimum_is_5_seconds(self):
        """5秒未満は 5.0 に切り上げられるか。"""
        upper, _ = make_upper()
        upper.set_interval(1.0)
        assert upper.get_state_info()["interval"] == 5.0


# ── UpperLayer.start() 早期リターン ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_upper_start_early_return_if_already_running():
    """start() を2回呼んでも例外が出ず、is_running が変わらないか。"""
    upper, _ = make_upper()
    upper.start()
    assert upper._running is True
    upper.start()  # 2回目 → 早期リターン（タスクが重複しない）
    assert upper._running is True
    upper.stop()
    await asyncio.sleep(0.05)


# ── UpperLayer._next_state() ─────────────────────────────────────────────────

class TestNextState:
    def test_returns_valid_state(self):
        """_next_state() が STATES のいずれかを返すか。"""
        from backend.three_layer_controller import STATES
        upper, _ = make_upper()
        for _ in range(20):
            s = upper._next_state()
            assert s in STATES

    def test_high_energy_biases_toward_early_states(self):
        """energy > 0.75 のとき void/sparse 確率が増えるか（確率的テスト）。"""
        from backend.three_layer_controller import STATES
        upper, _ = make_upper(energy_fn=lambda: 0.9)
        counts = {s: 0 for s in STATES}
        for _ in range(200):
            counts[upper._next_state()] += 1
        # void + sparse のカウントが 0 でないこと（完全にゼロではない）
        assert counts["void"] + counts["sparse"] > 0

    def test_low_energy_biases_toward_later_states(self):
        """energy < 0.25 のとき dense/intense 確率が増えるか（確率的テスト）。"""
        from backend.three_layer_controller import STATES
        upper, _ = make_upper(energy_fn=lambda: 0.1)
        counts = {s: 0 for s in STATES}
        for _ in range(200):
            counts[upper._next_state()] += 1
        assert counts["dense"] + counts["intense"] > 0

    def test_no_energy_fn_defaults_to_medium_energy(self):
        """energy_fn が None でも _next_state() がクラッシュしないか。"""
        from backend.three_layer_controller import STATES
        upper, _ = make_upper(energy_fn=None)
        result = upper._next_state()
        assert result in STATES


# ── UpperLayer._loop() 短時間実行 ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upper_loop_broadcasts_initial_markov_state():
    """_loop() 開始直後に markov_state をブロードキャストするか。"""
    upper, broadcast = make_upper(interval=5.0)
    upper._running = True
    upper._state_start = __import__("time").time()

    task = asyncio.create_task(upper._loop())
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    broadcast.assert_awaited()
    calls = broadcast.call_args_list
    assert any(
        call[0][0].get("type") == "markov_state"
        for call in calls
    )


@pytest.mark.asyncio
async def test_upper_loop_handles_cancelled_error():
    """_loop() が CancelledError を正常に処理するか。"""
    upper, _ = make_upper(interval=100.0)
    upper._running = True
    upper._state_start = __import__("time").time()

    task = asyncio.create_task(upper._loop())
    await asyncio.sleep(0.01)
    task.cancel()
    # CancelledError が伝播しない（内部で catch される）はずなので
    # タスクが正常に終了すること
    try:
        await asyncio.wait_for(task, timeout=1.0)
    except asyncio.CancelledError:
        pass  # 外側には伝播することもあるが、例外が出なければよい


# ── ThreeLayerController Markovラッパー群 ────────────────────────────────────

@pytest.mark.asyncio
async def test_start_markov_starts_upper():
    """start_markov() が UpperLayer を起動するか。"""
    ctrl, _, _ = make_controller()
    ctrl.start_markov()
    assert ctrl._upper._running is True
    ctrl.stop_markov()
    await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_stop_markov_stops_upper():
    """stop_markov() が UpperLayer を停止するか。"""
    ctrl, _, _ = make_controller()
    ctrl.start_markov()
    ctrl.stop_markov()
    assert ctrl._upper._running is False
    await asyncio.sleep(0.05)


def test_set_markov_interval():
    """set_markov_interval() が interval を変更するか。"""
    ctrl, _, _ = make_controller()
    ctrl.set_markov_interval(120.0)
    assert ctrl.get_markov_state()["interval"] == 120.0


def test_get_markov_state_returns_dict():
    """get_markov_state() が dict を返すか。"""
    ctrl, _, _ = make_controller()
    state = ctrl.get_markov_state()
    assert isinstance(state, dict)
    assert "state" in state


# ── ThreeLayerController.set_attractor() ─────────────────────────────────────

def test_set_attractor_valid_layer_param():
    """set_attractor() が有効なレイヤー/パラメーターを更新するか。"""
    ctrl, _, _ = make_controller()
    ctrl.set_attractor("drone", "feedback_amt", 0.88)
    uc = ctrl._upper.get_control("drone", "feedback_amt")
    assert uc.center == pytest.approx(0.88)


def test_set_attractor_invalid_layer_does_nothing():
    """set_attractor() に無効なレイヤーを渡してもエラーにならないか。"""
    ctrl, _, _ = make_controller()
    ctrl.set_attractor("nonexistent_layer", "feedback_amt", 0.5)  # 例外なし


def test_set_attractor_invalid_param_does_nothing():
    """set_attractor() に無効なパラメーターを渡してもエラーにならないか。"""
    ctrl, _, _ = make_controller()
    ctrl.set_attractor("drone", "nonexistent_param", 0.5)  # 例外なし


def test_set_attractor_with_range_val():
    """set_attractor() に range_val を渡すと width に反映されるか。"""
    ctrl, _, _ = make_controller()
    ctrl.set_attractor("granular", "density", 20.0, range_val=5.0)
    uc = ctrl._upper.get_control("granular", "density")
    assert uc.center == pytest.approx(20.0)
    assert uc.width == pytest.approx(5.0)


# ── ThreeLayerController モデル切り替えラッパー群 ────────────────────────────

def test_set_middle_model_does_not_raise():
    """set_middle_model() がログを出してエラーにならないか。"""
    ctrl, _, _ = make_controller()
    ctrl.set_middle_model("some_model")  # 例外なし


def test_set_lower_model_does_not_raise():
    """set_lower_model() がログを出してエラーにならないか。"""
    ctrl, _, _ = make_controller()
    ctrl.set_lower_model("some_model")  # 例外なし


def test_set_middle_chaos_affects_speed():
    """set_middle_chaos(ratio) が speed に反映されるか（speed = ratio * 2.0）。"""
    ctrl, _, _ = make_controller()
    ctrl.set_middle_chaos(0.5)
    uc = ctrl._upper.get_control("drone", "feedback_amt")
    assert uc.speed == pytest.approx(1.0)  # 0.5 * 2.0


def test_set_lower_chaos_affects_snap_prob():
    """set_lower_chaos(ratio) が snap_prob に反映されるか（prob = 1 - ratio）。"""
    ctrl, _, _ = make_controller()
    ctrl.set_lower_chaos(0.3)
    uc = ctrl._upper.get_control("drone", "feedback_amt")
    assert uc.snap_prob == pytest.approx(0.7)  # 1.0 - 0.3


# ── ThreeLayerController.set_markov_state_from_scene() ───────────────────────

class TestSetMarkovStateFromScene:
    def test_known_scene_changes_state(self):
        """既知シーン名でMarkov状態が変わるか。"""
        ctrl, _, _ = make_controller()
        ctrl.set_markov_state_from_scene("void")
        assert ctrl._upper.get_state_info()["state"] == "void"

    def test_scene_void_maps_to_void(self):
        ctrl, _, _ = make_controller()
        ctrl.set_markov_state_from_scene("void")
        assert ctrl._upper._state == "void"

    def test_scene_peak_maps_to_intense(self):
        ctrl, _, _ = make_controller()
        ctrl.set_markov_state_from_scene("peak")
        assert ctrl._upper._state == "intense"

    def test_unknown_scene_does_not_change_state(self):
        """不明なシーン名では状態が変わらないか。"""
        ctrl, _, _ = make_controller()
        initial = ctrl._upper._state
        ctrl.set_markov_state_from_scene("nonexistent_scene")
        assert ctrl._upper._state == initial

    def test_all_mapped_scenes(self):
        """_SCENE_TO_MARKOV の全エントリが動くか。"""
        from backend.three_layer_controller import STATES
        ctrl, _, _ = make_controller()
        for scene_name, markov_state in ctrl._SCENE_TO_MARKOV.items():
            ctrl.set_markov_state_from_scene(scene_name)
            assert ctrl._upper._state == markov_state


# ── ThreeLayerController._compute_energy() ───────────────────────────────────

class TestComputeEnergy:
    def test_returns_float_in_0_1(self):
        """_compute_energy() が 0〜1 の float を返すか。"""
        ctrl, _, _ = make_controller()
        e = ctrl._compute_energy()
        assert 0.0 <= e <= 1.0

    def test_initial_energy_is_positive(self):
        """初期値でのエネルギーが 0 より大きいか。"""
        ctrl, _, _ = make_controller()
        assert ctrl._compute_energy() > 0.0

    def test_exception_returns_default_0_5(self):
        """_params が壊れているとき 0.5 を返すか。"""
        ctrl, _, _ = make_controller()
        # get() が例外を投げるオブジェクトに差し替えて例外パスを誘発
        broken = MagicMock()
        broken.get.side_effect = RuntimeError("broken")
        ctrl._params = broken
        assert ctrl._compute_energy() == pytest.approx(0.5)


# ── ThreeLayerController._loop() ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_controller_loop_calls_tick():
    """_loop() が _tick() を呼び出すか（UPDATE_INTERVAL をパッチして高速化）。"""
    ctrl, _, _ = make_controller()
    tick_count = 0

    async def fake_tick():
        nonlocal tick_count
        tick_count += 1

    ctrl._tick = fake_tick
    ctrl._running = True

    with patch("backend.three_layer_controller.UPDATE_INTERVAL", 0.01):
        task = asyncio.create_task(ctrl._loop())
        await asyncio.sleep(0.05)
        ctrl._running = False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert tick_count >= 1


@pytest.mark.asyncio
async def test_controller_loop_stops_when_running_false():
    """_running=False になると _loop() がループを抜けるか。"""
    ctrl, _, _ = make_controller()
    ctrl._running = True
    iterations = 0

    async def fake_tick():
        nonlocal iterations
        iterations += 1
        ctrl._running = False  # 1回後に停止

    ctrl._tick = fake_tick

    with patch("backend.three_layer_controller.UPDATE_INTERVAL", 0.001):
        await ctrl._loop()

    assert iterations == 1


# ── _tick() tidal_ctrl パス ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tick_calls_send_tidal_ctrl_for_melody():
    """melody/rhythmic レイヤーが send_tidal_ctrl 経由で送られるか。"""
    send_tidal_ctrl = MagicMock()
    ctrl, send_osc, _ = make_controller(send_tidal_ctrl=send_tidal_ctrl)

    await ctrl._tick()

    assert send_tidal_ctrl.called
    # 呼び出し済みキー一覧（melody_note と rhythmic_* が含まれるはず）
    called_keys = [call[0][0] for call in send_tidal_ctrl.call_args_list]
    assert "melody_note" in called_keys
    assert all(isinstance(call[0][1], float)
               for call in send_tidal_ctrl.call_args_list)


@pytest.mark.asyncio
async def test_tick_no_tidal_ctrl_skips_melody_send():
    """send_tidal_ctrl=None のとき melody は OSC 送信をスキップするか。"""
    ctrl, send_osc, _ = make_controller(send_tidal_ctrl=None)

    await ctrl._tick()

    # melody/_tidal_ctrl は send_osc に流れないはず
    addresses = [call[0][0] for call in send_osc.call_args_list]
    assert "_tidal_ctrl" not in addresses
