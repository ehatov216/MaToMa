<!-- Generated: 2026-04-04 (updated) | Files scanned: 11 Python files | Token estimate: ~1000 -->
# Backend Architecture

## Entry Point

`backend/bridge.py` (1110行) — asyncio メインプロセス。OSCサーバー(9000) + WebSocketサーバー(8765) を同時起動。

## OSC Routes (SC → Python, port 9000)

```
/matoma/ready            → SC起動完了通知 → broadcast("sc_ready")
/matoma/seq/tick         → シーケンサーステップ → broadcast("seq_tick")
/matoma/granular/density → グレイン密度 → broadcast("granular_density")
/matoma/rhythmic/trigger → rhythmic シンセトリガー → broadcast("rhythmic_trigger")
/matoma/rhythmic/load    → rhythmic サンプルロード → broadcast("rhythmic_loaded")
```

## WebSocket Routes (Browser → Python, port 8765)

```
# シーン・基本制御
/matoma/scene                  → scenes.py.get_scene() → OSC複数送信
/matoma/param                  → sc_client → /matoma/param
/matoma/all/stop               → s.freeAll
/matoma/all/restart            → SC再起動

# ドローン・グラニュラー
/matoma/drone/param            → sc_client → /matoma/drone/param
/matoma/granular/param         → sc_client → /matoma/granular/param
/matoma/granular/load          → sc_client → /matoma/granular/load
/matoma/granular/browse        → macOSファイル選択ダイアログ
/matoma/gran_synth/start|stop  → sc_client
/matoma/gran_synth/param       → sc_client
/matoma/gran_sampler/browse    → macOSファイル選択ダイアログ

# ChaosEngine制御
/matoma/chaos/start            → chaos_engine.start()
/matoma/chaos/stop             → chaos_engine.stop()
/matoma/chaos/state            → chaos_engine.get_state() → broadcast
/matoma/chaos/attractor        → chaos_engine.set_attractor(layer, param, value)
/matoma/chaos/speed            → chaos_engine.set_speed(value)
/matoma/chaos/dejavu           → chaos_engine.set_dejavu_prob(prob)

# Markov上位レイヤー
/matoma/markov/start           → markov.start()
/matoma/markov/stop            → markov.stop()
/matoma/markov/interval        → markov.set_interval(seconds)
/matoma/markov/state           → markov.get_state() → broadcast

# ランダマイズモデル選択
/matoma/layer/middle/model     → chaos_engine.set_middle_model(name)
/matoma/layer/lower/model      → chaos_engine.set_lower_model(name)
/matoma/layer/middle/chaos     → chaos_engine.set_middle_chaos(ratio)  ★新規
/matoma/layer/lower/chaos      → chaos_engine.set_lower_chaos(ratio)   ★新規

# その他
/matoma/audio/get_devices      → pyaudio → broadcast(device_list)
/matoma/audio/set_device       → scsynth再起動
/matoma/drop/state             → sc_client → /matoma/drop/state
/matoma/energy/set             → sc_client → エネルギー設定
/matoma/master/amp             → sc_client → マスター音量
/matoma/tidal/*                → tidal_controller.py
```

## Module Map

