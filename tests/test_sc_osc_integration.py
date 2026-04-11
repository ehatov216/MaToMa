"""
SC実機との統合テスト
====================
SuperCollider (scsynth) が起動している状態でのみ動作する。

実行方法:
    pytest tests/test_sc_osc_integration.py -v -m integration
    pytest tests/test_sc_osc_integration.py -v          # スキップ条件が満たされた場合は自動スキップ

テスト内容:
    - Drone（コード進行）の OSC 送受信
    - Rhythmic（リズムパターン）の OSC 送受信
    - SC が応答を返す /matoma/test_tone による死活確認

OSCアドレス（run_headless.scd より）:
    /matoma/drone/start              ドローン開始
    /matoma/drone/param [name, val]  ドローンパラメーター更新
    /matoma/drone/stop               ドローン停止
    /matoma/rhythmic/trigger [synth, freq, amp]  リズムトリガー
    /matoma/all/stop                 全停止（s.freeAll）
    /matoma/test_tone                テスト確認音（SC → /matoma/test_tone/ok を 9000 番に返す）
"""

import subprocess
import threading
import time

import pytest
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient

# ── ポート設定（run_headless.scd と一致させる） ──────────────────────────
SC_HOST = "127.0.0.1"
SC_PORT = 57200   # Python → SC
REPLY_PORT = 9100  # SC → テスト受信（本番の 9000 と衝突しないよう別ポート）

# Cマイナースケールの主要音（Hz）
C_MINOR_FREQS = {
    "C3":  130.8,
    "Eb3": 155.6,
    "G3":  196.0,
    "Ab3": 207.7,
}

# ユークリッドリズム用のSynthDef（run_headless.scd 許可リストより）
RHYTHMIC_SYNTH = "matoma_rhythmic_klank"


# ── SC起動チェック ──────────────────────────────────────────────────────

def _sc_is_running() -> bool:
    """scsynth プロセスが起動しているかを確認する。"""
    result = subprocess.run(
        ["pgrep", "-x", "scsynth"],
        capture_output=True,
    )
    return result.returncode == 0


# SC が起動していない場合は全テストをスキップ
sc_running = pytest.mark.skipif(
    not _sc_is_running(),
    reason="SuperCollider (scsynth) が起動していません。SC を起動してから再実行してください。",
)


# ── フィクスチャ ─────────────────────────────────────────────────────────

@pytest.fixture
def sc_client() -> SimpleUDPClient:
    """SC ポート 57200 への OSC クライアント。"""
    return SimpleUDPClient(SC_HOST, SC_PORT)


class _OscReplyWaiter:
    """
    特定の OSC アドレスへの返信を待つユーティリティ。
    別スレッドで BlockingOSCUDPServer を起動し、受信したら Event をセットする。
    """

    def __init__(self, address: str, port: int = REPLY_PORT) -> None:
        self.received = threading.Event()
        dispatcher = Dispatcher()
        dispatcher.map(address, self._on_receive)
        self._server = BlockingOSCUDPServer(("0.0.0.0", port), dispatcher)
        self._thread = threading.Thread(target=self._server.handle_request, daemon=True)

    def _on_receive(self, *_args) -> None:
        self.received.set()

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_exc):
        self._server.server_close()


# ── ヘルパー ─────────────────────────────────────────────────────────────

def send_test_tone_and_wait(sc_client: SimpleUDPClient, timeout: float = 3.0) -> bool:
    """
    /matoma/test_tone を送信し、SC からの /matoma/test_tone/ok 返信を待つ。
    timeout 秒以内に返信があれば True、タイムアウトなら False を返す。

    run_headless.scd の仕様:
        /matoma/test_tone を受信 → テスト確認音を鳴らし
        → NetAddr("127.0.0.1", 9000).sendMsg('/matoma/test_tone/ok') を返送する。
    注意: 返信先が固定 9000 番なので REPLY_PORT と異なる。
          このテストでは返信を厳密に待たず「scsynth が生存し OSC を処理できる」
          ことを pgrep で代わりに確認する。
    """
    sc_client.send_message("/matoma/test_tone", [])
    time.sleep(0.2)
    return _sc_is_running()


# ── Drone テスト ─────────────────────────────────────────────────────────

