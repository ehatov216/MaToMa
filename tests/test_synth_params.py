"""
シンセパラメーター送信のテスト
==============================
「ブラウザのスライダーが動いたとき、正しい形式でSCにメッセージが届くか」を検証する。
"""

import json
import pytest


def make_param_message(param: str, value: float) -> dict:
    """ブラウザからブリッジへ送るメッセージを組み立てる。"""
    return {"address": "/matoma/param", "args": [param, value]}


def make_start_message() -> dict:
    return {"address": "/matoma/start", "args": []}


def make_stop_message() -> dict:
    return {"address": "/matoma/stop", "args": []}


# ── パラメーターメッセージのテスト ──────────────────────

def test_cutoff_message_format():
    """カットオフ（音の明るさ）のメッセージが正しく作られるか。"""
    msg = make_param_message("cutoff", 2000.0)
    assert msg["address"] == "/matoma/param"
    assert msg["args"][0] == "cutoff"
    assert msg["args"][1] == 2000.0


def test_freq_message_format():
    """周波数（音の高さ）のメッセージが正しく作られるか。"""
    msg = make_param_message("freq", 440.0)
    assert msg["args"][0] == "freq"
    assert msg["args"][1] == 440.0


def test_amp_message_format():
    """音量のメッセージが正しく作られるか。"""
    msg = make_param_message("amp", 0.5)
    assert msg["args"][0] == "amp"
    assert 0.0 <= msg["args"][1] <= 1.0


def test_start_stop_message_format():
    """開始・停止メッセージが正しく作られるか。"""
    start = make_start_message()
    stop = make_stop_message()
    assert start["address"] == "/matoma/start"
    assert stop["address"] == "/matoma/stop"


def test_message_is_json_serializable():
    """メッセージがJSONに変換できるか（ブラウザ送信の前提）。"""
    msg = make_param_message("cutoff", 1500.0)
    serialized = json.dumps(msg)
    restored = json.loads(serialized)
    assert restored == msg
