<!-- Generated: 2026-03-29 | Files scanned: requirements.txt, pyproject.toml | Token estimate: ~350 -->
# Dependencies & Integrations

## External Processes (ランタイム依存)

| プロセス | 起動方法 | 通信 | ポート |
|---------|---------|------|-------|
| SuperCollider (sclang) | bridge.py から自動起動 | OSC/UDP | SC→Python: 9000, Python→SC: 57200 |
| Tidal Cycles (GHCi) | TidalController.start() | stdin/stdout | — |

## Python Dependencies (requirements.txt)

```
python-osc       # OSC送受信 (pythonosc)
websockets       # WebSocketサーバー
asyncio          # 非同期I/O (標準ライブラリ)
chromadb         # ベクトルDB (RAG用)
anthropic        # Claude API (claude_tidal.py)
pytest           # テストフレームワーク
pytest-asyncio   # 非同期テスト
pytest-playwright # E2Eテスト
```

## SuperCollider UGen / Quarks

```
標準UGen:
  SinOsc, SinOscFB, Saw, LFSaw  — 基本オシレーター
  RLPF                           — レゾナントローパスフィルター
  FreeVerb2, GVerb               — リバーブ
  GrainSin, TGrains              — グラニュラー合成
  PV_*                           — スペクトル処理

Quarks (要インストール):
  Fb1                            — カオス・フィードバック
  DXMix                          — クロスフェード
  WaveFolder                     — ウェーブフォールド
```

## Tidal Cycles Dependencies

```
GHC (Haskell compiler)
Cabal または Stack
tidal (Haskell package)
BootTidal.hs (自動検出: ~/.cabal/share/tidal/ or ~/.local/share/tidal/)
SuperDirt (SuperCollider Quark)
```

## Knowledge RAG (knowledge/rag/)

```
chromadb    — ベクトルDB・類似検索
sources/    — 17個のMarkdownファイル (手動管理)
```

## 開発ツール

```
ruff        — Python linter/formatter (pyproject.toml設定)
pytest      — テストフレームワーク
pytest-asyncio — 非同期テスト
playwright  — E2Eテスト (test_ui.py)
```

## macOS 固有

```
tkinter     — ファイル選択ダイアログ (_handle_granular_browse)
sclang      — /Applications/SuperCollider.app/Contents/MacOS/sclang
```

## 通信プロトコル

```
WebSocket JSON フォーマット:
  送信: {"address": "/matoma/param", "args": ["freq", 220]}
  受信: {"type": "sc_ready"} / {"type": "seq_tick", "step": 3, ...}

OSC フォーマット:
  /matoma/param "freq" 220.0
  /matoma/drone/param "cutoff" 1200.0
```