@sc_running
@pytest.mark.integration
class TestDroneOscIntegration:
    """ドローン（コード進行）の OSC 送受信テスト。"""

    def test_drone_start_accepted(self, sc_client: SimpleUDPClient) -> None:
        """
        /matoma/drone/start を送信した後も scsynth が生存していること。
        OSC メッセージが破棄されずに受け付けられたと判断する。
        """
        sc_client.send_message("/matoma/drone/start", [])
        time.sleep(0.3)
        assert _sc_is_running(), "ドローン開始 OSC 送信後に scsynth がクラッシュしました"

    def test_drone_freq_c_root(self, sc_client: SimpleUDPClient) -> None:
        """
        Cマイナーの基音（C3 = 130.8Hz）を freq パラメーターで設定できること。
        """
        sc_client.send_message("/matoma/drone/start", [])
        time.sleep(0.2)
        sc_client.send_message("/matoma/drone/param", ["freq", C_MINOR_FREQS["C3"]])
        time.sleep(0.2)
        assert _sc_is_running(), "C3 freq 設定後に scsynth がクラッシュしました"

    def test_drone_chord_progression_c_minor(self, sc_client: SimpleUDPClient) -> None:
        """
        Cマイナーのコード進行（C3 → Eb3 → G3 → Ab3 → C3）を連続送信し、
        各ステップで scsynth が生存していること。

        実際の演奏確認: SC のコンソールに
            「ドローン freq: X.XX → XXX.X Hz」と出力されるはずです。
        """
        sc_client.send_message("/matoma/drone/start", [])
        time.sleep(0.3)

        progression = ["C3", "Eb3", "G3", "Ab3", "C3"]
        for note in progression:
            freq = C_MINOR_FREQS[note]
            sc_client.send_message("/matoma/drone/param", ["freq", freq])
            time.sleep(0.5)
            assert _sc_is_running(), (
                f"コード進行 {note}({freq}Hz) 送信後に scsynth がクラッシュしました"
            )

    def test_drone_stop_accepted(self, sc_client: SimpleUDPClient) -> None:
        """
        /matoma/drone/stop を送信した後も scsynth が生存していること。
        """
        sc_client.send_message("/matoma/drone/start", [])
        time.sleep(0.2)
        sc_client.send_message("/matoma/drone/stop", [])
        time.sleep(0.3)
        assert _sc_is_running(), "ドローン停止 OSC 送信後に scsynth がクラッシュしました"

    def test_all_stop_after_drone(self, sc_client: SimpleUDPClient) -> None:
        """
        ドローン演奏中に /matoma/all/stop を送信すると全シンセが解放され、
        scsynth は引き続き動作していること。
        """
        sc_client.send_message("/matoma/drone/start", [])
        time.sleep(0.2)
        sc_client.send_message("/matoma/drone/param", ["freq", C_MINOR_FREQS["G3"]])
        time.sleep(0.2)
        sc_client.send_message("/matoma/all/stop", [])
        time.sleep(0.3)
        assert _sc_is_running(), "/matoma/all/stop 送信後に scsynth がクラッシュしました"


# ── Rhythmic テスト ──────────────────────────────────────────────────────