```
bridge.py (1110行)
  ├── start_sc()                — sclang起動・bootstrap
  ├── ws_handler()              — WebSocket接続管理・ルーティング
  ├── on_osc_message()          — SC→Python OSC受信
  ├── broadcast()               — 全クライアントWS送信
  ├── _handle_tidal()           — Tidal Cyclesコマンド処理
  ├── _handle_granular_browse() — macOSファイル選択
  ├── _convert_mp3_to_wav()     — MP3→WAV変換 (ffmpeg)
  ├── _acquire_pid_lock()       — 多重起動防止
  └── Global: chaos_engine, markov, autonomous, tidal, sequencer

markov_timescale.py (359行) — class MarkovTimescale
  ├── __init__(chaos_engine, broadcast, interval, tidal_controller)
  ├── start() / stop()
  ├── set_interval(seconds)
  ├── get_state() → {running, state, interval, elapsed, remaining, speed, dejavu_prob}
  ├── _loop()                   — 1秒ごとカウントダウン + broadcast
  ├── _next_state()             — Markov 70% + エネルギーフィードバック 30%
  ├── _compute_energy()         — 4ソース加重平均（gran×0.30, synth×0.25, sampler×0.25, drone×0.20）
  └── _apply_state(state)       — 引力点 + speed/dejavu_prob → ChaosEngine + Tidal自動切換え
  定数: STATES×5, STATE_ATTRACTORS, STATE_GLOBALS, BASE_MATRIX, TIDAL_PRESET_BY_STATE

autonomous.py (716行)
  ├── class AutonomousMode      — 旧自律モード（非推奨。ChaosEngineに移行）
  └── class ChaosEngine         — 確率的パラメーター変化エンジン
      ├── start() / stop()
      ├── set_attractor(layer, param, value)
      ├── set_speed(speed)
      ├── set_dejavu_prob(prob)  — duck typing で DynamicBlendLower にも委譲
      ├── set_middle_model(name) — bounded_walk/fractal/lsystem/blend
      ├── set_lower_model(name)  — dejavu/bounded_walk/lsystem/blend
      ├── set_lower_chaos(ratio) — DynamicBlendLower.set_ratio() へ委譲
      ├── set_middle_chaos(ratio)— DynamicBlendMiddle.set_ratio() へ委譲
      ├── set_scene(scene)
      └── get_state() → {layer: {param: {value, attractor, ...}}}

randomize_models.py (405行)  ★新規
  ├── Protocol RandomizeModel   — next_value(current, attractor, lo, hi) → float
  ├── BoundedWalkModel          — 引力点へのドリフト + ランダム摂動
  ├── DejavuModel               — 過去状態への確率的スナップバック
  ├── FractalModel              — 1/fノイズ（複数正弦波重ね合わせ）
  ├── LSystemModel              — フレーズ蓄積 + ルール変換による次値予測
  ├── DynamicBlendLower         — Dejavu↔BoundedWalk 動的ブレンド ★新規
  │   ├── set_ratio(0〜1)       — 0=Dejavu, 1=BoundedWalk
  │   └── set_snap_prob()       — 内部DejavuModelへ委譲
  ├── DynamicBlendMiddle        — LSystem↔BoundedWalk 動的ブレンド ★新規
  │   └── set_ratio(0〜1)       — 0=LSystem, 1=BoundedWalk
  ├── blend(models, weights, ...) — 重み付き平均関数
  ├── _make_middle(name)        — モデル名→中位モデルインスタンス
  └── _make_lower(name)         — モデル名→下位モデルインスタンス

scenes.py (130行)
  ├── load_scenes()
  ├── get_scene(name)
  └── scene_to_osc_messages()

sequencer.py (208行) — class TuringSequencer
  ├── start() / stop()
  ├── set_bpm(20-300)
  ├── set_trig_prob(prob)
  ├── set_mutation_prob(prob)
  └── get_state()

tidal_controller.py (224行) — class TidalController
  ├── start(boot_path) / stop()
  ├── evaluate(code)
  ├── set_tempo(bpm)
  └── hush()

tidal_patterns.py (244行) — パターン生成ヘルパー関数群

claude_tidal.py (250行) — Claude API統合
  ├── retrieve_rag_context(prompt) — ChromaDB検索
  └── translate_with_claude(prompt, state) — 日本語→Tidalコード変換

param_mapper.py (129行) — パラメーター正規化・マッピング

turing_gene.py (285行) — 遺伝的アルゴリズムによるパターン進化
```

## 3層タイムスケールアーキテクチャ

```
MarkovTimescale（上位, 30s〜5min）
  状態: void / sparse / medium / dense / intense
  制御: Markov 70% + エネルギーフィードバック 30%
        ↓ 引力点 + speed/dejavu_prob を設定
        ↓ Tidalプリセット自動切換え（TIDAL_PRESET_BY_STATE）
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

## Global State (bridge.py)

```python
connected_clients: set[WebSocket]
sc_client: SimpleUDPClient          # SC送信 (OSC/UDP, port 57120)
chaos_engine: ChaosEngine           # メインエンジン（4レイヤー: gran/drone/synth/sampler）
markov: MarkovTimescale(chaos_engine, broadcast, tidal_controller=tidal)
autonomous: AutonomousMode          # 旧自律モード（非推奨）
tidal: TidalController
sequencer: TuringSequencer
sc_ready: bool
```
