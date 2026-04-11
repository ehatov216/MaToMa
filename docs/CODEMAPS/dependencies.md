<!-- Generated: 2026-04-11 | Files scanned: requirements.txt, pyproject.toml | SC_SYNTH_PORT追加 -->
# Dependencies & Integrations

## External Processes (ランタイム依存)

| プロセス | 起動方法 | 通信 | ポート |
|---------|---------|------|-------|
| SuperCollider (sclang) | bridge.py から自動起動 | OSC/UDP | SC→Python: 9000, Python→SC(sclang): 57200 |
| scsynth (SCサーバー) | sclang 内部から自動起動 | OSC/UDP (native) | Python→scsynth: 57110 |
| Tidal Cycles (GHCi) | TidalController.start() | stdin/stdout | — |

## Python Dependencies (requirements.txt)

```text
python-osc       # OSC送受信 (pythonosc) — SimpleUDPClient × 2 (port 57200, 57110)
websockets       # WebSocketサーバー
asyncio          # 非同期I/O (標準ライブラリ)
chromadb         # ベクトルDB (RAG用)
anthropic        # Claude API (claude_tidal.py)
pytest           # テストフレームワーク
pytest-asyncio   # 非同期テスト
pytest-playwright # E2Eテスト
```

## SuperCollider UGen / Quarks

```text
標準UGen:
  SinOsc, SinOscFB, Saw, LFSaw  — 基本オシレーター
  RLPF                           — レゾナントローパスフィルター
  FreeVerb2, GVerb               — リバーブ
  GrainSin, TGrains              — グラニュラー合成 (gran_synth)
  GrainBuf                       — バッファ読込グラニュラー合成 (gran_sampler)
  PV_*                           — スペクトル処理

Quarks (要インストール):
  Fb1                            — カオス・フィードバック
  DXMix                          — クロスフェード
  WaveFolder                     — ウェーブフォールド
```

## Tidal Cycles Dependencies

```text
GHC (Haskell compiler)
Cabal または Stack
tidal (Haskell package)
BootTidal.hs (自動検出: ~/.cabal/share/tidal/ or ~/.local/share/tidal/)
SuperDirt (SuperCollider Quark)
```

## Knowledge RAG (knowledge/rag/)

```text
chromadb    — ベクトルDB・類似検索
sources/    — Markdownファイル群 (手動管理)
```

## 開発ツール

```text
ruff        — Python linter/formatter (pyproject.toml設定)
pytest      — テストフレームワーク
pytest-asyncio — 非同期テスト
playwright  — E2Eテスト
```

## macOS 固有

```text
tkinter     — ファイル選択ダイアログ (_handle_granular_browse, _handle_gran_sampler_browse)
sqlite3     — Sonic Anatomy SQLite DB読込 (stdlib)
sclang      — /Applications/SuperCollider.app/Contents/MacOS/sclang
```

## 通信プロトコル

```text
WebSocket JSON フォーマット:
  送信: {"address": "/matoma/param", "args": ["freq", 220]}
  受信: {"type": "flow_state", "key": {...}, "harmony": {...}, "rhythm": {...}}
        {"type": "sc_node_tree", "nodes": [...]}
        {"type": "markov_state", "state": {...}}

OSC フォーマット (sclang, port 57200):
  /matoma/param "freq" 220.0
  /matoma/drone/param "cutoff" 1200.0

OSC フォーマット (scsynth native, port 57110):
  /g_queryTree 0 0    — SCノードツリー取得要求
  /g_freeAll   0      — 全シンセ解放
  /g_queryTree.reply  — scsynth からの応答 → _parse_node_tree() → broadcast("sc_node_tree")
```