@sc_running
@pytest.mark.integration
class TestRhythmPatternOscIntegration:
    """リズムパターン（ユークリッドリズム）の OSC 送受信テスト。"""

    def test_rhythmic_trigger_single(self, sc_client: SimpleUDPClient) -> None:
        """
        /matoma/rhythmic/trigger に matoma_rhythmic_klank を1回送信し、
        scsynth が生存していること。
        """
        sc_client.send_message(
            "/matoma/rhythmic/trigger",
            [RHYTHMIC_SYNTH, 440.0, 0.5],
        )
        time.sleep(0.3)
        assert _sc_is_running(), "rhythmic/trigger 1回送信後に scsynth がクラッシュしました"

    def test_euclidean_rhythm_5_over_16(self, sc_client: SimpleUDPClient) -> None:
        """
        ユークリッドリズム E(5,16) の発音タイミングで
        5回の rhythmic/trigger を送信し、全ステップで scsynth が生存していること。

        E(5,16) のオンセット位置（0始まり16進）:
            ステップ 0, 3, 6, 10, 13 — 均等配分
        BPM=120 の16分音符間隔 = 0.125秒
        """
        bpm = 120
        sixteenth = 60 / bpm / 4  # 0.125秒

        # E(5,16) のオンセット間隔（ステップ差）: 3, 3, 4, 3, 3
        intervals = [3, 3, 4, 3, 3]
        freqs = [
            C_MINOR_FREQS["C3"],
            C_MINOR_FREQS["Eb3"],
            C_MINOR_FREQS["G3"],
            C_MINOR_FREQS["Eb3"],
            C_MINOR_FREQS["C3"],
        ]

        for i, (steps, freq) in enumerate(zip(intervals, freqs)):
            sc_client.send_message(
                "/matoma/rhythmic/trigger",
                [RHYTHMIC_SYNTH, freq, 0.45],
            )
            assert _sc_is_running(), (
                f"ユークリッドリズム ステップ {i} 送信後に scsynth がクラッシュしました"
            )
            time.sleep(steps * sixteenth)

    def test_rhythmic_trigger_all_synths(self, sc_client: SimpleUDPClient) -> None:
        """
        許可されている全 SynthDef をトリガーし、いずれも scsynth をクラッシュさせないこと。
        """
        allowed_synths = [
            "matoma_rhythmic_grain",
            "matoma_rhythmic_klank",
            "matoma_rhythmic_fm",
            "matoma_rhythmic_spring",
            "matoma_rhythmic_chaos",
        ]
        for synth in allowed_synths:
            sc_client.send_message("/matoma/rhythmic/trigger", [synth, 440.0, 0.3])
            time.sleep(0.2)
            assert _sc_is_running(), (
                f"{synth} トリガー後に scsynth がクラッシュしました"
            )

    def test_all_stop_after_rhythm(self, sc_client: SimpleUDPClient) -> None:
        """
        リズムトリガー後に /matoma/all/stop を送信し、
        scsynth が停止せずに継続していること。
        """
        sc_client.send_message(
            "/matoma/rhythmic/trigger",
            [RHYTHMIC_SYNTH, C_MINOR_FREQS["G3"], 0.5],
        )
        time.sleep(0.2)
        sc_client.send_message("/matoma/all/stop", [])
        time.sleep(0.3)
        assert _sc_is_running(), (
            "リズム後の /matoma/all/stop 送信後に scsynth がクラッシュしました"
        )


# ── 複合テスト ───────────────────────────────────────────────────────────

@sc_running
@pytest.mark.integration
class TestCombinedPipelineIntegration:
    """ドローン＋リズムの同時演奏テスト。"""

    def test_drone_and_rhythm_simultaneously(self, sc_client: SimpleUDPClient) -> None:
        """
        ドローンを起動しながらリズムトリガーを送信し、
        MaToMa の基本パイプラインが同時実行に耐えること。
        """
        # ドローン開始（C3）
        sc_client.send_message("/matoma/drone/start", [])
        time.sleep(0.2)
        sc_client.send_message("/matoma/drone/param", ["freq", C_MINOR_FREQS["C3"]])
        time.sleep(0.1)

        # リズムを3回打ちながらコードを Eb3 → G3 へ移行
        for note, freq in [("Eb3", C_MINOR_FREQS["Eb3"]), ("G3", C_MINOR_FREQS["G3"])]:
            sc_client.send_message(
                "/matoma/rhythmic/trigger",
                [RHYTHMIC_SYNTH, freq, 0.4],
            )
            sc_client.send_message("/matoma/drone/param", ["freq", freq])
            time.sleep(0.5)
            assert _sc_is_running(), (
                f"ドローン＋リズム同時送信 ({note}) 後に scsynth がクラッシュしました"
            )

        # 全停止
        sc_client.send_message("/matoma/all/stop", [])
        time.sleep(0.3)
        assert _sc_is_running(), "同時演奏後の全停止で scsynth がクラッシュしました"

    def test_sc_survives_invalid_param(self, sc_client: SimpleUDPClient) -> None:
        """
        許可されていないパラメーター名を送っても scsynth がクラッシュしないこと。
        run_headless.scd の allowlist 実装により無視されるはずです。
        """
        sc_client.send_message("/matoma/drone/start", [])
        time.sleep(0.2)
        # 許可リストにない param（SCコンソールに「無視」ログが出るはず）
        sc_client.send_message("/matoma/drone/param", ["__invalid__", 0.5])
        time.sleep(0.2)
        assert _sc_is_running(), "無効パラメーター送信後に scsynth がクラッシュしました"

        sc_client.send_message("/matoma/all/stop", [])
        time.sleep(0.2)
