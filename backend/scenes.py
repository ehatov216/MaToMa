"""
MaToMa シーン管理
=================
ライブのシーン（プリセット）を管理する。
scenes.json を編集することでClaudeがセッション間にシーンを追加・変更できる。

シーンの定義方針（Phase 4以降）:
  シーンは「具体的な値」ではなく「引力点（attractor）と揺れ幅（range）」で定義する。
  ChaosEngine がこれを参照して、パラメーターを自律的にドリフトさせる。
"""

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

SCENES_FILE = Path(__file__).parent / "scenes.json"


def load_scenes() -> list[dict]:
    """scenes.json からシーン一覧を読み込む。"""
    try:
        with open(SCENES_FILE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        log.error(f"scenes.json が見つかりません: {SCENES_FILE}")
        return []
    except json.JSONDecodeError as e:
        log.error(f"scenes.json のパースに失敗しました: {e}")
        return []


def get_scene(name: str) -> dict | None:
    """英語id または日本語nameでシーンを取得する。見つからなければNoneを返す。

    フロントエンドは英語id（例: "void", "warm"）を送信するため、
    まずidでルックアップし、次にnameで検索する。
    """
    for scene in load_scenes():
        if scene.get("id") == name or scene["name"] == name:
            return scene
    return None


def scene_to_osc_messages(scene: dict) -> list[dict]:
    """シーンをOSCメッセージのリストに変換する。

    Phase 4以降のシーン形式（引力点ベース）に対応する。
    ChaosEngine の set_scene() を補完するために、
    SCに直接送れる代表値（引力点の値）をOSCメッセージとして返す。

    返却形式: [{"address": "/matoma/...", "args": [...]}]
    """
    messages: list[dict] = []

    # Drone の引力点を代表値としてSCへ送信する
    drone = scene.get("drone", {})
    drone_param_map = {
        "freq":         "freq_attractor",
        "feedback_amt": "feedback_attractor",
        "shimmer":      "shimmer_attractor",
        "room":         "room_attractor",
    }
    for sc_key, scene_key in drone_param_map.items():
        if scene_key in drone:
            messages.append({
                "address": "/matoma/drone/param",
                "args": [sc_key, float(drone[scene_key])],
            })

    # Granular の引力点を代表値として送信する
    granular = scene.get("granular", {})
    granular_param_map = {
        "density": "density_attractor",
        "spray":   "spray_attractor",
        "room":    "room_attractor",
    }
    for sc_key, scene_key in granular_param_map.items():
        if scene_key in granular:
            messages.append({
                "address": "/matoma/granular/param",
                "args": [sc_key, float(granular[scene_key])],
            })

    # Organic Coupling: シーン切り替え時にドローン↔グラニュラーの連動強度を設定する
    # 0.0 = 完全独立（深淵シーン） / 1.0 = 完全オーガニック（崩壊シーン）
    # SC側の /matoma/coupling OSCdef が ~couplingBus を更新する
    if "organic_coupling" in scene:
        messages.append({
            "address": "/matoma/coupling",
            "args": [float(scene["organic_coupling"])],
        })

    # Rhythmic の引力点を送信する
    rhythmic = scene.get("rhythmic", {})
    if "prob_attractor" in rhythmic:
        messages.append({
            "address": "/matoma/rhythmic/param",
            "args": ["prob", float(rhythmic["prob_attractor"])],
        })

    # レイヤーの開始・停止（scenes.json の layers フィールドで制御）
    layers = scene.get("layers", {})

    # Granular: true → start、false → stop
    if layers.get("granular") is True:
        messages.append({"address": "/matoma/granular/start", "args": []})
    elif layers.get("granular") is False:
        messages.append({"address": "/matoma/granular/stop", "args": []})

    # Turing Machine: true → start、false → stop
    if layers.get("turing") is True:
        messages.append({"address": "/matoma/rhythmic/start", "args": []})
    elif layers.get("turing") is False:
        messages.append({"address": "/matoma/rhythmic/stop", "args": []})

    # Spectral: true → start（パラメーター付き）、false → stop
    spectral = scene.get("spectral", {})
    if layers.get("spectral") is True:
        for key, val in spectral.items():
            messages.append({
                "address": "/matoma/spectral/param",
                "args": [key, float(val)],
            })
        messages.append({"address": "/matoma/spectral/start", "args": []})
    elif layers.get("spectral") is False:
        messages.append({"address": "/matoma/spectral/stop", "args": []})

    return messages
