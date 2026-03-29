"""
Claude × Tidal 自然言語インターフェース (CLI)
===============================================
自然言語の指示をTidal Cyclesのコードに変換してブリッジに送る。
VS Code のターミナルから実行することを想定している。

使い方:
  python backend/claude_tidal.py "Cマイナーで120BPMにして"
  python backend/claude_tidal.py "もっと暗い雰囲気に、テンポゆっくり"
  python backend/claude_tidal.py --hush          # 全パターンを停止
  python backend/claude_tidal.py --code "hush"   # Tidalコードを直接送る
  python backend/claude_tidal.py --yes "Aマイナーに" # 確認なしで即適用

依存:
  pip install anthropic websockets

環境変数:
  ANTHROPIC_API_KEY  (必須)
  MATOMA_WS_URL      (省略時: ws://localhost:8765)
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

try:
    import anthropic
    from anthropic.types import TextBlock
    import websockets
except ImportError:
    print("依存ライブラリが不足しています。以下を実行してください:", file=sys.stderr)
    print("  pip install anthropic websockets", file=sys.stderr)
    sys.exit(1)

# プロジェクトルートをパスに追加してknowledgeモジュールを使えるようにする
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from knowledge.rag.retriever import KnowledgeRetriever
    _retriever = KnowledgeRetriever()
    _rag_available = True
except Exception:
    _retriever = None
    _rag_available = False

WS_URL = os.environ.get("MATOMA_WS_URL", "ws://localhost:8765")

SYSTEM_PROMPT = """\
あなたはTidal Cyclesのエキスパートです。
ユーザーの日本語の指示をTidal Cyclesのコードに変換してください。

## 利用可能なコマンド（抜粋）

テンポ:
  setcps (120/60/4)   -- 120 BPM、4拍/サイクル

スケール（利用可能な値）:
  "major" "minor" "dorian" "phrygian" "lydian" "mixolydian"
  "locrian" "minPent" "majPent" "wholetone" "chromatic"

コード（利用可能な値）:
  "maj" "min" "dim" "aug" "maj7" "min7" "dom7" "sus2" "sus4"

シンセ:
  "superpiano" "supersaw" "supersquare" "superpwm" "superpad"

パターン例:
  -- コード（Cマイナー）
  d1 $ n (chord "min" + 60) # s "superpiano" # amp 0.5

  -- スケールアルペジオ（Cマイナー、8ステップ）
  d2 $ note (scale "minor" (run 8) + 60) # s "superpiano" # amp 0.4

  -- ドラム
  d3 $ s "bd sn [~ bd] sn" # amp 0.7

  -- 複数行
  setcps (90/60/4)
  d1 $ n (chord "maj7" + 67) # s "superpad" # amp 0.4

## MIDIノート番号（オクターブ4）
  C=60 D=62 E=64 F=65 G=67 A=69 B=71
  （オクターブ変更は ±12 ずつ加算）

## 現在の状態
{current_state}

