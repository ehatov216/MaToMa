<!-- Generated: 2026-04-05 (updated) | ThreeLayerController移行・SonicAnatomyBridge追加 -->
# Architecture Overview

## System Diagram

```
[Browser UI]  ←→  WebSocket (ws://localhost:8765)
    index.html           ↓
                 [Python Bridge]  backend/bridge.py
                  ↙        ↘
         OSC/UDP            GHCi subprocess
      (127.0.0.1:57200)      (Tidal Cycles)
            ↓                     ↓
    [SuperCollider]          [Tidal Cycles]
     sc/run_headless.scd      Haskell patterns
            ↓
       Audio Output
```

## Layer Responsibilities

| Layer | Tech | Role |
|-------|------|------|
| UI | HTML+JS | ユーザー操作・パラメーター可視化 |
| Bridge | Python (asyncio) | OSC⇔WebSocket変換・自律制御 |
| SC | SuperCollider | リアルタイム音響合成 |
| Tidal | Haskell/GHCi | パターン・リズム生成 |

## Core Pipeline

```
Human (Browser) → WS → bridge.py → OSC → SC → Audio
                              ↓
                    ThreeLayerController（3層統合制御）
                        ├── UpperLayer   (Markov状態機械, 60秒ごと)
                        │     → STATE_ZONES/STATE_CONTROLS から UpperControl 生成
                        │     → Tidalプリセット自動切換え
                        ├── _middle_next (BoundedWalk, 0.1秒ごと)
                        └── _lower_next  (Dejavu, 0.1秒ごと) → OSC送信
                    TuringSequencer  (Turingステップ)
                    TidalController  (パターン生成)
                    SonicAnatomyBridge (SA DB → Tidalシード生成)
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
```

## 4-Layer Musical Time Control (SPEC.md)

```
Song Form  (数分)        ← UpperLayer (void→intense Markov遷移)
Section    (8-32小節)    ← 人間がプリセットシーン選択 / SonicAnatomyBridge
Phrase     (1-4小節)     ← _middle_next (BoundedWalk ドリフト)
Parameter  (ms-秒)      ← _lower_next (Dejavu微変動) + TuringSequencer
```
