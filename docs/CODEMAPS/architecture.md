<!-- Generated: 2026-03-29 | Files scanned: 48 | Token estimate: ~600 -->
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
                    autonomous.py (確率的自律)
                    sequencer.py  (Turingステップ)
                    tidal.py      (パターン生成)
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

## 4-Layer Time Control (SPEC.md)

```
Song Form  (数分)    ← 人間が Tidal でコード進行
Section    (8-32小節) ← 人間がプリセットシーン選択
Phrase     (1-4小節)  ← 半自動 (autonomous.py)
Parameter  (ms-秒)   ← SC内部カオス / sequencer.py
```
