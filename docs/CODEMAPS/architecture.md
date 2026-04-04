<!-- Generated: 2026-04-04 (updated) | Files scanned: 48 | Token estimate: ~700 -->
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
                    MarkovTimescale  (上位: 30s〜5min)
                        ↓ 引力点設定
                    ChaosEngine      (中位+下位: ms〜2拍)
                        ├── _middle_model (BoundedWalk/Fractal/LSystem/Blend)
                        └── _lower_model  (Dejavu/BoundedWalk/LSystem/Blend)
                    TuringSequencer  (Turingステップ)
                    TidalController  (パターン生成)
```

## 3層タイムスケールアーキテクチャ

```
MarkovTimescale（上位, 30s〜5min）
  状態: void / sparse / medium / dense / intense
  制御: Markov 70% + エネルギーフィードバック 30%
        ↓ 引力点 + speed/dejavu_prob を設定
        ↓ Tidalプリセット自動切換え（TIDAL_PRESET_BY_STATE）
           void→minimal_klank, sparse→opn_sparse, medium→alva_euclidean,
           dense→alva_phase, intense→chaos_collapse
─────────────────────────────────────────────
ChaosEngine._middle_model（中位, 2s〜16拍）
  選択: BoundedWalk / Fractal / LSystem / DynamicBlendMiddle
  人間制御: REPEAT↔CHAOS スライダー（0=LSystem, 1=BoundedWalk）
─────────────────────────────────────────────
ChaosEngine._lower_model（下位, 0.1s〜2拍）
  選択: Dejavu / BoundedWalk / LSystem / DynamicBlendLower
  人間制御: REPEAT↔CHAOS スライダー（0=Dejavu, 1=BoundedWalk）
  Markov制御: dejavu_prob（set_snap_prob経由で委譲）
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
Song Form  (数分)        ← MarkovTimescale (void→intense遷移)
Section    (8-32小節)    ← 人間がプリセットシーン選択
Phrase     (1-4小節)     ← ChaosEngine (中位モデル)
Parameter  (ms-秒)      ← ChaosEngine (下位モデル) + TuringSequencer
```
