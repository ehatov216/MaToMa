<!-- Generated: 2026-04-11 | Files scanned: 8 | Token estimate: ~1200 -->
# Backend Architecture

## Entry Point

`backend/bridge.py` (1446行) — asyncio メインプロセス。OSCサーバー(9000) + WebSocketサーバー(8765) を同時起動。

## OSC Routes (SC → Python, port 9000)

```
/matoma/ready            → SC起動完了通知 → broadcast("sc_ready") + controller.start()
/matoma/seq/tick         → シーケンサーステップ → broadcast("seq_tick")
/matoma/granular/density → グレイン密度 → broadcast("granular_density")
/matoma/rhythmic/trigger → rhythmic シンセトリガー → broadcast("rhythmic_trigger")
/matoma/rhythmic/load    → rhythmic サンプルロード → broadcast("rhythmic_loaded")
/g_queryTree.reply       → _parse_node_tree() → broadcast("sc_node_tree")
```

## WebSocket Routes (Browser → Python, port 8765)

```
# シーン・基本制御
/matoma/scene                  → scenes.py.get_scene() → controller.set_scene()
/matoma/param                  → sc_client → /matoma/param
/matoma/all/stop               → s.freeAll
/matoma/all/restart            → SC再起動

# SC直接制御
/matoma/sc/start               → start_sc() → SC起動
/matoma/sc/stop                → pkill sclang/scsynth + sc_process.terminate()
/matoma/sc/reboot              → start_sc() → SC再起動
/matoma/sc/free_all            → sc_synth_client.send_message("/g_freeAll", [0])
/matoma/sc/query_tree          → sc_synth_client.send_message("/g_queryTree", [0, 0])

# ドローン・グラニュラー
/matoma/drone/param            → sc_client → /matoma/drone/param
/matoma/granular/param         → sc_client → /matoma/granular/param
/matoma/granular/load          → sc_client → /matoma/granular/load
/matoma/granular/browse        → macOSファイル選択ダイアログ
/matoma/gran_synth/start|stop  → sc_client
/matoma/gran_synth/param       → sc_client
/matoma/gran_sampler/browse    → macOSファイル選択ダイアログ

# 3層制御システム（ThreeLayerController）
/matoma/chaos/start            → controller.start()
/matoma/chaos/stop             → controller.stop()
/matoma/chaos/state            → controller.get_state() → broadcast
/matoma/chaos/attractor        → controller.set_attractor(layer, param, value, range)
/matoma/chaos/speed            → controller.set_speed(value)
/matoma/chaos/dejavu           → controller.set_dejavu_prob(prob)

# Markov上位レイヤー（UpperLayer）
/matoma/markov/start           → controller.start_markov()
/matoma/markov/stop            → controller.stop_markov()
/matoma/markov/interval        → controller.set_markov_interval(seconds)
/matoma/markov/state           → controller.get_markov_state() → broadcast
/matoma/markov/set_state       → controller._upper.force_state(state_name) → broadcast("markov_state")

# ランダマイズモデル選択（現バージョンは固定実装）
/matoma/layer/middle/model     → controller.set_middle_model(name)  — BoundedWalk固定
/matoma/layer/lower/model      → controller.set_lower_model(name)   — Dejavu固定
/matoma/layer/middle/chaos     → controller.set_middle_chaos(ratio) — speed変換
/matoma/layer/lower/chaos      → controller.set_lower_chaos(ratio)  — dejavu_prob変換

# Sonic Anatomy Bridge
/matoma/sonic_anatomy/load            → load_record(None) → broadcast("sonic_anatomy_seed")
/matoma/sonic_anatomy/load/<track_id> → load_record(track_id) → broadcast("sonic_anatomy_seed")
/matoma/sonic_anatomy/apply           → _apply_seed(seed, rhythm=True, harmony=True)
/matoma/sonic_anatomy/apply_rhythm    → _apply_seed(seed, rhythm=True, harmony=False)
/matoma/sonic_anatomy/apply_harmony   → _apply_seed(seed, rhythm=False, harmony=True)
/matoma/sonic_anatomy/catalog         → load_catalog() → broadcast("sonic_anatomy_catalog")

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
bridge.py (1446行)
  ├── start_sc()                — sclang起動・bootstrap
  ├── ws_handler()              — WebSocket接続管理・ルーティング
  ├── on_osc_message()          — SC→Python OSC受信（/matoma/ready で controller自動起動）
  │   /g_queryTree.reply → _parse_node_tree() → broadcast(sc_node_tree)
  ├── _parse_node_tree()        — /g_queryTree.reply の args を再帰的にパースしてdict化
  ├── broadcast()               — 全クライアントWS送信
  ├── _send_osc()               — SC へ OSC 送信（Studio Mode 用ブロードキャスト付き）
  ├── _periodic_state_broadcast() — 2秒周期: flow_state + chaos_state + /g_queryTree(6秒周期)
  ├── _handle_tidal()           — Tidal Cyclesコマンド処理
  ├── _handle_sonic_anatomy()   — /matoma/sonic_anatomy/* ルーティング
  ├── _apply_seed()             — SA シードを Tidal へ適用（rhythm/harmonyオプション）
  ├── _handle_gran_sampler_browse() — macOSファイル選択（Gran Sampler用）
  ├── _handle_granular_browse() — macOSファイル選択（旧Granular用）
  ├── _convert_mp3_to_wav()     — MP3→WAV変換 (ffmpeg)
  ├── _acquire_pid_lock()       — 多重起動防止
  └── Global: controller, tidal, sequencer, musical, music_gen, sc_synth_client, sc_ready

three_layer_controller.py (819行) — 3層制御システム（ChaosEngine+MarkovTimescale統合版）
  ├── class ThreeLayerController
  │   ├── __init__(send_osc, broadcast, tidal_controller, interval=60.0)
  │   ├── start() / stop()
  │   ├── start_markov() / stop_markov() / set_markov_interval() / get_markov_state()
  │   ├── set_attractor(layer, param, value, range_val)
  │   ├── set_speed(speed) / set_dejavu_prob(prob)
  │   ├── set_middle_model / set_lower_model / set_middle_chaos / set_lower_chaos
  │   ├── set_scene(scene)      — シーン定義からゾーン中心を設定
  │   ├── get_state()           — 全パラメーター状態（UI用）
  │   ├── _compute_energy()     — 4ソース加重平均
  │   └── _loop() / _tick()     — 0.1秒ごとに全パラメーター更新 + OSC送信
  │
  ├── class UpperLayer          — Markov状態機械（60秒ごと5状態遷移）
  │   ├── force_state(state_name)  — フロントエンドの状態ボタンから強制遷移
  │   ├── get_control(layer, param) → UpperControl(center, width, speed, snap_prob, micro_range, floor, ceiling)
  │   ├── get_state_info()      — フロントエンド用状態（markov_state メッセージ）
  │   ├── set_zone_override / clear_zone_override / set_speed_override / set_snap_override
  │   ├── set_interval(seconds) / start() / stop()
  │   ├── _loop()               — 1秒ごとカウントダウン + broadcast
  │   ├── _next_state()         — Markov 70% + エネルギーフィードバック 30%
  │   └── _apply_tidal(state)   — TIDAL_PRESET_BY_STATE から自動切換え
  │
  ├── _middle_next(current, ctrl) → float  [BoundedWalk]
  └── _lower_next(middle, ctrl, history) → float  [Dejavu]

music_generator.py (1233行) — class MusicGenerator: Multi-timescale Tidalコード生成エンジン
  ├── start(scene_name, sa_record?) / stop()
  ├── set_scene(scene_name, sa_record?)  — SCENE_DNA + SAシードを適用
  ├── _upper_loop()  — ~60-120秒ごとに Markov スケール遷移
  ├── _middle_loop() — ~4-8秒ごとに GravityMatrix コード度数選択
  ├── _lower_tick()  — ~1-2秒ごとに Tidal d1-d6 コード送信
  └── _compute_sa_activity_multiplier(record) → speed抑制倍率 (1.0〜8.0)

scenes.py (198行) — load_scenes / get_scene / SCENE_DNA (5シーン)
sequencer.py (208行) — class TuringSequencer
tidal_controller.py (224行) — class TidalController (GHCi subprocess管理)
tidal_patterns.py (244行) — get_preset(preset_name) → [code_str, ...]
param_mapper.py (129行) — パラメーター正規化・マッピング
sonic_anatomy_bridge.py (397行) — Sonic Anatomy DB → Tidalシード生成
```

