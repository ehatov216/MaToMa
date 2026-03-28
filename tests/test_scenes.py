"""
シーン管理のテスト
==================
「シーンのロードと切り替えが正しく動くか」を検証する。
"""

import json
import pytest
from pathlib import Path


# ── シーンのロードテスト ──────────────────────────────

def test_load_scenes_returns_list():
    """scenes.json からシーンのリストが読み込めるか。"""
    from backend.scenes import load_scenes
    scenes = load_scenes()
    assert isinstance(scenes, list)
    assert len(scenes) > 0


def test_each_scene_has_required_keys():
    """各シーンに必要なキーが揃っているか。"""
    from backend.scenes import load_scenes
    for scene in load_scenes():
        assert "name" in scene
        assert "freq" in scene
        assert "cutoff" in scene
        assert "amp" in scene


def test_scene_values_are_in_range():
    """各シーンのパラメーター値が有効範囲内か。"""
    from backend.scenes import load_scenes
    for scene in load_scenes():
        assert 55 <= scene["freq"] <= 880,   f"{scene['name']}: freq out of range"
        assert 200 <= scene["cutoff"] <= 8000, f"{scene['name']}: cutoff out of range"
        assert 0.0 <= scene["amp"] <= 1.0,   f"{scene['name']}: amp out of range"


# ── シーン取得テスト ──────────────────────────────────

def test_get_scene_by_name():
    """名前でシーンを取得できるか。"""
    from backend.scenes import get_scene
    scene = get_scene("暗い")
    assert scene is not None
    assert scene["name"] == "暗い"


def test_get_scene_unknown_name_returns_none():
    """存在しない名前を指定したときNoneを返すか。"""
    from backend.scenes import get_scene
    assert get_scene("存在しないシーン") is None


# ── シーン切り替えOSCメッセージのテスト ──────────────

def test_scene_to_osc_messages():
    """シーンをOSCメッセージのリストに変換できるか。"""
    from backend.scenes import scene_to_osc_messages
    scene = {"name": "テスト", "freq": 220.0, "cutoff": 1000.0, "amp": 0.5}
    messages = scene_to_osc_messages(scene)

    assert len(messages) == 3
    addrs = [m["address"] for m in messages]
    assert all(a == "/matoma/param" for a in addrs)

    params = {m["args"][0]: m["args"][1] for m in messages}
    assert params["freq"] == 220.0
    assert params["cutoff"] == 1000.0
    assert params["amp"] == 0.5
