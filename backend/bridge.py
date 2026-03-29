"""
MaToMa ブリッジ
==============
SC（SuperCollider）から来るOSCメッセージを受け取り、
WebSocket経由でブラウザに転送する中継役。

流れ:
  SC → OSC(UDP) → このファイル → WebSocket → ブラウザ
  ブラウザ → WebSocket → このファイル → OSC(UDP) → SC
"""

import asyncio
import json
import logging
import os
import shutil
import signal
import subprocess
import tempfile
import uuid
from pathlib import Path

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient


def get_audio_output_devices() -> list[str]:
    """
    macOS の system_profiler から出力チャンネルを持つオーディオデバイス名を取得する。
    SC の OSC 経由では日本語名が途切れるため、Python 側で直接取得する。
    """
    try:
        r = subprocess.run(
            ["system_profiler", "SPAudioDataType", "-json"],
            capture_output=True, text=True, timeout=5,
        )
        data = json.loads(r.stdout)
        items = data.get("SPAudioDataType", [{}])[0].get("_items", [])
        return [
            item["_name"]
            for item in items
            if item.get("coreaudio_device_output", 0) > 0
        ]
    except Exception as e:
        log.warning(f"オーディオデバイス取得失敗: {e}")
        return []
import websockets
from scenes import get_scene, scene_to_osc_messages
from autonomous import AutonomousMode, ChaosEngine
from tidal_controller import TidalController
from tidal_patterns import make_chord_pattern, make_arp_pattern, make_drum_pattern
from sequencer import TuringSequencer

# ── PID ファイル ─────────────────────────────────────────
PID_FILE = Path(__file__).parent / ".bridge.pid"

# ── ポート設定 ──────────────────────────────────────────
OSC_LISTEN_HOST = "127.0.0.1"
OSC_LISTEN_PORT = 9000   # SCからPythonへ（このポートで待ち受ける）
SC_HOST = "127.0.0.1"
SC_PORT = 57200  # PythonからSCへ（MaToMa専用ポート）
WS_HOST = "localhost"
WS_PORT = 8765   # ブラウザとのWebSocket

# SCの起動タイムアウト（秒）
SC_BOOT_TIMEOUT = 60
# ────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

# 接続中のブラウザを管理するセット
connected_clients: set = set()

# SCへメッセージを送るクライアント
sc_client = SimpleUDPClient(SC_HOST, SC_PORT)

# 自律モード（broadcast は後で関数参照として渡す）
autonomous: AutonomousMode

# カオスエンジン（Dejavu パターンによる記憶付きドリフト）
chaos_engine: ChaosEngine

# Tidal Cycles コントローラー
tidal: TidalController

# Turing Machine ステップシーケンサー
sequencer: TuringSequencer

# SC プロセス
sc_process = None

# SC が ready かどうか
sc_ready = False


