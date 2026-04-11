<!-- Generated: 2026-04-11 | Files scanned: 6 | Token estimate: ~700 -->
# Architecture Overview

## System Diagram

```
[Browser UI]  ←→  WebSocket (ws://localhost:8765)
    index.html           ↓
                 [Python Bridge]  backend/bridge.py
                  ↙        ↘
         OSC/UDP            GHCi subprocess
      (127.0.0.1:57200)      (Tidal Cycles)
      (127.0.0.1:57110)  ← scsynth native (/g_queryTree)
            ↓                     ↓
    [SuperCollider]          [Tidal Cycles]
     sc/run_headless.scd      Haskell patterns
            ↓
       Audio Output
```

## Layer Responsibilities

| Layer | Tech | Role |
|-------|------|------|
| UI | HTML+JS (866行) | 2タブGUI: Signal Flow + SC Node Tree |
| Bridge | Python (asyncio, 1446行) | OSC⇔WebSocket変換・自律制御・ノードツリー取得 |
| SC | SuperCollider | リアルタイム音響合成 |
| Tidal | Haskell/GHCi | パターン・リズム生成 |

## Core Pipeline

```
Human (Browser) → WS → bridge.py → OSC(57200) → SC → Audio
                              ↓
                    ThreeLayerController（3層統合制御）
                        ├── UpperLayer   (Markov状態機械, 60秒ごと)
                        │     → STATE_ZONES/STATE_CONTROLS から UpperControl 生成
                        │     → Tidalプリセット自動切換え
                        ├── _middle_next (BoundedWalk, 0.1秒ごと)
                        └── _lower_next  (Dejavu, 0.1秒ごと) → OSC送信
                    MusicGenerator（Multi-timescale Tidalコード生成）
                        ├── UpperLayer (~60-120秒): Markov スケール遷移
                        ├── MiddleLayer (~4-8秒):  GravityMatrix コード度数選択
                        └── LowerLayer (~1-2秒):   Tidal d1-d6 コード送信
                        ← SCENE_DNA + SonicAnatomyRecord でシード
                        ← SA activity multiplier で speed 抑制
                    TidalController  (パターン生成)
                    SonicAnatomyBridge (SA DB → Tidalシード生成)

[scsynth native] ←→ OSC(57110) ← bridge.py → /g_queryTree
    /g_queryTree.reply → _parse_node_tree() → broadcast(sc_node_tree)
```

## GUI 設計思想（2タブ構成）

```
SIGNAL FLOW タブ（ライブパフォーマンス用）
  KEY → HARMONY → RHYTHM → SYNTH → OUT の5ノードパイプライン
  各ノードをクリック → 詳細パネルが展開して「方向制御」を提供
  ThreeLayerController が全パラメーターを自律更新するため
  UIは「細かいパラメーター制御」ではなく「状態・方向の選択」を行う

SC NODE TREE タブ（開発・デバッグ用）
  /g_queryTree.reply を6秒ごとにポーリング
  Group/Synth の階層ツリーをリアルタイム表示
```

## 3層タイムスケールアーキテクチャ

```
UpperLayer（上位, 60秒 Markov）
  状態: void / sparse / medium / dense / intense（5状態）
  制御: Markov 70% + エネルギーフィードバック 30%
        ↓ UpperControl(center, width, speed, snap_prob, micro_range) を生成
        ↓ Tidalプリセット自動切換え（TIDAL_PRESET_BY_STATE）
           void→minimal_klank, sparse→opn_sparse, medium→alva_euclidean,
           dense→alva_phase, intense→chaos_collapse
─────────────────────────────────────────────
_middle_next（中位, 0.1秒更新）
  アルゴリズム: BoundedWalk（固定実装）
  動作: Upper の center に引き寄せられながら width 内をドリフト
─────────────────────────────────────────────
_lower_next（下位, 0.1秒更新）
  アルゴリズム: Dejavu（固定実装）
  動作: middle ± micro_range で微変動、snap_prob で過去値へスナップバック
  → OSC送信: _send_osc(osc_address, [param, new_current])
```

## Startup Flow

```
start.sh
  → pkill sclang (競合プロセスkill)
  → python backend/bridge.py
      → sclang sc/run_headless.scd  (SC起動)
      → OSCserver 127.0.0.1:9000    (SC→Python受信)
      → WebSocketserver :8765       (Browser接続)
      → _periodic_state_broadcast() (2秒周期: flow_state + chaos_state)
      → /g_queryTree ポーリング     (6秒周期: sc_synth_client → port 57110)
```

## 4-Layer Musical Time Control (SPEC.md)

```
Song Form  (数分)        ← UpperLayer (void→intense Markov遷移)
Section    (8-32小節)    ← 人間がMarkov状態ボタン選択 / SonicAnatomyBridge
Phrase     (1-4小節)     ← _middle_next (BoundedWalk ドリフト)
Parameter  (ms-秒)      ← _lower_next (Dejavu微変動) + TidalController
```
