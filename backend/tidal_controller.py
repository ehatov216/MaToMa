"""
Tidal Cycles コントローラー
============================
GHCiプロセスを管理してTidal Cyclesのパターンを送信する。

起動方法:
  bridge.py が自動的に使用する。
  Tidalが未インストールの場合はエラーをログに出力し、
  既存のSuperCollider機能は通常通り動作する。
"""

import glob
import logging
import subprocess
import threading
import time
from pathlib import Path

log = logging.getLogger(__name__)


def _find_boot_tidal() -> Path | None:
    """BootTidal.hs のパスを自動検出する（macOS / Linux）。"""
    patterns = [
        # Cabal インストール（macOS）
        str(Path.home() / ".cabal" / "share" / "*" / "tidal-*" / "BootTidal.hs"),
        # Stack インストール
        str(Path.home() / ".stack" / "snapshots" / "*" / "*" / "*" / "share" / "tidal-*" / "BootTidal.hs"),
        # Linux / NixOS
        "/usr/share/tidal/BootTidal.hs",
        "/usr/local/share/tidal/BootTidal.hs",
    ]
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            return Path(sorted(matches)[-1])  # 最新バージョンを使う
    return None


class TidalController:
    """GHCiプロセスを通じてTidal Cyclesを制御する。

    Tidalが未インストールの場合も安全に失敗し、
    既存のSuperCollider機能には影響しない。
    """

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._write_lock = threading.Lock()
        self._reader_thread: threading.Thread | None = None
        self._running = False
        # 現在の状態（GUIへの同期用）
        self.state: dict = {
            "tempo_bpm": 120.0,
            "root": "C",
            "scale": "minor",
            "chord": "minor",
            "synth": "superpiano",
            "octave": 4,
            "amp": 0.5,
        }

    @property
    def is_running(self) -> bool:
        return self._running and self._proc is not None and self._proc.poll() is None

    def start(self, boot_path: str | None = None) -> bool:
        """GHCiとTidalを起動する。

        Returns:
            True: 起動成功
            False: 起動失敗（GHCi/Tidal未インストールなど）
        """
        if self.is_running:
            return True

        resolved_boot = Path(boot_path) if boot_path else _find_boot_tidal()

        try:
            cmd = ["ghci", "-v0"]  # -v0 = 最小ログ出力
            if resolved_boot and resolved_boot.exists():
                cmd += ["-ghci-script", str(resolved_boot)]
                log.info(f"BootTidal.hs 使用: {resolved_boot}")
            else:
                log.info("BootTidal.hs が見つからないため手動セットアップします")

            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError:
            log.warning("ghci が見つかりません。GHC/Tidalがインストールされているか確認してください。")
            return False
        except Exception as e:
            log.error(f"Tidal起動エラー: {e}")
            return False

        # バックグラウンドでGHCiの出力を読む
        self._reader_thread = threading.Thread(target=self._read_output, daemon=True)
        self._reader_thread.start()

        # 起動を待つ
        time.sleep(3)

        # BootTidal.hs がない場合は手動セットアップ
        if not resolved_boot or not resolved_boot.exists():
            self._manual_setup()

        self._running = True
        log.info("Tidal Cycles 起動完了")
        return True

    def stop(self) -> None:
        """全パターンを停止してGHCiを終了する。"""
        if self._proc:
            try:
                self._write("hush")
                time.sleep(0.5)
                self._proc.terminate()
            except Exception:
                pass
        self._running = False
        self._proc = None
        log.info("Tidal停止")

    def _manual_setup(self) -> None:
        """BootTidal.hs なしで手動セットアップする。"""
        setup_lines = [
            ":set -XOverloadedStrings",
            ":set prompt \"\"",
            ":set prompt-cont \"\"",
            ":set -package tidal",
            "import Sound.Tidal.Context",
        ]
        for line in setup_lines:
            self._write(line)
            time.sleep(0.3)

        time.sleep(0.5)
        self._write("(cps, nudge) <- bpsUtils")
        time.sleep(0.5)
        self._write("tidal <- startTidal (superdirtTarget {oLatency = 0.1}) defaultConfig")
        time.sleep(2)

        aliases = [
            "let p = streamReplace tidal",
            "let hush = streamHush tidal",
            "let setcps = streamSetCPS tidal",
            "let d1 = p 1 . (|< orbit 0)",
            "let d2 = p 2 . (|< orbit 1)",
            "let d3 = p 3 . (|< orbit 2)",
            "let d4 = p 4 . (|< orbit 3)",
        ]
        for line in aliases:
            self._write(line)
            time.sleep(0.1)

    def _read_output(self) -> None:
        """GHCiの出力をバックグラウンドで読み捨てる（ブロック防止）。"""
        while self._proc:
            try:
                if self._proc.stdout:
                    line = self._proc.stdout.readline()
                    if line:
                        log.debug(f"GHCi: {line.rstrip()}")
            except Exception:
                break

    def _write(self, code: str) -> None:
        """GHCiのstdinにコードを書き込む。"""
        if not self._proc or not self._proc.stdin:
            return
        with self._write_lock:
            try:
                self._proc.stdin.write(code + "\n")
                self._proc.stdin.flush()
            except Exception as e:
                log.error(f"Tidal書き込みエラー: {e}")
                self._running = False

    def evaluate(self, code: str) -> None:
        """Tidalコードを評価する。複数行は改行で区切る。"""
        if not self.is_running:
            log.warning("Tidal未起動。/matoma/tidal/start で起動してください。")
            return
        for line in code.strip().splitlines():
            line = line.strip()
            if line and not line.startswith("--"):
                log.info(f"Tidal: {line}")
                self._write(line)

    def set_tempo(self, bpm: float, beats_per_cycle: int = 4) -> None:
        """テンポを設定する（BPM）。"""
        cps = bpm / 60 / beats_per_cycle
        self.state["tempo_bpm"] = bpm
        self.evaluate(f"setcps {cps:.4f}  -- {bpm:.0f} BPM")

    def hush(self) -> None:
        """全パターンを停止する。"""
        self.evaluate("hush")