## 注意
- Tidalコードのみを返してください（説明・マークダウン不要）
- コメントは行末に -- で追加可
- 停止は hush（全パターン）または d1 silence
"""


async def get_current_state() -> dict:
    """ブリッジから現在のTidal状態を取得する。"""
    try:
        async with websockets.connect(WS_URL, open_timeout=2) as ws:
            await ws.send(json.dumps(
                {"address": "/matoma/tidal/state", "args": []}
            ))
            reply = await asyncio.wait_for(ws.recv(), timeout=2.0)
            data = json.loads(reply)
            if data.get("type") == "tidal_state":
                return data.get("state", {})
    except Exception:
        pass  # ブリッジ未起動時はデフォルト値を返す
    # デフォルト値
    return {
        "tempo_bpm": 120,
        "root": "C",
        "scale": "minor",
        "chord": "minor",
        "synth": "superpiano",
        "octave": 4,
    }


async def send_to_bridge(tidal_code: str) -> bool:
    """ブリッジ経由でTidalにコードを送る。"""
    try:
        async with websockets.connect(WS_URL, open_timeout=3) as ws:
            await ws.send(json.dumps({
                "address": "/matoma/tidal/eval",
                "args": [tidal_code],
            }))
            try:
                reply = await asyncio.wait_for(ws.recv(), timeout=3.0)
                data = json.loads(reply)
                if data.get("type") == "tidal_applied":
                    return True
            except asyncio.TimeoutError:
                pass
        return True  # 送信完了（確認なし）
    except ConnectionRefusedError:
        print("エラー: ブリッジ（bridge.py）が起動していません。", file=sys.stderr)
        print("  python backend/bridge.py  で起動してください。", file=sys.stderr)
        return False
    except Exception as e:
        print(f"エラー: {e}")
        return False


def retrieve_rag_context(prompt: str, top_k: int = 3) -> str:
    """プロンプトに関連するSCドキュメントをRAGで取得してテキストに整形する。"""
    if not _rag_available or _retriever is None:
        return ""
    try:
        result = _retriever.query(prompt, n_results=top_k)
        if not result.chunks:
            return ""
        lines = ["## SuperCollider参考ドキュメント（関連度順）"]
        for chunk, score in zip(result.chunks, result.scores):
            lines.append(f"\n### [{chunk.section}] (関連度: {score:.0%})")
            lines.append(chunk.content)
        return "\n".join(lines)
    except Exception:
        return ""


def translate_with_claude(prompt: str, current_state: dict) -> str:
    """Claude APIを使って自然言語をTidalコードに変換する。"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("エラー: ANTHROPIC_API_KEY 環境変数が設定されていません。")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    state_str = json.dumps(current_state, ensure_ascii=False, indent=2)
    system = SYSTEM_PROMPT.format(current_state=state_str)

    rag_context = retrieve_rag_context(prompt)
    if rag_context:
        system = system + "\n\n" + rag_context

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    block = message.content[0]
    if not isinstance(block, TextBlock):
        raise ValueError(f"予期しないレスポンス型: {type(block)}")
    return block.text.strip()


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Claude × Tidal 自然言語インターフェース",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使い方の例:
  python backend/claude_tidal.py "Cマイナーで120BPMにして"
  python backend/claude_tidal.py "もっと暗く、テンポをゆっくりに"
  python backend/claude_tidal.py --code "setcps (90/60/4)"
  python backend/claude_tidal.py --hush
        """,
    )
    parser.add_argument("prompt", nargs="?", help="自然言語の指示")
    parser.add_argument("--code", "-c", metavar="CODE", help="Tidalコードを直接送る")
    parser.add_argument("--hush", action="store_true", help="全パターンを停止")
    parser.add_argument("--yes", "-y", action="store_true", help="確認なしで即適用")
    args = parser.parse_args()

    # 直接停止
    if args.hush:
        ok = await send_to_bridge("hush")
        if ok:
            print("全パターンを停止しました。")
        return

    # Tidalコードを直接送る
    if args.code:
        ok = await send_to_bridge(args.code)
        if ok:
            print(f"適用しました:\n{args.code}")
        return

    # 自然言語 → Tidalコード
    if not args.prompt:
        parser.print_help()
        sys.exit(1)

    print("Claude に翻訳を依頼中...")
    current_state = await get_current_state()
    tidal_code = translate_with_claude(args.prompt, current_state)

    print("\n生成されたTidalコード:")
    print("-" * 40)
    print(tidal_code)
    print("-" * 40)

    if not args.yes:
        answer = input("\n適用しますか？ [Y/n]: ").strip().lower()
        if answer not in ("", "y", "yes"):
            print("キャンセルしました。")
            return

    ok = await send_to_bridge(tidal_code)
    if ok:
        print("適用しました。")


if __name__ == "__main__":
    asyncio.run(main())
