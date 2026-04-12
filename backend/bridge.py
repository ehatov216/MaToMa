"""
MaToMa ブリッジ（シンプル版）
==============================
Sonic Anatomy の分析データを TidalCycles パターンに変換して演奏する。

パイプライン:
  GUI（トラック選択 + Start/Stop）
          ↓ WebSocket
  bridge.py
    load_record(track_id)
    generate_tidal_seed(record)
    tidal.set_tempo(seed.bpm)
    tidal.evaluate(all_lines)
          ↓
  TidalCycles → 既存SCシンセ

WebSocket メッセージ仕様:

  ブラウザ → サーバー:
    {"type": "play",        "track_id": "xxx"}   トラックを再生
    {"type": "stop"}                             全停止 (hush)
    {"type": "tidal_start"}                      Tidal を起動
    {"type": "sc_start"}                         SC を起動
    {"type": "sc_stop"}                          SC を停止

  サーバー → ブラウザ:
    {"type": "sc_status",   "ready": bool}       SC 状態
    {"type": "sc_ready",    "message": str}       SC 起動完了
    {"type": "sc_booting",  "message": str}       SC 起動中
    {"type": "catalog",     "tracks": [...]}      SA トラック一覧
    {"type": "tidal_started","message": str}      Tidal 起動完了
    {"type": "playing",     "track_id": str, ...} 再生中トラック情報
    {"type": "stopped"}                           停止完了
    {"type": "error",       "message": str}       エラー
"""

import asyncio
import json
import logging
import os
import shutil
import signal
import subprocess
from pathlib import Path
from typing import Optional

import websockets
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer

from tidal_controller import TidalController
from sonic_anatomy_bridge import list_records, load_record, generate_tidal_seed, seed_to_dict

# ── ポート設定 ──────────────────────────────────────────
OSC_LISTEN_HOST = "127.0.0.1"
OSC_LISTEN_PORT = 9000   # SC → Python
WS_HOST = "localhost"
WS_PORT = 8765           # ブラウザ ↔ Python

SC_BOOT_TIMEOUT = 60

# ── PID ファイル ─────────────────────────────────────────
PID_FILE = Path(__file__).parent / ".bridge.pid"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

connected_clients: set = set()
sc_process = None
sc_ready = False
tidal: Optional[TidalController] = None


# ── ユーティリティ ─────────────────────────────────────────────────────

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


async def broadcast(message: dict) -> None:
    """接続中の全ブラウザに JSON を送る。切断済みは自動除去。"""
    if not connected_clients:
        return
    data = json.dumps(message, ensure_ascii=False)
    disconnected: set = set()
    for ws in list(connected_clients):
        try:
            await ws.send(data)
        except Exception:
            disconnected.add(ws)
    connected_clients.difference_update(disconnected)


async def _ensure_tidal_running(websocket) -> bool:
    """Tidal が未起動なら起動し、起動済みならそのまま続行する。"""
    global tidal
    if tidal is None:
        await websocket.send(json.dumps({
            "type": "error",
            "message": "Tidalコントローラーが初期化されていません。",
        }))
        return False

    if tidal.is_running:
        return True

    ok = await asyncio.get_running_loop().run_in_executor(None, tidal.start)
    if ok:
        await broadcast({
            "type": "tidal_started",
            "message": "Tidal起動完了",
        })
        return True

    await websocket.send(json.dumps({
        "type": "error",
        "message": "Tidalの起動に失敗しました。GHC/TidalのインストールとBootTidal設定を確認してください。",
    }))
    return False


# ── SuperCollider 制御 ────────────────────────────────────────────────

async def start_sc() -> bool:
    """SuperCollider を起動する。/matoma/ready が届くまで待機。"""
    global sc_process, sc_ready

    log.info("既存SCプロセスをkill中...")
    subprocess.run(["pkill", "-f", "sclang"], capture_output=True)
    subprocess.run(["pkill", "-f", "scsynth"], capture_output=True)
    await asyncio.sleep(1.5)

    sclang = find_sclang()
    if not sclang:
        log.error("sclang が見つかりません")
        await broadcast({"type": "error", "message": "sclang が見つかりません。SuperCollider をインストールしてください。"})
        return False

    sc_script = Path(__file__).parent.parent / "sc" / "run_headless.scd"
    if not sc_script.exists():
        log.error(f"SCスクリプトが見つかりません: {sc_script}")
        await broadcast({"type": "error", "message": f"SCスクリプトが見つかりません: {sc_script}"})
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
        await broadcast({"type": "error", "message": f"SC起動失敗: {e}"})
        return False

    asyncio.create_task(_pipe_sc_output(sc_process))

    log.info(f"SC readyを待機中（最大{SC_BOOT_TIMEOUT}秒）...")
    await broadcast({"type": "sc_booting", "message": "SC起動中..."})
    try:
        await asyncio.wait_for(_wait_sc_ready(), timeout=SC_BOOT_TIMEOUT)
        log.info("SC起動完了")
        return True
    except asyncio.TimeoutError:
        log.error("SC起動タイムアウト")
        await broadcast({"type": "error", "message": f"SC起動タイムアウト（{SC_BOOT_TIMEOUT}秒）"})
        return False


