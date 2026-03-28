"""
Web UI E2E テスト
=================
SC コードの変更がブラウザ UI に正しく反映されているかを確認するテスト群。

テスト構成:
  - WebSocket 接続状態の確認
  - シーンボタンのクリックと UI 更新
  - スライダー操作と WebSocket メッセージ送信
  - 音再生ボタンのトグル動作
"""

from __future__ import annotations

import time

import pytest
from playwright.sync_api import Page, expect


# ── ヘルパー ───────────────────────────────────────────────────────────────

def wait_for_ws_message(
    messages: list[dict],
    address: str,
    timeout: float = 2.0,
) -> dict | None:
    """指定アドレスの WS メッセージが届くまで待つ。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        for msg in messages:
            if msg.get("address") == address:
                return msg
        time.sleep(0.05)
    return None


# ── テストケース ───────────────────────────────────────────────────────────

class TestConnection:
    """WebSocket 接続と UI 初期状態のテスト。"""

    def test_page_loads(self, page: Page, ui_url: str) -> None:
        """ページが正常に読み込まれ、タイトルが表示される。"""
        page.goto(ui_url)
        expect(page.locator("h1")).to_have_text("MaToMa")

    def test_ws_connected(self, page: Page, ui_url: str) -> None:
        """bridge.py（モック）に接続すると「接続済み」と表示される。"""
        page.goto(ui_url)
        expect(page.locator("#status")).to_have_text("接続済み", timeout=3000)
        expect(page.locator("#status")).to_have_class("connected")

    def test_initial_slider_values(self, page: Page, ui_url: str) -> None:
        """スライダーの初期値が正しく表示されている。"""
        page.goto(ui_url)
        expect(page.locator("#freq-val")).to_have_text("220 Hz")
        expect(page.locator("#cutoff-val")).to_have_text("1000 Hz")
        expect(page.locator("#amp-val")).to_have_text("0.50")


class TestSceneButtons:
    """シーン選択ボタンのテスト。"""

    def test_scene_button_active_state(self, page: Page, ui_url: str) -> None:
        """シーンボタンをクリックすると active クラスが付く。"""
        page.goto(ui_url)
        page.wait_for_selector("#status.connected", timeout=3000)

        btn = page.locator(".scene-btn", has_text="暗い")
        btn.click()
        expect(btn).to_have_class("scene-btn active")

    def test_only_one_scene_active(self, page: Page, ui_url: str) -> None:
        """複数クリックしても active は 1 つだけ。"""
        page.goto(ui_url)
        page.wait_for_selector("#status.connected", timeout=3000)

        page.locator(".scene-btn", has_text="暗い").click()
        page.locator(".scene-btn", has_text="明るい").click()

        active_buttons = page.locator(".scene-btn.active")
        expect(active_buttons).to_have_count(1)
        expect(active_buttons).to_have_text("明るい")

    def test_scene_sends_ws_message(
        self, page: Page, ui_url: str, ws_messages: list[dict]
    ) -> None:
        """シーンボタンが WebSocket で /matoma/scene を送信する。"""
        page.goto(ui_url)
        page.wait_for_selector("#status.connected", timeout=3000)

        page.locator(".scene-btn", has_text="標準").click()

        msg = wait_for_ws_message(ws_messages, "/matoma/scene")
        assert msg is not None, "/matoma/scene メッセージが届かなかった"
        assert msg["args"] == ["標準"]


class TestSliders:
    """スライダー操作のテスト。"""

    def test_freq_slider_updates_display(
        self, page: Page, ui_url: str
    ) -> None:
        """freq スライダーを動かすと表示値が変わる。"""
        page.goto(ui_url)
        page.wait_for_selector("#status.connected", timeout=3000)

        page.evaluate(
            """() => {
                const el = document.getElementById('freq');
                el.value = 440;
                el.dispatchEvent(new Event('input', { bubbles: true }));
            }"""
        )
        expect(page.locator("#freq-val")).to_have_text("440 Hz")

    def test_freq_slider_sends_ws_message(
        self, page: Page, ui_url: str, ws_messages: list[dict]
    ) -> None:
        """freq スライダーが /matoma/param を WebSocket で送信する。"""
        page.goto(ui_url)
        page.wait_for_selector("#status.connected", timeout=3000)

        page.evaluate(
            """() => {
                const el = document.getElementById('freq');
                el.value = 440;
                el.dispatchEvent(new Event('input', { bubbles: true }));
            }"""
        )
        msg = wait_for_ws_message(ws_messages, "/matoma/param")
        assert msg is not None, "/matoma/param メッセージが届かなかった"
        assert msg["args"][0] == "freq"
        assert msg["args"][1] == pytest.approx(440, abs=1)

    def test_amp_slider_shows_decimal(self, page: Page, ui_url: str) -> None:
        """amp スライダーは小数点2桁で表示される。"""
        page.goto(ui_url)
        page.wait_for_selector("#status.connected", timeout=3000)

        page.evaluate(
            """() => {
                const el = document.getElementById('amp');
                el.value = 0.75;
                el.dispatchEvent(new Event('input', { bubbles: true }));
            }"""
        )
        expect(page.locator("#amp-val")).to_have_text("0.75")


class TestSoundButtons:
    """音再生ボタンのトグルテスト。"""

    def test_start_button_toggle(self, page: Page, ui_url: str) -> None:
        """音を鳴らすボタンを押すとテキストが変わり playing クラスが付く。"""
        page.goto(ui_url)
        page.wait_for_selector("#status.connected", timeout=3000)

        btn = page.locator("#start-btn")
        expect(btn).to_have_text("▶ 音を鳴らす")
        expect(btn).not_to_have_class("playing")

        btn.click()
        expect(btn).to_have_text("■ 音を止める")
        expect(btn).to_have_class("playing")

    def test_start_button_sends_start_message(
        self, page: Page, ui_url: str, ws_messages: list[dict]
    ) -> None:
        """音を鳴らすボタンが /matoma/start を送信する。"""
        page.goto(ui_url)
        page.wait_for_selector("#status.connected", timeout=3000)

        page.locator("#start-btn").click()
        msg = wait_for_ws_message(ws_messages, "/matoma/start")
        assert msg is not None, "/matoma/start メッセージが届かなかった"

    def test_start_button_sends_stop_message(
        self, page: Page, ui_url: str, ws_messages: list[dict]
    ) -> None:
        """音を止めるボタンが /matoma/stop を送信する。"""
        page.goto(ui_url)
        page.wait_for_selector("#status.connected", timeout=3000)

        page.locator("#start-btn").click()  # start
        ws_messages.clear()
        page.locator("#start-btn").click()  # stop

        msg = wait_for_ws_message(ws_messages, "/matoma/stop")
        assert msg is not None, "/matoma/stop メッセージが届かなかった"

    def test_drone_button_toggle(self, page: Page, ui_url: str) -> None:
        """ドローンボタンをトグルすると playing クラスが付く。"""
        page.goto(ui_url)
        page.wait_for_selector("#status.connected", timeout=3000)

        btn = page.locator("#drone-btn")
        btn.click()
        expect(btn).to_have_class("playing")

    def test_granular_button_toggle(self, page: Page, ui_url: str) -> None:
        """グラニューラボタンをトグルすると playing クラスが付く。"""
        page.goto(ui_url)
        page.wait_for_selector("#status.connected", timeout=3000)

        btn = page.locator("#granular-btn")
        btn.click()
        expect(btn).to_have_class("playing")


class TestDroneSliders:
    """ドローンスライダーのテスト。"""

    def test_drone_freq_sends_ws_message(
        self, page: Page, ui_url: str, ws_messages: list[dict]
    ) -> None:
        """drone-freq スライダーが /matoma/drone/param を送信する。"""
        page.goto(ui_url)
        page.wait_for_selector("#status.connected", timeout=3000)

        page.evaluate(
            """() => {
                const el = document.getElementById('drone-freq');
                el.value = 80;
                el.dispatchEvent(new Event('input', { bubbles: true }));
            }"""
        )
        msg = wait_for_ws_message(ws_messages, "/matoma/drone/param")
        assert msg is not None, "/matoma/drone/param メッセージが届かなかった"
        assert msg["args"][0] == "freq"
        assert msg["args"][1] == pytest.approx(80, abs=1)
