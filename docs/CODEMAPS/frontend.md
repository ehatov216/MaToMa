<!-- Generated: 2026-04-11 | Files scanned: frontend/index.html (866行) | 2タブGUI全面刷新 -->
# Frontend Architecture

## Stack

- HTML5 + 純JavaScript（フレームワーク不使用）
- WebSocket: `ws://localhost:8765`
- 1ファイル構成: `frontend/index.html` (866行)

## UI 構成（2タブ）

```
Tab 1: SIGNAL FLOW  — ライブパフォーマンス用（デフォルト表示）
Tab 2: SC NODE TREE — 開発・デバッグ用
```

## SIGNAL FLOW タブ

5ノードパイプライン（クリックで詳細パネル展開）:

```
KEY → HARMONY → RHYTHM → SYNTH → OUT

各ノード:
  KEY     — スケール・ルート表示 (flow_state受信で更新)
  HARMONY — コード進行・モード表示 (flow_state受信で更新)
  RHYTHM  — Tidalプリセット・BPM表示 + Markov状態ボタン (5状態)
  SYNTH   — SCエンジン制御 (free_all / refresh_tree)
  OUT     — マスター音量スライダー
```

### 詳細パネル（各ノードクリック時に展開）

```
KEY パネル:
  状態表示: root / scale / mode
  UpperLayer 遷移ボタン: void / sparse / medium / dense / intense
    → /matoma/markov/set_state (controller._upper.force_state で即時適用)

HARMONY パネル:
  状態表示: chord / degree
  Markov遷移方向ボタン (UpperLayer 状態誘導)

RHYTHM パネル:
  Tidalプリセット表示
  BPM表示
  次の Markov 遷移までの残り秒数

SYNTH パネル:
  [FREE ALL]    → /matoma/sc/free_all → scsynth /g_freeAll [0]
  [REFRESH TREE] → /matoma/sc/query_tree → scsynth /g_queryTree [0,0]

OUT パネル:
  マスター音量スライダー → /matoma/master/amp
```

## SC NODE TREE タブ

```
6秒ごとに /g_queryTree を scsynth (port 57110) へ送信
← /g_queryTree.reply → _parse_node_tree() → broadcast("sc_node_tree")
← WS受信 → renderTree() → Group/Synth 階層ツリーをHTML表示

ヘッダー:
  SC STATUS バッジ (connected/disconnected)
  [START] → /matoma/sc/start
  [STOP]  → /matoma/sc/stop
  [REBOOT] → /matoma/sc/reboot
```

## JavaScript 主要関数

```javascript
// 接続・通信
connect()              — WebSocket接続・再接続（3秒リトライ）
send(address, args)    — OSCメッセージ送信 ({address, args})
onMessage(event)       — WS受信ディスパッチ

// ノードクリック → パネル切替
openPanel(nodeId)      — 詳細パネル展開・switch(nodeId)でdetailXxx()呼び出し

// 詳細パネル生成
detailKey()            — KEY パネルHTML生成
detailHarmony()        — HARMONY パネルHTML生成
detailRhythm()         — RHYTHM パネルHTML生成
detailSynth()          — SYNTH パネルHTML生成 (btn-free-all, btn-refresh-tree)
detailOut()            — OUT パネルHTML生成

// イベントバインド（パネル生成後に呼ぶ）
bindKey()              — UpperLayer状態ボタン → /matoma/markov/set_state
bindHarmony()          — Markov方向ボタン
bindRhythm()           — Tidalプリセット・BPM
bindSynth()            — btn-free-all → /matoma/sc/free_all
                         btn-refresh-tree → /matoma/sc/query_tree
bindOut()              — マスター音量スライダー

// 表示更新
updateFlowState(msg)   — flow_state受信 → KEY/HARMONY/RHYTHM ノード表示更新
updateMarkovState(msg) — markov_state受信 → 状態バッジ・残り秒数更新
renderTree(nodes)      — sc_node_tree受信 → Group/Synth ツリーHTML生成
updateSCStatus(ready)  — SC STATUS バッジ更新
```

## WebSocket メッセージ受信タイプ

```
flow_state      → {"type":"flow_state", "key":{root,scale,mode}, "harmony":{chord,degree}, "rhythm":{preset,bpm}}
                  → updateFlowState() → KEY/HARMONY/RHYTHM ノード表示更新
markov_state    → {"type":"markov_state", "state":{name,remaining,interval,...}}
                  → updateMarkovState() → Markov状態バッジ・残り秒数更新
sc_node_tree    → {"type":"sc_node_tree", "nodes":[...]}
                  → renderTree() → SC NODE TREE タブ更新
sc_ready        → {"type":"sc_ready"} → updateSCStatus(true)
sc_status       → {"type":"sc_status", "ready":bool} → updateSCStatus(bool)
sc_booting      → {"type":"sc_booting", "message":"..."} → 起動中メッセージ表示
chaos_state     → {"type":"chaos_state", "state":{...}} → モニター更新（必要時）
```

## State Flow

```
ユーザー操作 (ノードクリック → 状態ボタン / スライダー)
  → send(address, args)
  → ws.send(JSON)
  → [bridge.py]
  → ThreeLayerController or sc_synth_client

Python フィードバック
  → bridge.py: broadcast()
  → ws.onmessage → onMessage()
  → updateFlowState() / updateMarkovState() / renderTree() → UI更新
```