def find_sclang() -> str | None:
    """sclang の実行パスを探す。"""
    candidates = [
        shutil.which("sclang"),
        "/Applications/SuperCollider.app/Contents/MacOS/sclang",
        "/usr/local/bin/sclang",
        "/usr/bin/sclang",
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


async def start_sc() -> bool:
    """
    SuperCollider を起動する。
    既存プロセスをkillしてから起動し、/matoma/ready が届くまで待機する。
    戻り値: 起動成功 = True
    """
    global sc_process, sc_ready

    # 既存SCプロセスをkill（ポート競合を防ぐ）
    log.info("既存SCプロセスをkill中...")
    subprocess.run(["pkill", "-f", "sclang"], capture_output=True)
    subprocess.run(["pkill", "-f", "scsynth"], capture_output=True)
    await asyncio.sleep(1.5)

    sclang = find_sclang()
    if not sclang:
        log.error("sclang が見つかりません。SuperCollider をインストールしてください。")
        await broadcast({
            "type": "sc_error",
            "message": "sclang が見つかりません。SuperCollider をインストールしてください。",
        })
        return False

    sc_script = Path(__file__).parent.parent / "sc" / "run_headless.scd"
    if not sc_script.exists():
        log.error(f"SCスクリプトが見つかりません: {sc_script}")
        return False

    log.info(f"SC起動中: {sclang} {sc_script}")
    sc_ready = False

    try:
        sc_process = await asyncio.create_subprocess_exec(
            sclang, str(sc_script),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except Exception as e:
        log.error(f"SC起動失敗: {e}")
        await broadcast({"type": "sc_error", "message": f"SC起動失敗: {e}"})
        return False

    # SC のログを非同期で読み続けるタスクを起動
    asyncio.create_task(_pipe_sc_output(sc_process))

    # /matoma/ready が届くまで待機
    log.info(f"SC readyを待機中（最大{SC_BOOT_TIMEOUT}秒）...")
    await broadcast({"type": "sc_booting", "message": "SC起動中..."})
    try:
        await asyncio.wait_for(_wait_sc_ready(), timeout=SC_BOOT_TIMEOUT)
        log.info("SC起動完了")
        return True
    except asyncio.TimeoutError:
        log.error("SC起動タイムアウト")
        await broadcast({
            "type": "sc_error",
            "message": f"SC起動タイムアウト（{SC_BOOT_TIMEOUT}秒）。run_headless.scd を確認してください。",
        })
        return False


async def _wait_sc_ready():
    """sc_ready フラグが True になるまで待機する。"""
    while not sc_ready:
        await asyncio.sleep(0.2)


async def _pipe_sc_output(proc):
    """SC プロセスの stdout を logger に流し続ける。"""
    if proc.stdout is None:
        return
    async for line in proc.stdout:
        text = line.decode("utf-8", errors="replace").rstrip()
        if text:
            log.info(f"[SC] {text}")


async def broadcast(message: dict) -> None:
    """接続中の全ブラウザにJSONを送る。"""
    if not connected_clients:
        return
    data = json.dumps(message, ensure_ascii=False)
    await asyncio.gather(
        *(ws.send(data) for ws in connected_clients),
        return_exceptions=True,
    )


def on_osc_message(address: str, *args) -> None:
    """SCからのOSCメッセージを受け取りブラウザへ転送する。"""
    global sc_ready

    if address == "/matoma/audio/devices":
        # SC からの音声デバイスリストは日本語名が途切れるため、
        # デバイスリストは Python 側で system_profiler から取得する。
        # current_device（SC が起動時に使ったデバイス名）は参考として受け取る。
        config_path = Path(__file__).parent / "audio_device.txt"
        current_device = config_path.read_text(encoding="utf-8").strip() if config_path.exists() else ""
        devices = get_audio_output_devices()
        log.info(f"音声デバイスリスト(Python取得): current={current_device!r} devices={devices}")
        asyncio.get_running_loop().create_task(
            broadcast({
                "type": "audio_devices",
                "current": current_device,
                "devices": devices,
            })
        )
        return

    if address == "/matoma/ready":
        sc_ready = True
        log.info("SC ready 受信 → ブラウザへ通知")
        # SC 起動完了と同時に ChaosEngine を自動スタート
        # （これがないとパラメーターが一切変化しない）
        chaos_engine.start()
        log.info("ChaosEngine 自動スタート")
        asyncio.get_running_loop().create_task(
            broadcast({"type": "sc_ready", "message": "SC起動完了"})
        )
        return

    if address == "/matoma/granular/not_ready":
        log.warning("グラニュラー: バッファ未ロード状態でSTARTが押されました")
        asyncio.get_running_loop().create_task(
            broadcast({
                "type": "granular_load_error",
                "message": "バッファ未ロード。先にファイルを選択してください",
            })
        )
        return

    if address == "/matoma/granular/loaded":
        path = str(args[0]) if args else ""
        num_frames = int(args[1]) if len(args) > 1 else 0
        sample_rate = float(args[2]) if len(args) > 2 else 44100.0
        duration = (
            round(num_frames / sample_rate, 2) if sample_rate > 0 else 0.0
        )
        log.info(f"グラニュラーロード完了: {path} ({duration}s)")
        asyncio.get_running_loop().create_task(
            broadcast({
                "type": "granular_loaded",
                "path": path,
                "num_frames": num_frames,
                "sample_rate": sample_rate,
                "duration": duration,
            })
        )
        return

    log.info(f"OSC受信: {address}  args={args}")
    asyncio.get_running_loop().create_task(
        broadcast({"address": address, "args": list(args)})
    )


async def ws_handler(websocket) -> None:
    """ブラウザからのWebSocket接続を管理する。

    ブラウザから届いたメッセージはそのままSCへOSC転送する。
    形式: {"address": "/matoma/param", "args": ["cutoff", 0.5]}
    """
    connected_clients.add(websocket)
    log.info(
        f"ブラウザ接続: {websocket.remote_address}  合計={len(connected_clients)}"
    )

    # 接続直後に現在のSC状態を通知する
    await websocket.send(json.dumps({
        "type": "sc_status",
        "ready": sc_ready,
        "message": "SC起動完了" if sc_ready else "SC未起動",
    }))

    # SC が起動済みならデバイスリストを要求する
    if sc_ready:
        sc_client.send_message("/matoma/audio/get_devices", [])

    try:
        async for raw in websocket:
            try:
                msg = json.loads(raw)
                address = msg.get("address", "/matoma/unknown")
                args = msg.get("args", [])

                if address == "/matoma/scene":
                    # シーン切り替え：全パラメーターをまとめてSCへ送信
                    scene_name = args[0] if args else ""
                    scene = get_scene(scene_name)
                    if scene:
                        for osc in scene_to_osc_messages(scene):
                            sc_client.send_message(osc["address"], osc["args"])
                        # ChaosEngine の引力点をシーンに合わせて更新する
                        chaos_engine.set_scene(scene)
                        await broadcast({"type": "scene_changed", "scene": scene})
                        log.info(f"シーン切り替え: {scene_name}")
                    else:
                        log.warning(f"シーンが見つかりません: {scene_name}")

                elif address == "/matoma/chaos/state":
                    # カオスエンジンの現在状態をブラウザへ送る
                    await broadcast({
                        "type": "chaos_state",
                        "state": chaos_engine.get_state(),
                    })

                elif address == "/matoma/all/stop":
                    chaos_engine.stop()
                    autonomous.stop()
                    sc_client.send_message("/matoma/all/stop", [])
                    log.info("全停止")
                    await broadcast({"type": "all_stopped"})

                elif address == "/matoma/all/restart":
                    chaos_engine.stop()
                    autonomous.stop()
                    sc_client.send_message("/matoma/all/restart", [])
                    log.info("再セットアップ")
                    await broadcast({"type": "restarting"})

                elif address == "/matoma/chaos/attractor":
                    # 引力点を手動で設定する
                    # args: [layer, param, attractor, range_opt]
                    if len(args) >= 3:
                        layer_name = str(args[0])
                        param_name = str(args[1])
                        attractor_val = float(args[2])
                        range_val = float(args[3]) if len(args) >= 4 else None
                        chaos_engine.set_attractor(
                            layer_name, param_name, attractor_val, range_val
                        )
                        log.info(
                            f"引力点設定: {layer_name}/{param_name}"
                            f" → {attractor_val} (range={range_val})"
                        )

                elif address == "/matoma/chaos/start":
                    # カオスエンジンを開始する
                    chaos_engine.start()
                    log.info("ChaosEngine 開始")
                    await broadcast({"type": "chaos_started"})

                elif address == "/matoma/chaos/stop":
                    # カオスエンジンを停止する
                    chaos_engine.stop()
                    log.info("ChaosEngine 停止")
                    await broadcast({"type": "chaos_stopped"})

                elif address.startswith("/matoma/autonomous/"):
                    # 自律モードの制御
                    sub = address[len("/matoma/autonomous/"):]
                    if sub == "start":
                        autonomous.start()
                        log.info("自律モード開始")
                    elif sub == "stop":
                        autonomous.stop()
                        log.info("自律モード停止")
                    elif sub == "mode" and args:
                        autonomous.set_mode(str(args[0]))
                        log.info(f"自律モード変更: {args[0]}")
                    elif sub == "speed" and args:
                        autonomous.set_speed(float(args[0]))
                        log.info(f"自律モード速度: {args[0]}")
                    elif sub == "target" and len(args) >= 2:
                        autonomous.set_target(str(args[0]), float(args[1]))
                        log.info(f"目標値設定: {args[0]} = {args[1]}")
                    elif sub == "tidal_auto" and args:
                        enabled = bool(args[0])
                        autonomous.set_tidal_auto(enabled)
                        log.info(f"Tidal自律モード: {'ON' if enabled else 'OFF'}")
                    elif sub == "progression" and args:
                        autonomous.set_progression(str(args[0]))
                        log.info(f"コード進行変更: {args[0]}")
                    elif sub == "trig_prob" and args:
                        autonomous.set_trig_prob(float(args[0]))
                        log.info(f"TRIG確率: {args[0]}")
                    elif sub == "dejavu_prob" and args:
                        autonomous.set_dejavu_prob(float(args[0]))
                        log.info(f"Dejavu確率: {args[0]}")
                    elif sub == "dejavu_len" and args:
                        autonomous.set_dejavu_len(int(args[0]))
                        log.info(f"Dejavu長さ: {args[0]}")

                elif address == "/matoma/audio/get_devices":
                    # デバイスリストは Python 側で取得（SC OSC 経由では名前が途切れるため）
                    config_path = Path(__file__).parent / "audio_device.txt"
                    current_device = config_path.read_text(encoding="utf-8").strip() if config_path.exists() else ""
                    devices = get_audio_output_devices()
                    log.info(f"デバイスリスト要求(Python取得): current={current_device!r} devices={devices}")
                    await broadcast({
                        "type": "audio_devices",
                        "current": current_device,
                        "devices": devices,
                    })

                elif address == "/matoma/audio/set_device":
                    device_name = str(args[0]) if args else ""
                    config_path = Path(__file__).parent / "audio_device.txt"
                    config_path.write_text(device_name, encoding="utf-8")
                    log.info(f"音声デバイス設定を保存: {device_name!r}")
                    await broadcast({
                        "type": "sc_booting",
                        "message": f"デバイス「{device_name or 'デフォルト'}」へ切替のため SC を再起動中...",
                    })
                    asyncio.create_task(start_sc())

                elif address.startswith("/matoma/tidal/"):
                    await _handle_tidal(address, args, websocket)

                elif address == "/matoma/granular/browse":
                    await _handle_granular_browse(websocket)

                elif address.startswith("/matoma/seq/"):
                    await _handle_seq(address, args, websocket)

                elif address.startswith("/matoma/spectral/"):
                    # スペクトルシンセはそのままSCへ転送する
                    sc_client.send_message(address, args)
                    log.info(f"Spectral SCへ転送: {address}  args={args}")

                else:
                    # 手動スライダー操作時に自律モードの現在値を同期する
                    if address == "/matoma/param" and len(args) >= 2:
                        autonomous.sync_current(str(args[0]), float(args[1]))
                    elif address == "/matoma/drone/param" and len(args) >= 2:
                        autonomous.sync_current(
                            "drone_" + str(args[0]), float(args[1])
                        )
                    sc_client.send_message(address, args)
                    log.info(f"SCへ転送: {address}  args={args}")
            except (json.JSONDecodeError, Exception) as e:
                log.warning(f"メッセージ解析エラー: {e}")
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_clients.discard(websocket)
        log.info(f"ブラウザ切断  残={len(connected_clients)}")


async def _handle_tidal(address: str, args: list, websocket) -> None:
    """Tidal関連のWebSocketメッセージを処理する。"""
    sub = address[len("/matoma/tidal/"):]

    if sub == "start":
        ok = await asyncio.get_running_loop().run_in_executor(None, tidal.start)
        reply = {
            "type": "tidal_started" if ok else "tidal_error",
            "message": (
                "Tidal起動完了" if ok
                else "Tidal起動失敗（GHC/Tidalをインストールしてください）"
            ),
        }
        await broadcast(reply)

    elif sub == "stop":
        await asyncio.get_running_loop().run_in_executor(None, tidal.stop)
        await broadcast({"type": "tidal_stopped"})

    elif sub == "hush":
        tidal.hush()
        await broadcast({"type": "tidal_applied", "code": "hush"})

    elif sub == "eval":
        code = args[0] if args else ""
        tidal.evaluate(code)
        log.info(f"Tidal評価: {code}")
        await broadcast({"type": "tidal_applied", "code": code})

    elif sub == "tempo":
        bpm = float(args[0]) if args else 120.0
        tidal.set_tempo(bpm)
        tidal.state["tempo_bpm"] = bpm
        await broadcast({"type": "tidal_state", "state": tidal.state})

    elif sub == "chord":
        # args: [root, chord_type, synth, track, octave, amp]
        root = args[0] if len(args) > 0 else tidal.state["root"]
        chord = args[1] if len(args) > 1 else tidal.state["chord"]
        synth = args[2] if len(args) > 2 else tidal.state["synth"]
        track = int(args[3]) if len(args) > 3 else 1
        octave = int(args[4]) if len(args) > 4 else tidal.state["octave"]
        amp = float(args[5]) if len(args) > 5 else tidal.state["amp"]
        tidal.state.update({"root": root, "chord": chord, "synth": synth})
        code = make_chord_pattern(track, synth, root, chord, octave, amp)
        tidal.evaluate(code)
        await broadcast(
            {"type": "tidal_state", "state": tidal.state, "code": code}
        )

    elif sub == "scale":
        # args: [root, scale, synth, track, octave, amp]
        root = args[0] if len(args) > 0 else tidal.state["root"]
        scale = args[1] if len(args) > 1 else tidal.state["scale"]
        synth = args[2] if len(args) > 2 else tidal.state["synth"]
        track = int(args[3]) if len(args) > 3 else 2
        octave = int(args[4]) if len(args) > 4 else tidal.state["octave"]
        amp = float(args[5]) if len(args) > 5 else tidal.state["amp"]
        tidal.state.update({"root": root, "scale": scale, "synth": synth})
        code = make_arp_pattern(track, synth, root, scale, 8, octave, amp)
        tidal.evaluate(code)
        await broadcast(
            {"type": "tidal_state", "state": tidal.state, "code": code}
        )

    elif sub == "state":
        # 現在の状態を返す
        await websocket.send(
            json.dumps({"type": "tidal_state", "state": tidal.state})
        )

    elif sub == "drums":
        # args: [preset, kick_gain, snare_gain, hat_gain, speed]
        preset     = str(args[0]) if len(args) > 0 else "minimal"
        kick_gain  = float(args[1]) if len(args) > 1 else 0.9
        snare_gain = float(args[2]) if len(args) > 2 else 0.7
        hat_gain   = float(args[3]) if len(args) > 3 else 0.5
        speed      = float(args[4]) if len(args) > 4 else 1.0
        codes = make_drum_pattern(3, 4, 5, preset, kick_gain, snare_gain, hat_gain, speed)
        for code in codes:
            tidal.evaluate(code)
        combined = "\n".join(codes)
        log.info(f"ドラムパターン送信: {preset}")
        await broadcast({"type": "tidal_applied", "code": combined})

    elif sub == "drums_stop":
        # ドラムトラック (d3, d4, d5) を停止
        for track in [3, 4, 5]:
            tidal.evaluate(f"d{track} $ silence")
        await broadcast({"type": "tidal_applied", "code": "d3..d5 silence"})


async def _handle_seq(address: str, args: list, websocket) -> None:
    """シーケンサー関連の WebSocket メッセージを処理する。"""
    sub = address[len("/matoma/seq/"):]

    if sub == "start":
        sequencer.start()
        await broadcast({"type": "seq_state", "state": sequencer.get_state()})
        log.info("シーケンサー開始")

    elif sub == "stop":
        sequencer.stop()
        await broadcast({"type": "seq_state", "state": sequencer.get_state()})
        log.info("シーケンサー停止")

    elif sub == "bpm" and args:
        sequencer.set_bpm(float(args[0]))
        log.info(f"seq BPM: {args[0]}")

    elif sub == "step_div" and args:
        sequencer.set_step_div(str(args[0]))
        log.info(f"seq step_div: {args[0]}")

    elif sub == "trig_prob" and args:
        sequencer.set_trig_prob(float(args[0]))

    elif sub == "mutation" and args:
        sequencer.set_mutation_prob(float(args[0]))
        log.info(f"seq mutation: {args[0]}")

    elif sub == "step_enabled" and len(args) >= 2:
        sequencer.set_step_enabled(int(args[0]), bool(args[1]))

    elif sub == "active_params" and args:
        sequencer.set_active_params(list(args))
        log.info(f"seq active_params: {args}")

    elif sub == "state":
        await websocket.send(
            json.dumps({"type": "seq_state", "state": sequencer.get_state()})
        )


async def _convert_mp3_to_wav(src_path: str) -> str | None:
    """MP3をWAVに変換してパスを返す。ffmpegが必要。失敗時はNoneを返す。"""
    tmp_wav = Path(tempfile.gettempdir()) / f"matoma_{uuid.uuid4().hex}.wav"
    try:
        result = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: subprocess.run(
                [
                    "ffmpeg", "-y", "-i", src_path,
                    "-ar", "44100", "-ac", "1", str(tmp_wav),
                ],
                capture_output=True,
                timeout=60,
            ),
        )
        if result.returncode == 0:
            return str(tmp_wav)
        stderr_head = result.stderr.decode(errors="replace")[:200]
        log.warning(
            f"ffmpeg変換失敗 (code={result.returncode}): {stderr_head}"
        )
        return None
    except FileNotFoundError:
        log.warning("ffmpegが見つかりません。MP3を読み込むにはffmpegをインストールしてください。")
        return None
    except Exception as e:
        log.warning(f"MP3変換エラー: {e}")
        return None


async def _handle_granular_browse(websocket) -> None:
    """macOSのファイル選択ダイアログを開き、選ばれたパスをブラウザへ返す。"""
    script = (
        'POSIX path of (choose file of type {"wav", "aif", "aiff", "flac", "mp3"} '
        'with prompt "グラニュラー音源ファイルを選択してください")'
    )
    try:
        result = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=60,
            ),
        )
        path = result.stdout.strip()
        if not path:
            log.info("ファイル選択がキャンセルされました")
            return

        log.info(f"グラニュラー音源選択: {path}  接続数={len(connected_clients)}")

        # ファイル選択をブラウザへ通知（ロード中として表示させる）
        await websocket.send(
            json.dumps({"type": "granular_file_selected", "path": path})
        )

        # MP3の場合はffmpegでWAVに変換してからSCへ送る
        sc_load_path = path
        if path.lower().endswith(".mp3"):
            log.info("MP3を検出 → ffmpegでWAVに変換中...")
            converted = await _convert_mp3_to_wav(path)
            if converted:
                sc_load_path = converted
                log.info(f"変換完了: {sc_load_path}")
            else:
                await broadcast({
                    "type": "granular_load_error",
                    "message": (
                        "MP3変換失敗。"
                        "ffmpegをインストールしてください（brew install ffmpeg）"
                    ),
                })
                return

        sc_client.send_message("/matoma/granular/load", [sc_load_path])
    except Exception as e:
        log.warning(f"ファイル選択ダイアログエラー: {e}")