async def _wait_sc_ready() -> None:
    while not sc_ready:
        await asyncio.sleep(0.2)


async def _pipe_sc_output(proc) -> None:
    if proc.stdout is None:
        return
    async for line in proc.stdout:
        text = line.decode("utf-8", errors="replace").rstrip()
        if text:
            log.info(f"[SC] {text}")


def on_osc_message(address: str, *args) -> None:
    """SCからのOSCメッセージを処理する。"""
    global sc_ready
    if address == "/matoma/ready":
        sc_ready = True
        log.info("SC ready 受信")
        asyncio.get_running_loop().create_task(
            broadcast({"type": "sc_ready", "message": "SC起動完了"})
        )
    else:
        log.debug(f"OSC受信: {address}  args={args}")


# ── WebSocket ハンドラ ────────────────────────────────────────────────

async def ws_handler(websocket) -> None:
    """ブラウザからの WebSocket 接続を管理する。"""
    global sc_process, sc_ready
    connected_clients.add(websocket)
    log.info(f"ブラウザ接続: {websocket.remote_address}  合計={len(connected_clients)}")

    # 接続直後: SC 状態を送る
    await websocket.send(json.dumps({
        "type": "sc_status",
        "ready": sc_ready,
    }))

    # SA カタログを送る
    tracks = list_records(limit=100)
    await websocket.send(json.dumps({
        "type": "catalog",
        "tracks": tracks,
    }))
    log.info(f"SAカタログ送信: {len(tracks)} 件")

    try:
        async for raw in websocket:
            try:
                msg = json.loads(raw)
                msg_type = msg.get("type", "")

                if msg_type == "play":
                    await _handle_play(msg.get("track_id"), websocket)

                elif msg_type == "stop":
                    if tidal is not None:
                        tidal.hush()
                    await broadcast({"type": "stopped"})
                    log.info("停止")

                elif msg_type == "tidal_start":
                    await _ensure_tidal_running(websocket)

                elif msg_type == "sc_start":
                    await broadcast({"type": "sc_booting", "message": "SC起動中..."})
                    asyncio.create_task(start_sc())

                elif msg_type == "sc_stop":
                    sc_ready = False
                    subprocess.run(["pkill", "-f", "sclang"], capture_output=True)
                    subprocess.run(["pkill", "-f", "scsynth"], capture_output=True)
                    if sc_process is not None:
                        try:
                            sc_process.terminate()
                        except Exception:
                            pass
                        sc_process = None
                    await broadcast({"type": "sc_status", "ready": False})
                    log.info("SC停止")

            except json.JSONDecodeError:
                log.warning("不正なJSONを受信しました")
            except Exception as e:
                log.warning(f"メッセージ処理エラー: {e}")

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_clients.discard(websocket)
        log.info(f"ブラウザ切断  残={len(connected_clients)}")


async def _handle_play(track_id: Optional[str], websocket) -> None:
    """トラックを選択して Tidal で演奏する。"""
    if not await _ensure_tidal_running(websocket):
        return

    record = load_record(track_id)
    if record is None:
        await websocket.send(json.dumps({
            "type": "error",
            "message": f"トラックが見つかりません: {track_id}",
        }))
        return

    seed = generate_tidal_seed(record)
    tidal.set_tempo(seed.bpm)
    all_code = "\n".join(
        seed.rhythm_lines + seed.harmony_lines + seed.melody_lines
    )
    tidal.evaluate(all_code)

    seed_dict = seed_to_dict(seed)
    await broadcast({
        **seed_dict,
        "type": "playing",
    })
    log.info(f"再生開始: {record.track_id}  BPM={record.bpm:.1f}  key={record.key_root} {record.key_mode}")


# ── PID ロック ────────────────────────────────────────────────────────

def _acquire_pid_lock() -> None:
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            os.kill(old_pid, signal.SIGTERM)
            log.info(f"旧 bridge.py (PID={old_pid}) を停止しました")
        except (ValueError, ProcessLookupError, PermissionError):
            pass
    PID_FILE.write_text(str(os.getpid()))
    log.info(f"PIDファイル書き込み (PID={os.getpid()})")


def _release_pid_lock() -> None:
    try:
        if PID_FILE.exists() and PID_FILE.read_text().strip() == str(os.getpid()):
            PID_FILE.unlink()
    except OSError:
        pass


# ── メインループ ──────────────────────────────────────────────────────

async def main() -> None:
    global tidal

    _acquire_pid_lock()
    await asyncio.sleep(0.8)

    tidal = TidalController()

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
