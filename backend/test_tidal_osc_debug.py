"""
Tidal→OSC 疎通デバッグテスト
==============================
テスト用ポート 57201 で UDP を受信し、Tidal が実際に OSC を送っているか確認する。

手順:
  1. このスクリプトを実行するだけ（SC を停止しない）
  2. ログに「OSCパケット受信!」が出れば Tidal→UDP は正常
  3. 出なければ Tidal が OSC を送信していない

使い方:
  cd ~/dev/MaToMa/backend
  python test_tidal_osc_debug.py
"""

import logging
import socket
import tempfile
import threading
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

from tidal_controller import TidalController

# テスト用ポート（SC の 57200 とは別）
TEST_PORT = 57201

# BootTidal_matoma.hs と同じ内容でポートだけ 57201 に変える
BOOT_CONTENT = """-- MaToMa OSC デバッグ用BootTidal（ポート57201）
:set -fno-warn-orphans -Wno-type-defaults -XMultiParamTypeClasses -XOverloadedStrings
:set prompt ""

import Sound.Tidal.Boot

:{
let matomaTarget = superdirtTarget { oName = "MaToMaDebug", oAddress = "127.0.0.1", oPort = 57201, oHandshake = False, oBusPort = Nothing }
:}

:{
let matomaShape = OSC "/matoma/rhythmic/trigger" $ ArgList [("s", Nothing), ("freq", Just $ VF 440.0), ("amp", Just $ VF 0.5)]
:}

default (Rational, Integer, Double, Pattern String)

tidalInst <- mkTidalWith [(matomaTarget, [matomaShape])] (defaultConfig { cCtrlListen = False })

instance Tidally where tidal = tidalInst

:set prompt "tidal> "
:set prompt-cont ""
"""


received_packets: list[bytes] = []
_stop_server = threading.Event()


def _udp_server() -> None:
    """ポート 57201 で UDP パケットを受信してログに出す。"""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", TEST_PORT))
        sock.settimeout(1.0)
        log.info(f"UDP受信待機: 127.0.0.1:{TEST_PORT}")
        while not _stop_server.is_set():
            try:
                data, addr = sock.recvfrom(4096)
                log.info(
                    f"★ OSCパケット受信! {len(data)} bytes from {addr}"
                    f" | hex: {data[:30].hex()}"
                )
                received_packets.append(data)
            except socket.timeout:
                continue


def main() -> None:
    # テスト用BootTidal をテンポラリファイルに書き出す
    boot_file = Path(tempfile.mktemp(suffix=".hs", prefix="BootTidal_debug_"))
    boot_file.write_text(BOOT_CONTENT)
    log.info(f"テスト用BootTidal: {boot_file}")

    # UDP サーバーをバックグラウンドで起動
    server_thread = threading.Thread(target=_udp_server, daemon=True)
    server_thread.start()

    # Tidal をテスト用BootTidal（ポート57201向き）で起動
    tidal = TidalController()
    log.info("=== Tidal 起動（ポート57201向き） ===")
    ok = tidal.start(boot_path=str(boot_file))
    log.info(f"tidal.start() → {ok}")

    if not ok:
        log.error("Tidal 起動失敗")
        _stop_server.set()
        boot_file.unlink(missing_ok=True)
        return

    log.info("2秒待機...")
    time.sleep(2)

    log.info("=== パターン送信 ===")
    tidal.evaluate('d1 $ s "matoma_rhythmic_klank" # freq 440 # amp 0.7')

    log.info("10秒間監視中（パケット到着を待つ）...")
    time.sleep(10)

    tidal.hush()
    time.sleep(0.5)
    tidal.stop()
    _stop_server.set()

    # 結果サマリー
    log.info("")
    log.info("=== デバッグ結果 ===")
    log.info(f"受信パケット数: {len(received_packets)}")
    if received_packets:
        log.info("✓ Tidal → OSC 送信 OK（ポートを 57200 に戻せば SC に届くはず）")
    else:
        log.info("✗ パケット未受信 → Tidal が OSC を送信していない")
        log.info("  考えられる原因:")
        log.info("  1. mkTidalWith がエラーで失敗している（[GHCi] ログを確認）")
        log.info("  2. d1 への書き込みが stdin に届いていない")
        log.info("  3. CPS が 0 になっている（setcps が呼ばれた？）")

    boot_file.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
