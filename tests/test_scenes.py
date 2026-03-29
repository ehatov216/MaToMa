"""
シーン管理のテスト
==================
「シーンのロードと切り替えが正しく動くか」を検証する。

Phase 4以降はシーンが「引力点と揺れ幅」ベースに変わったため、
テストも新スキーマに合わせて更新している。
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
    """各シーンに必要なキーが揃っているか（Phase 4形式）。"""
    from backend.scenes import load_scenes
    for scene in load_scenes():
        assert "name" in scene, f"{scene.get('name', '?')}: name がない"
        assert "drone" in scene, f"{scene['name']}: drone がない"
        assert "granular" in scene, f"{scene['name']}: granular がない"
        assert "rhythmic" in scene, f"{scene['name']}: rhythmic がない"


def test_each_scene_drone_has_attractor_keys():
    """各シーンのdroneに引力点キーが揃っているか。"""
    from backend.scenes import load_scenes
    required_drone_keys = [
        "freq_attractor",
        "feedback_attractor",
        "shimmer_attractor",
        "room_attractor",
    ]
    for scene in load_scenes():
        drone = scene["drone"]
        for key in required_drone_keys:
            assert key in drone, f"{scene['name']} / drone: {key} がない"


def test_each_scene_granular_has_attractor_keys():
    """各シーンのgranularに引力点キーが揃っているか。"""
    from backend.scenes import load_scenes
    required_keys = ["density_attractor", "spray_attractor", "room_attractor"]
    for scene in load_scenes():
        granular = scene["granular"]
        for key in required_keys:
            assert key in granular, f"{scene['name']} / granular: {key} がない"


def test_scene_drone_values_are_in_range():
    """Droneの引力点が有効範囲内か。"""
    from backend.scenes import load_scenes
    for scene in load_scenes():
        drone = scene["drone"]
        assert 20 <= drone["freq_attractor"] <= 200, \
            f"{scene['name']}: drone freq_attractor out of range"
        assert 0.0 <= drone["feedback_attractor"] <= 1.0, \
            f"{scene['name']}: drone feedback_attractor out of range"
        assert 0.0 <= drone["shimmer_attractor"] <= 1.0, \
            f"{scene['name']}: drone shimmer_attractor out of range"
        assert 0.0 <= drone["room_attractor"] <= 1.0, \
            f"{scene['name']}: drone room_attractor out of range"


def test_scene_rhythmic_prob_in_range():
    """Rhythmicの確率引力点が0〜1の範囲内か。"""
    from backend.scenes import load_scenes
    for scene in load_scenes():
        rhythmic = scene["rhythmic"]
        assert 0.0 <= rhythmic["prob_attractor"] <= 1.0, \
            f"{scene['name']}: rhythmic prob_attractor out of range"


# ── シーン取得テスト ──────────────────────────────────

def test_get_scene_by_name():
    """名前でシーンを取得できるか。"""
    from backend.scenes import load_scenes, get_scene
    first_name = load_scenes()[0]["name"]
    scene = get_scene(first_name)
    assert scene is not None
    assert scene["name"] == first_name


def test_get_scene_unknown_name_returns_none():
    """存在しない名前を指定したときNoneを返すか。"""
    from backend.scenes import get_scene
    assert get_scene("存在しないシーン") is None


# ── シーン切り替えOSCメッセージのテスト ──────────────

def test_scene_to_osc_messages_drone():
    """シーンのdrone引力点がOSCメッセージに変換されるか。"""
    from backend.scenes import scene_to_osc_messages
    scene = {
        "name": "テスト",
        "drone": {
            "freq_attractor": 55.0,
            "feedback_attractor": 0.25,
            "shimmer_attractor": 0.4,
            "room_attractor": 0.75,
        },
        "granular": {},
        "rhythmic": {},
    }
    messages = scene_to_osc_messages(scene)

    drone_msgs = [m for m in messages if m["address"] == "/matoma/drone/param"]
    assert len(drone_msgs) == 4

    params = {m["args"][0]: m["args"][1] for m in drone_msgs}
    assert params["freq"] == 55.0
    assert params["feedback_amt"] == 0.25
    assert params["shimmer"] == 0.4
    assert params["room"] == 0.75


def test_scene_to_osc_messages_granular():
    """シーンのgranular引力点がOSCメッセージに変換されるか。"""
    from backend.scenes import scene_to_osc_messages
    scene = {
        "name": "テスト",
        "drone": {},
        "granular": {
            "density_attractor": 12.0,
            "spray_attractor": 0.5,
            "room_attractor": 0.6,
        },
        "rhythmic": {},
    }
    messages = scene_to_osc_messages(scene)

    granular_msgs = [m for m in messages if m["address"] == "/matoma/granular/param"]
    assert len(granular_msgs) == 3

    params = {m["args"][0]: m["args"][1] for m in granular_msgs}
    assert params["density"] == 12.0
    assert params["spray"] == 0.5
    assert params["room"] == 0.6


def test_scene_to_osc_messages_rhythmic():
    """シーンのrhythmic引力点がOSCメッセージに変換されるか。"""
    from backend.scenes import scene_to_osc_messages
    scene = {
        "name": "テスト",
        "drone": {},
        "granular": {},
        "rhythmic": {
            "prob_attractor": 0.3,
        },
    }
    messages = scene_to_osc_messages(scene)

    rhythmic_msgs = [m for m in messages if m["address"] == "/matoma/rhythmic/param"]
    assert len(rhythmic_msgs) == 1
    assert rhythmic_msgs[0]["args"][0] == "prob"
    assert rhythmic_msgs[0]["args"][1] == 0.3
