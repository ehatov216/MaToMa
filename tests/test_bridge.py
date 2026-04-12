"""
ブリッジのユニットテスト
========================
「SCから届いたOSCメッセージが正しくブラウザへ届くか」を検証する。
実際のネットワーク通信は使わず、関数の動作だけをテストする。
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── broadcast 関数のテスト ──────────────────────────────

@pytest.mark.asyncio
async def test_broadcast_sends_to_all_clients():
    """接続中の全ブラウザにメッセージが届くか。"""
    from backend.bridge import broadcast, connected_clients

    # 偽のWebSocketクライアントを2つ用意
    client_a = AsyncMock()
    client_b = AsyncMock()
    connected_clients.clear()
    connected_clients.add(client_a)
    connected_clients.add(client_b)

    message = {"address": "/matoma/test", "args": [0.5]}
    await broadcast(message)

    expected = json.dumps(message, ensure_ascii=False)
    client_a.send.assert_awaited_once_with(expected)
    client_b.send.assert_awaited_once_with(expected)

    connected_clients.clear()


@pytest.mark.asyncio
async def test_broadcast_does_nothing_when_no_clients():
    """ブラウザが0台のとき、エラーにならないか。"""
    from backend.bridge import broadcast, connected_clients

    connected_clients.clear()
    # 例外が出なければOK
    await broadcast({"address": "/matoma/test", "args": []})


# ── on_osc_message 関数のテスト ────────────────────────

@pytest.mark.asyncio
async def test_on_osc_message_ignores_unrelated_messages():
    """SCからの無関係なOSCメッセージで状態が壊れないか。"""
    from backend import bridge

    bridge.sc_ready = False
    bridge.on_osc_message("/matoma/param/cutoff", 0.75)

    assert bridge.sc_ready is False


# ── メッセージ形式のテスト ──────────────────────────────

def test_osc_message_format():
    """OSCメッセージがJSONに正しく変換されるか。"""
    address = "/matoma/param/cutoff"
    args = [0.5, "test", 42]

    message = {"address": address, "args": args}
    serialized = json.dumps(message, ensure_ascii=False)
    deserialized = json.loads(serialized)

    assert deserialized["address"] == address
    assert deserialized["args"] == args


@pytest.mark.asyncio
async def test_handle_play_auto_starts_tidal_when_needed():
    """play 受信時に Tidal が未起動なら自動起動を試みる。"""
    from backend import bridge

    fake_tidal = MagicMock()
    fake_tidal.is_running = False
    fake_tidal.start = MagicMock(return_value=True)
    fake_tidal.set_tempo = MagicMock()
    fake_tidal.evaluate = MagicMock()

    fake_record = MagicMock()
    fake_record.track_id = "track-1"
    fake_record.bpm = 128.0
    fake_record.key_root = "C"
    fake_record.key_mode = "major"

    fake_seed = MagicMock(
        bpm=128.0,
        rhythm_lines=["d1"],
        harmony_lines=["d2"],
        melody_lines=["d3"],
        source_track_id="track-1",
        key_root="C",
        key_mode="major",
    )

    websocket = AsyncMock()

    with (
        patch.object(bridge, "tidal", fake_tidal),
        patch.object(bridge, "load_record", return_value=fake_record),
        patch.object(bridge, "generate_tidal_seed", return_value=fake_seed),
        patch.object(bridge, "seed_to_dict", return_value={
            "track_id": "track-1",
            "bpm": 128.0,
            "key_root": "C",
            "key_mode": "major",
            "synth": "matoma_lead",
            "all_lines": ["d1", "d2", "d3"],
        }),
        patch.object(bridge, "broadcast", new=AsyncMock()),
    ):
        await bridge._handle_play("track-1", websocket)

    fake_tidal.start.assert_called_once()
    fake_tidal.set_tempo.assert_called_once_with(128.0)
    fake_tidal.evaluate.assert_called_once_with("d1\nd2\nd3")
    websocket.send.assert_not_called()
