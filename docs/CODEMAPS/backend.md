<!-- Generated: 2026-04-05 (updated) | 3層制御システム移行完了 | ThreeLayerController 採用 -->
# Backend Architecture

## Entry Point

`backend/bridge.py` (1110行) — asyncio メインプロセス。OSCサーバー(9000) + WebSocketサーバー(8765) を同時起動。

## OSC Routes (SC → Python, port 9000)

```
/matoma/ready            → SC起動完了通知 → broadcast("sc_ready") + controller.start()
/matoma/seq/tick         → シーケンサーステップ → broadcast("seq_tick")
/matoma/granular/density → グレイン密度 → broadcast("granular_density")
/matoma/rhythmic/trigger → rhythmic シンセトリガー → broadcast("rhythmic_trigger")
/matoma/rhythmic/load    → rhythmic サンプルロード → broadcast("rhythmic_loaded")
```

## WebSocket Routes (Browser → Python, port 8765)

```
# シーン・基本制御
/matoma/scene                  → scenes.py.get_scene() → controller.set_scene()
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
  ├── on_osc_message()          — SC→Python OSC受信（/matoma/ready で controller自動起動）
  ├── broadcast()               — 全クライアントWS送信
  ├── _send_osc()               — SC へ OSC 送信（Studio Mode 用ブロードキャスト付き）
  ├── _handle_tidal()           — Tidal Cyclesコマンド処理
  ├── _handle_granular_browse() — macOSファイル選択
  ├── _convert_mp3_to_wav()     — MP3→WAV変換 (ffmpeg)
  ├── _acquire_pid_lock()       — 多重起動防止
  └── Global: controller, autonomous, tidal, sequencer, musical

three_layer_controller.py (720行) — 3層制御システム（ChaosEngine+MarkovTimescale統合版）
  ├── class ThreeLayerController
  │   ├── __init__(send_osc, broadcast, tidal_controller, interval=60.0)
  │   ├── start() / stop()
  │   ├── start_markov() / stop_markov() / set_markov_interval() / get_markov_state()
  │   ├── set_attractor(layer, param, value, range_val)
  │   ├── set_speed(speed)      — 全パラメーターのドリフト速度
  │   ├── set_dejavu_prob(prob) — 全パラメーターのDejavu確率
  │   ├── set_middle_model / set_lower_model — モデル切り替え（現バージョン固定）
  │   ├── set_middle_chaos / set_lower_chaos — カオス比率（speed/dejavu_prob変換）
  │   ├── set_scene(scene)      — シーン定義からゾーン中心を設定
  │   ├── get_state()           — 全パラメーター状態（UI用）
  │   ├── _compute_energy()     — 4ソース加重平均（gran×0.30, synth×0.25, sampler×0.25, drone×0.20）
  │   ├── _loop() / _tick()     — 0.1秒ごとに全パラメーター更新 + OSC送信
  │   └── _params: {layer: {param: _ParamState(current, middle, osc_address)}}
  │
  ├── class UpperLayer          — Markov状態機械（60秒ごと5状態遷移）
  │   ├── get_control(layer, param) → UpperControl(center, width, speed, snap_prob, micro_range, floor, ceiling)
  │   ├── get_state_info()      — フロントエンド用状態（markov_state メッセージ）
  │   ├── set_zone_override(layer, param, center, width) — 手動引力点調整
  │   ├── clear_zone_override / set_speed_override / set_snap_override
  │   ├── set_interval(seconds) / start() / stop()
  │   ├── _loop()               — 1秒ごとカウントダウン + broadcast
  │   ├── _next_state()         — Markov 70% + エネルギーフィードバック 30%
  │   └── _apply_tidal(state)   — TIDAL_PRESET_BY_STATE から自動切換え
  │
  ├── _middle_next(current, ctrl) → float
  │   └── BoundedWalk: Upper ゾーンの center に引き寄せられながらドリフト
  │
  └── _lower_next(middle, ctrl, history) → float
      └── Dejavu: middle 周辺で微変動 + snap_prob で過去値へスナップバック

  定数:
    PARAM_SPECS         — {layer: {param: (min, max, init, osc_address)}}
    STATE_ZONES         — {state: {layer: {param: {"center": float, "width": float}}}}
    STATE_CONTROLS      — {state: {"speed": float, "snap_prob": float, "micro_ratio": float}}
    BASE_MATRIX         — {state: [prob_to_void, prob_to_sparse, ...]}
    TIDAL_PRESET_BY_STATE — {state: preset_name}

autonomous.py (716行)
  └── class AutonomousMode      — 旧自律モード（非推奨。ThreeLayerControllerに移行）

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
  └── get_preset(preset_name) → [code_str, ...]

claude_tidal.py (250行) — Claude API統合
  ├── retrieve_rag_context(prompt) — ChromaDB検索
  └── translate_with_claude(prompt, state) — 日本語→Tidalコード変換

param_mapper.py (129行) — パラメーター正規化・マッピング

sonic_anatomy_bridge.py (397行) — Sonic Anatomy DB → Tidalシード生成
  ├── load_record(track_id?) → Optional[SonicAnatomyRecord]
  │   SQLiteDB (/Sonic Anatomy/projects/sonic_anatomy_catalog.db) から解析データ読み込み
  ├── generate_tidal_seed(record) → TidalSeed
  │   BPM/スケール/リズム/コード進行 → Tidalパターンコード（d1〜d6）
  └── seed_to_dict(seed) → dict (WebSocket送信用JSON)

  ⚠️ 注意: フロントエンドUIが未実装（load/applyボタン・WS受信ハンドラーなし）
  ⚠️ 注意: randomize_models.py（BoundedWalk/DejavuModel）は未使用・dead code

musical_control.py — MusicalControl（Tidalとの統合制御）
```