def _acquire_pid_lock() -> None:
    """
    PIDファイルを使って旧インスタンスを停止し、自分のPIDを登録する。
    これにより複数の bridge.py が同時に動くことを防ぐ。
    """
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            os.kill(old_pid, signal.SIGTERM)
            log.info(f"旧 bridge.py (PID={old_pid}) を停止しました")
        except (ValueError, ProcessLookupError, PermissionError):
            pass  # 既に終了済みまたは無効なPID
    PID_FILE.write_text(str(os.getpid()))
    log.info(f"PIDファイル書き込み: {PID_FILE} (PID={os.getpid()})")


def _release_pid_lock() -> None:
    """終了時にPIDファイルを削除する。"""
    try:
        if PID_FILE.exists() and PID_FILE.read_text().strip() == str(os.getpid()):
            PID_FILE.unlink()
    except OSError:
        pass


async def main() -> None:
    """OSCサーバーとWebSocketサーバーを同時に起動する。"""
    global autonomous, chaos_engine, tidal, sequencer

    _acquire_pid_lock()
    await asyncio.sleep(0.8)  # 旧プロセスの終了を待つ（イベントループをブロックしない）

    autonomous = AutonomousMode(sc_client.send_message, broadcast)
    chaos_engine = ChaosEngine(sc_client.send_message, broadcast)
    tidal = TidalController()
    autonomous.set_tidal(tidal)
    sequencer = TuringSequencer(sc_client.send_message, broadcast)

    disp = Dispatcher()
    disp.set_default_handler(on_osc_message)
    osc_server = AsyncIOOSCUDPServer(
        (OSC_LISTEN_HOST, OSC_LISTEN_PORT), disp, asyncio.get_running_loop()
    )
    transport, _ = await osc_server.create_serve_endpoint()

    ws_server = await websockets.serve(ws_handler, WS_HOST, WS_PORT)

    log.info(f"OSC受信待ち: {OSC_LISTEN_HOST}:{OSC_LISTEN_PORT}")
    log.info(f"WebSocket起動: ws://{WS_HOST}:{WS_PORT}")
    log.info("ブラウザで frontend/index.html を開いてください")

    # SC を自動起動
    await start_sc()

    try:
        await asyncio.Future()
    finally:
        transport.close()
        ws_server.close()
        if sc_process and sc_process.returncode is None:
            sc_process.terminate()
        _release_pid_lock()


if __name__ == "__main__":
    asyncio.run(main())
