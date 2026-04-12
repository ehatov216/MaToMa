"""
Tidal 単体テスト
================
GUI/bridge.py 不要。TidalController だけ起動して直接パターンを送る。

使い方:
  cd ~/dev/MaToMa/backend
  python test_tidal.py

[GHCi] で始まる行が GHCi の生ログ。エラーがあればここに出る。
"""

import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

from tidal_controller import TidalController

log = logging.getLogger(__name__)

def main() -> None:
    tidal = TidalController()

    log.info("=== Tidal 起動 ===")
    ok = tidal.start()
    log.info(f"tidal.start() → {ok}")

    if not ok:
        log.error("Tidal の起動に失敗しました。ghci / Tidal がインストールされているか確認してください。")
        return

    # 起動直後は少し待つ
    log.info("2秒待機中...")
    time.sleep(2)

    # 最もシンプルなパターン: 毎サイクル Klank を 1 回鳴らす
    log.info("=== パターン送信 ===")
    tidal.evaluate('d1 $ s "matoma_rhythmic_klank" # freq 440 # amp 0.7')

    log.info("10秒間演奏中... 音が聞こえれば Tidal→SC 疎通 OK")
    time.sleep(10)

    log.info("=== 停止 ===")
    tidal.hush()
    time.sleep(1)
    tidal.stop()
    log.info("完了")


if __name__ == "__main__":
    main()