## Global State (bridge.py)

```python
connected_clients: set[WebSocket]
sc_client: SimpleUDPClient          # sclang OSC送信 (port 57200)
sc_synth_client: SimpleUDPClient    # scsynth native OSC送信 (port 57110)
controller: ThreeLayerController    # 3層制御システム
music_gen: MusicGenerator           # Multi-timescale Tidalコード生成エンジン
tidal: TidalController
sequencer: TuringSequencer
musical: MusicalControl
sc_ready: bool
_sonic_anatomy_state: dict
```

## 定期ブロードキャスト (_periodic_state_broadcast)

```
2秒周期:
  flow_state  → {"type": "flow_state", "key": ..., "harmony": ..., "rhythm": ...}
  chaos_state → {"type": "chaos_state", "state": controller.get_state()}

6秒周期:
  sc_synth_client.send_message("/g_queryTree", [0, 0])
  → /g_queryTree.reply 受信 → _parse_node_tree() → broadcast("sc_node_tree")
```

## 制御フロー

```
1. Upper._loop() — 60秒ごとに Markov 遷移、STATE_ZONES/STATE_CONTROLS から UpperControl 生成
2. ThreeLayerController._tick() — 0.1秒ごと全パラメーターを更新
   a. ctrl = upper.get_control(layer, param)
   b. new_middle = _middle_next(state.middle, ctrl)  — BoundedWalk
   c. new_current = _lower_next(new_middle, ctrl, history)  — Dejavu
   d. _send_osc(osc_address, [param, new_current])
   e. broadcast({"type": "chaos_state", ...})
```

## 定数定義（three_layer_controller.py）

```
PARAM_SPECS          — {layer: {param: (min, max, init, osc_address)}}
STATE_ZONES          — {state: {layer: {param: {"center": float, "width": float}}}}
STATE_CONTROLS       — {state: {"speed": float, "snap_prob": float, "micro_ratio": float}}
BASE_MATRIX          — {state: [prob_to_void, ..., prob_to_intense]}
TIDAL_PRESET_BY_STATE — void→minimal_klank / sparse→opn_sparse / medium→alva_euclidean
                        dense→alva_phase / intense→chaos_collapse
```
