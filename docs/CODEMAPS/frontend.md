<!-- Generated: 2026-04-04 (updated) | Files scanned: frontend/index.html | Token estimate: ~650 -->
# Frontend Architecture

## Stack

- HTML5 + 純JavaScript（フレームワーク不使用）
- WebSocket: `ws://localhost:8765`
- 1ファイル構成: `frontend/index.html` (1850行)

## UI モジュール一覧

| モジュール | 色 | 役割 | 主要送信アドレス |
|-----------|---|------|----------------|
| SCENE | #4ade80 緑 | 4プリセット切替 | `/matoma/scene` |
| DRONE | #60a5fa 青 | ドローン・アンビエント | `/matoma/drone/param` |
| SYNTH | #fbbf24 オレンジ | FM合成シンセ | `/matoma/param` |
| GRANULAR | #fb923c 薄橙 | グラニュラーサンプラー（バッファベース） | `/matoma/granular/*` |
| GRAN SYNTH | #8b7355 (tan) | グラニュラーシンセ（バッファ不要・独立型） | `/matoma/gran_synth/*` |
| SPECTRAL | #e879f9 マゼンタ | スペクトル処理 | `/matoma/spectral/param` |
| SEQ | #d4f74c ライム | Turingシーケンサー | `/matoma/seq/*` |
| CHAOS ENGINE | #a78bfa 紫 | ChaosEngine + MarkovTimescale制御 | `/matoma/chaos/*` `/matoma/markov/*` `/matoma/layer/*` |
| TIDAL | #22d3ee シアン | Tidal Cycles | `/matoma/tidal/*` |
| DRUMS | #f43f5e ピンク | ドラムマシン | `/matoma/tidal/drums` |

## CHAOS ENGINE モジュール 詳細

```
START / STOP ボタン
読み取り専用モニター:
  SPEED   — ChaosEngine._speed (進行速度)
  PROB    — trig_prob (パラメーター変化確率)
  REPEAT  — dejavu_prob (履歴スナップバック確率)

DRIFT MODEL（モデル選択ラジオボタン）:
  MIDDLE: BoundedWalk* / Fractal / L-System / Blend
  LOWER:  Dejavu* / BoundedWalk / L-System / Blend
  (* = デフォルト)

REPEAT↔CHAOS スライダー:
  MIDDLE (0=L-System, 1=BoundedWalk)  → /matoma/layer/middle/chaos
  LOWER  (0=Dejavu,   1=BoundedWalk)  → /matoma/layer/lower/chaos

MARKOV セクション:
  ▶/■ MARKOV ボタン  → /matoma/markov/start|stop
  INTERVAL スライダー (10-300s)  → /matoma/markov/interval
  状態表示: void/sparse/medium/dense/intense + 次まで残り秒数

状態モニター（read-only バー）:
  DRONE: freq, shimmer, feedback_amt, room, amp
  GRANULAR: density, spray, pos, room, amp
  GRAN SYNTH: density, bright, chaos, room, amp
  GRAN SAMPLER: density, spray, pos, room, amp
```

## DRONE モジュール 詳細

```
XY Pad: X軸=freq (40-220Hz), Y軸=detune (0-1)
Sliders:
  cutoff   (80-3000 Hz)
  drift    (0-1)     ← LFO速度
  room     (0-1)     ← リバーブ量
  revtime  (1-30s)   ← リバーブ残響時間
  amp      (0-1)
  breathe  (0-1)     ← 振幅変調の深さ
```

## GRANULAR モジュール 詳細

```
Parameters (バッファベース):
  pos     (0-1)      再生位置
  density (1-50)     グレイン/秒
  spread  (0-1)      ピッチばらつき
  amp     (0-1)      音量
Buffer Load ボタン
```

## GRAN SYNTH モジュール 詳細

```
Start / Stop ボタン
Parameters (バッファ不要・GrainSin):
  freq      (40-220 Hz)   基本周波数（Hz）
  density   (5-60)        グレイン/秒
  grainDur  (0.05-0.5s)   グレイン長
  spread    (0-1.0)       ピッチ散乱
  panSpread (0-1.0)       ステレオ広がり
  bright    (0-1.0)       オクターブ上層量
  chaos     (0-1.0)       有機モジュレーション深さ
  room      (0-1.0)       リバーブ量
  amp       (0-1.0)       音量
```

## SEQ モジュール 詳細

```
16ステップグリッド (ON/OFF 視覚フィードバック付き)
BPM: 20-300
Step Div: 1/4 / 1/8 / 1/16 / 1/32
TRIG Prob: 0-1
Mutation Prob: 0-1
Active Params: drone_cutoff / drone_drift / spectral_smear / spectral_chaos
```

## TIDAL モジュール 詳細

```
Start / Stop / Hush
Tempo (BPM)
Root: C / C# / D / ... / B
Scale: major / minor / dorian / phrygian / lydian / ...
Chord: major7 / minor7 / sus4 / ...
Synth: 各種SuperCollider SynthDef
Octave: 1-6
Pattern Buttons: Chord / Scale / Arp / Drums
```

## JavaScript 主要関数

```
connect()                  — WebSocket接続・再接続
send(msg)                  — OSCメッセージ送信 ({address, args})
onMessage(event)           — WS受信ディスパッチ
selectScene(name)          — シーン切替 + UI更新
onSeqTick(msg)             — シーケンサーステップ表示更新
updateDensityDots(n)       — グレイン密度表示
chaosToggle()              — ChaosEngine ON/OFF
markovToggle()             — MarkovTimescale ON/OFF
setMarkovRunning(bool)     — Markovボタン表示更新
updateMarkovState(state)   — Markovステータス表示更新 (state/remaining/interval)
updateChaosState(state)    — ChaosEngineバー更新
```

## WebSocket メッセージ受信タイプ

```
sc_ready          → SC起動完了通知
seq_tick          → シーケンサーステップ更新
granular_density  → グレイン密度表示更新
chaos_state       → CHAOS ENGINEバー一括更新
markov_state      → Markov状態・残り時間更新
```

## State Flow

```
ユーザー操作 (スライダー/ボタン)
  → send({address, args})
  → ws.send(JSON)
  → [bridge.py]
  → SC or TidalController or ChaosEngine or MarkovTimescale

SC/Python フィードバック
  → bridge.py: broadcast()
  → ws.onmessage → onMessage()
  → 各 updateXxx() → UI更新
```

## キーボードショートカット

```
1-4  → シーン選択 (暗い/標準/明るい/高音・静か)
```