## 3層タイムスケールアーキテクチャ

```
UpperLayer（上位, 60秒 Markov）
  状態: void / sparse / medium / dense / intense（5状態）
  制御: Markov 70% + エネルギーフィードバック 30%
        ↓ center/width/speed/snap_prob/micro_range を Middle/Lower へ渡す
        ↓ Tidalプリセット自動切換え（TIDAL_PRESET_BY_STATE）
─────────────────────────────────────────────
_middle_next（中位, 0.1秒更新）
  アルゴリズム: BoundedWalk（固定実装）
  動作: Upper の center に引き寄せられながら width 内をドリフト
  入力: current, UpperControl(center, width, speed, floor, ceiling)
  出力: 新しい middle 値（Lower の参照点）
─────────────────────────────────────────────
_lower_next（下位, 0.1秒更新）
  アルゴリズム: Dejavu（固定実装）
  動作: middle ± micro_range で微変動、snap_prob で過去値へスナップバック
  入力: middle, UpperControl(snap_prob, micro_range, floor, ceiling), history
  出力: 新しい current 値 → OSC 送信
```

## 制御フロー

```
1. Upper._loop() — 60秒ごとに Markov 遷移、STATE_ZONES/STATE_CONTROLS から UpperControl 生成
2. ThreeLayerController._tick() — 0.1秒ごと全パラメーターを更新
   a. ctrl = upper.get_control(layer, param)  — center/width/speed/snap_prob/micro_range取得
   b. new_middle = _middle_next(state.middle, ctrl)  — Middle: center へドリフト
   c. new_current = _lower_next(new_middle, ctrl, history)  — Lower: middle 周辺で微変動
   d. _send_osc(osc_address, [param, new_current])  — SC へ送信
   e. broadcast({"type": "chaos_state", "state": get_state()})  — UI更新
```

## Global State (bridge.py)

```python
connected_clients: set[WebSocket]
sc_client: SimpleUDPClient          # SC送信 (OSC/UDP, port 57120)
controller: ThreeLayerController    # 3層制御システム（upper+middle+lower統合）
                                    # 初期化: ThreeLayerController(_send_osc, broadcast, tidal_controller=tidal)
                                    # 起動: SC起動完了時 (/matoma/ready 受信) に controller.start() 自動実行
autonomous: AutonomousMode          # 旧自律モード（非推奨）
tidal: TidalController
sequencer: TuringSequencer
musical: MusicalControl(tidal, broadcast, lambda: controller._upper._state)
sc_ready: bool
```

## bridge.py と ThreeLayerController の連携

```python
# 初期化（bridge.py 内、main() 関数）
controller = ThreeLayerController(
    send_osc=_send_osc,              # _send_osc(address, args) → sc_client.send_message() + broadcast(studio_mode用)
    broadcast=broadcast,              # WebSocketクライアント全体へブロードキャスト
    tidal_controller=tidal,           # UpperLayer が状態遷移時に Tidal プリセット自動切換え
    interval=60.0                     # Markov 状態遷移間隔（デフォルト60秒）
)

# SC起動完了時の自動起動（on_osc_message 内）
@dispatcher.map("/matoma/ready")
def ready_handler(address, *args):
    global sc_ready
    sc_ready = True
    if controller is not None:
        controller.start()  # → 0.1秒ごとのパラメーター更新ループ開始 + Markov開始
        log.info("ThreeLayerController 自動スタート")

# WebSocket経由の手動制御（ws_handler 内）
/matoma/chaos/start      → controller.start()
/matoma/chaos/stop       → controller.stop()
/matoma/chaos/attractor  → controller.set_attractor(layer, param, value, range_val)
/matoma/markov/start     → controller.start_markov()
/matoma/markov/stop      → controller.stop_markov()
/matoma/scene            → controller.set_scene(scene_dict)

# _send_osc の役割
# 1. SC へ OSC 送信（sc_client.send_message）
# 2. Studio Mode 用に WebSocket ブロードキャスト（{"type": "studio_osc", "address": ..., "args": ...}）
```

