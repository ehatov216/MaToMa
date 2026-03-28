"""
E2E テスト用フィクスチャ
========================
- http_server : frontend/index.html を HTTP で配信する（ポート 18080）
- ws_messages : Playwright の route_web_socket でブラウザの WS 送信を捕捉するリスト
- ui_url      : ブラウザが開く URL を返す

外部 WebSocket サーバーは不要。Playwright が ws://localhost:8765 への接続を
インターセプトするため、実際の bridge.py が起動していてもいなくても動作する。
"""

from __future__ import annotations

import http.server
import json
import threading
from pathlib import Path
from typing import Generator

import pytest
from playwright.sync_api import Page, WebSocketRoute


HTTP_PORT = 18080
FRONTEND_DIR = Path(__file__).parents[2] / "frontend"
WS_URL = "ws://localhost:8765"


# ── HTTP サーバー ──────────────────────────────────────────────────────────

class _SilentHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture(scope="session")
def http_server() -> Generator[None, None, None]:
    """frontend/ を HTTP で配信するサーバー（セッション全体で共有）。"""
    srv = http.server.HTTPServer(
        ("localhost", HTTP_PORT),
        lambda *a, **kw: _SilentHandler(*a, directory=str(FRONTEND_DIR), **kw),
    )
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield
    srv.shutdown()


# ── WebSocket インターセプター ──────────────────────────────────────────────

@pytest.fixture()
def ws_messages() -> list[dict]:
    """各テストで受信した WS メッセージを格納するリスト。"""
    return []


@pytest.fixture()
def ui_url(
    page: Page,
    http_server: None,
    ws_messages: list[dict],
) -> Generator[str, None, None]:
    """
    WS をインターセプトして UI の URL を返す。

    ブラウザから ws://localhost:8765 へ送信されるメッセージを ws_messages に記録する。
    bridge.py が動いていてもいなくても動作する。
    """
    def _handle_ws(ws_route: WebSocketRoute) -> None:
        def _on_message(message: str | bytes) -> None:
            try:
                ws_messages.append(json.loads(message))
            except (json.JSONDecodeError, TypeError):
                pass
        # ブラウザ→サーバー方向のメッセージを捕捉する
        # （on_message を呼ぶと自動転送が止まるが、テストでは転送不要）
        ws_route.on_message(_on_message)

    page.route_web_socket(WS_URL, _handle_ws)
    yield f"http://localhost:{HTTP_PORT}/index.html"
