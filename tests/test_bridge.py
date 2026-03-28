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
async def test_on_osc_message_creates_broadcast_task():
    """SCからのOSCメッセージ受信時にbroadcastが呼ばれるか。"""
    from backend import bridge

    broadcast_calls = []

    async def fake_broadcast(message):
        broadcast_calls.append(message)

    loop = asyncio.get_event_loop()

    with patch.object(bridge, "broadcast", side_effect=fake_broadcast):
        bridge.on_osc_message("/matoma/param/cutoff", 0.75)
        # タスクが実行される時間を与える
        await asyncio.sleep(0.01)

    assert len(broadcast_calls) == 1
    assert broadcast_calls[0]["address"] == "/matoma/param/cutoff"
    assert broadcast_calls[0]["args"] == [0.75]


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