## 定数定義（three_layer_controller.py）

### PARAM_SPECS
```python
{layer: {param: (min_val, max_val, init_val, osc_address)}}

例:
  "drone": {
    "feedback_amt": (0.0, 1.0, 0.25, "/matoma/drone/param"),
    "shimmer":      (0.0, 1.0, 0.40, "/matoma/drone/param"),
  },
  "granular": {
    "density": (1.0, 60.0, 15.0, "/matoma/granular/param"),
  }
```

### STATE_ZONES
```python
{state: {layer: {param: {"center": float, "width": float}}}}

void 状態の例:
  "drone": {
    "feedback_amt": {"center": 0.10, "width": 0.06},  # 0.04〜0.16の範囲でドリフト
    "amp":          {"center": 0.15, "width": 0.04},
  }

intense 状態の例:
  "drone": {
    "feedback_amt": {"center": 0.45, "width": 0.15},  # 0.30〜0.60の範囲でドリフト
    "amp":          {"center": 0.65, "width": 0.06},
  }
```

### STATE_CONTROLS
```python
{state: {"speed": float, "snap_prob": float, "micro_ratio": float}}

void:    speed=0.3,  snap_prob=0.50, micro_ratio=0.15  # ゆっくり、安定的
sparse:  speed=0.5,  snap_prob=0.40, micro_ratio=0.20
medium:  speed=0.8,  snap_prob=0.30, micro_ratio=0.25
dense:   speed=1.2,  snap_prob=0.15, micro_ratio=0.35
intense: speed=1.8,  snap_prob=0.05, micro_ratio=0.50  # 速く、激しく変動

speed:       Middle のドリフト速度（大きいほど center へ速く引き寄せられる）
snap_prob:   Lower の Dejavu 確率（過去値へスナップバックする頻度）
micro_ratio: Lower の微変動幅 = width × micro_ratio
```

### BASE_MATRIX
```python
{state: [prob_to_void, prob_to_sparse, prob_to_medium, prob_to_dense, prob_to_intense]}

void:    [0.40, 0.40, 0.15, 0.04, 0.01]  # void に留まる or sparse へ移行しやすい
medium:  [0.05, 0.20, 0.40, 0.25, 0.10]  # medium に留まりつつ、dense/sparse へ分散
intense: [0.05, 0.10, 0.25, 0.40, 0.20]  # intense/dense を維持しやすい
```

### TIDAL_PRESET_BY_STATE
```python
{state: preset_name}

void:    "minimal_klank"   # 最小限の音響
sparse:  "opn_sparse"      # OPN 風スパース
medium:  "alva_euclidean"  # Alva Noto 風ユークリッド
dense:   "alva_phase"      # 密度の高い位相変調
intense: "chaos_collapse"  # カオス的崩壊
```

## データフロー図

```
ユーザー操作（UI）
    ↓
WebSocket → bridge.py → controller.set_attractor(layer, param, value, range_val)
                                 ↓
                         upper.set_zone_override(layer, param, center, width)
                                 ↓
─── 60秒ごと ───────────────────────────────────────────────
upper._loop()
  _next_state() — Markov 70% + エネルギーフィードバック 30%
  _apply_tidal(state) — Tidal プリセット自動切換え
  broadcast({"type": "markov_state", "state": get_state_info()})
─────────────────────────────────────────────────────────
─── 0.1秒ごと ──────────────────────────────────────────
controller._tick()
  for each param:
    ctrl = upper.get_control(layer, param)  # center/width/speed/snap_prob/micro_range
    new_middle = _middle_next(state.middle, ctrl)  # BoundedWalk
    new_current = _lower_next(new_middle, ctrl, history)  # Dejavu
    _send_osc(osc_address, [param, new_current])
  broadcast({"type": "chaos_state", "state": get_state()})
─────────────────────────────────────────────────────────
    ↓
SuperCollider (受信側)
  SynthDef.drone.set(param, new_current)
  SynthDef.granular.set(param, new_current)
  ...
```
