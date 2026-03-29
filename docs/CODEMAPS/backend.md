<!-- Generated: 2026-03-29 | Files scanned: 9 Python files | Token estimate: ~700 -->
# Backend Architecture

## Entry Point

`backend/bridge.py` — asyncio メインプロセス。OSCサーバーとWebSocketサーバーを同時起動。

## OSC Routes (SC → Python, port 9000)

```
/matoma/ready           → SC起動完了通知 → broadcast("sc_ready")
/matoma/seq/tick        → シーケンサーステップ → broadcast("seq_tick")
/matoma/granular/density → グレイン密度 → broadcast("granular_density")
```

## WebSocket Routes (Browser → Python, port 8765)

```
/matoma/scene           → scenes.py.get_scene() → OSC複数送信
/matoma/param           → sc_client.send_message("/matoma/param", ...)
/matoma/drone/param     → sc_client.send_message("/matoma/drone/param", ...)
/matoma/granular/param  → sc_client.send_message("/matoma/granular/param", ...)
/matoma/granular/load   → sc_client.send_message("/matoma/granular/load", ...)
/matoma/granular/browse → _handle_granular_browse() → ファイル選択ダイアログ
/matoma/spectral/param  → sc_client.send_message("/matoma/spectral/param", ...)
/matoma/auto/*          → autonomous.py のメソッド呼び出し
/matoma/seq/*           → sequencer.py のメソッド呼び出し
/matoma/tidal/*         → _handle_tidal() → tidal_controller.py
```

## Module Map

```
bridge.py (586行)
  ├── start_sc()              — sclang起動・ブートstrap
  ├── ws_handler()            — WebSocket接続管理・ルーティング
  ├── on_osc_message()        — SC→Python OSC受信
  ├── broadcast()             — 全クライアントWS送信
  ├── _handle_tidal()         — Tidal Cyclesコマンド処理
  ├── _handle_seq()           — シーケンサー制御
  └── _handle_granular_browse() — macOSファイル選択

scenes.py (46行)
  ├── load_scenes()           — scenes.json 読み込み
  ├── get_scene(name)         — 名前でシーン取得
  └── scene_to_osc_messages() — シーン→OSCリスト変換

autonomous.py (307行) — class AutonomousMode
  ├── start() / stop()
  ├── set_mode("random"|"directed")
  ├── set_speed(0.0-1.0)
  ├── set_trig_prob(prob)     — 各パラメーター変化確率
  ├── set_dejavu_prob(prob)   — 履歴再生確率
  ├── set_dejavu_len(1-32)    — 履歴参照深さ
  ├── set_tidal_auto(bool)    — Tidal自動コード進行
  ├── set_progression(name)  — コード進行プリセット変更
  └── sync_current(param, val) — 手動操作値の同期

sequencer.py (209行) — class TuringSequencer
  ├── start() / stop()
  ├── set_bpm(20-300)
  ├── set_step_div("1/4"|"1/8"|"1/16"|"1/32")
  ├── set_trig_prob(prob)
  ├── set_mutation_prob(prob)
  ├── set_step_enabled(idx, bool)
  ├── set_active_params([...])
  └── get_state()

tidal_controller.py — class TidalController
  ├── start(boot_path)        — GHCi起動
  ├── stop()                  — 全停止
  ├── evaluate(code)          — Tidalコード実行
  ├── set_tempo(bpm)
  └── hush()

tidal_patterns.py — パターン生成ヘルパー
  ├── tempo_to_cps(bpm, beats_per_cycle)
  ├── make_chord_pattern(...)
  ├── make_scale_pattern(...)
  ├── make_arp_pattern(...)
  └── make_drum_pattern(...)
```

## Global State (bridge.py)

```python
connected_clients: set[WebSocket]   # 接続中ブラウザ
sc_client: SimpleUDPClient          # SC送信 (OSC/UDP)
autonomous: AutonomousMode          # 自律モードインスタンス
tidal: TidalController              # Tidal Cyclesインスタンス
sequencer: TuringSequencer          # シーケンサーインスタンス
sc_ready: bool                      # SCブートフラグ
```

## Key Data: PARAM_SPECS (autonomous.py)

```python
"freq"         → /matoma/param       55-880 Hz
"cutoff"       → /matoma/param       200-8000 Hz
"drone_freq"   → /matoma/drone/param 40-220 Hz
"drone_detune" → /matoma/drone/param 0-1
"drone_cutoff" → /matoma/drone/param 80-3000 Hz
"drone_drift"  → /matoma/drone/param 0-1
"drone_room"   → /matoma/drone/param 0-1
```

## Key Data: SEQ_PARAMS (sequencer.py)

```python
"drone_cutoff"   400-2800 Hz
"drone_drift"    0-0.6
"spectral_smear" 0.1-0.9
"spectral_chaos" 0.1-0.8
```
