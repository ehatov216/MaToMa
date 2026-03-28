"""
MaToMa シーン管理
=================
ライブのシーン（プリセット）を管理する。
scenes.json を編集することでClaudeがセッション間にシーンを追加・変更できる。
"""

import json
from pathlib import Path

SCENES_FILE = Path(__file__).parent / "scenes.json"


def load_scenes() -> list[dict]:
    """scenes.json からシーン一覧を読み込む。"""
    with open(SCENES_FILE, encoding="utf-8") as f:
        return json.load(f)


def get_scene(name: str) -> dict | None:
    """名前でシーンを取得する。見つからなければNoneを返す。"""
    for scene in load_scenes():
        if scene["name"] == name:
            return scene
    return None


def scene_to_osc_messages(scene: dict) -> list[dict]:
    """シーンをOSCメッセージのリストに変換する。"""
    params = ["freq", "cutoff", "amp"]
    return [
        {"address": "/matoma/param", "args": [p, float(scene[p])]}
        for p in params
        if p in scene
    ]
