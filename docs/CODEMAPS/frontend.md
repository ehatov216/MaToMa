<!-- Generated: 2026-03-31 | Files scanned: frontend/index.html | Token estimate: ~580 -->
# Frontend Architecture

## Stack

- HTML5 + 純JavaScript（フレームワーク不使用）
- WebSocket: `ws://localhost:8765`
- 1ファイル構成: `frontend/index.html` (1551行 + GRAN SYNTH パネル)

## UI モジュール一覧

| モジュール | 色 | 役割 | 主要送信アドレス |
|-----------|---|------|----------------|
| SCENE | #4ade80 緑 | 4プリセット切替 | `/matoma/scene` |
| DRONE | #60a5fa 青 | ドローン・アンビエント | `/matoma/drone/param` |
| SYNTH | #fbbf24 オレンジ | FM合成シンセ | `/matoma/param` |
| GRANULAR | #fb923c 薄橙 | グラニュラーサンプラー（バッファベース） | `/matoma/granular/*` |
| GRAN SYNTH | #8b7355 (tan) | グラニュラーシンセ（バッファ不要・独立型） | `/matoma/gran_synth/*` NEW |
| SPECTRAL | #e879f9 マゼンタ | スペクトル処理 | `/matoma/spectral/param` |
| SEQ | #d4f74c ライム | Turingシーケンサー | `/matoma/seq/*` |
| AUTONOMOUS | #a78bfa 紫 | 自律モード | `/matoma/auto/*` |
| TIDAL | #22d3ee シアン | Tidal Cycles | `/matoma/tidal/*` |
| DRUMS | #f43f5e ピンク | ドラムマシン | `/matoma/tidal/drums` |

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

## GRAN SYNTH モジュール 詳細 NEW

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

特徴:
  - Droneに依存しない独立型
  - バッファロード不要
  - Layer A 3階層有機モジュレーション（drone.scdと同設計）
  - attack 2s / release 5s でゆっくり立ち上がり・消滅
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

## AUTONOMOUS モジュール 詳細

```
ON/OFF
Mode: random / directed
Speed: 0.0-1.0
TRIG Prob: 0-1      ← パラメーター変化確率
Dejavu Prob: 0-1    ← 履歴再生確率
Dejavu Len: 1-32    ← 履歴深さ
Tidal Auto: ON/OFF  ← 自動コード進行
Progression: ambient_minor / dark_drone / minimal_shift / alva_noto / bright_drift
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
connect()                — WebSocket接続・再接続
sendOsc(address, args)   — OSCメッセージ送信
onOscMessage(addr, args) — OSC受信ディスパッチ
selectScene(name)        — シーン切替 + UI更新
onSeqTick(msg)           — シーケンサーステップ表示更新
updateDensityDots(n)     — グレイン密度表示
```

## State Flow

```
ユーザー操作 (スライダー/ボタン)
  → sendOsc(address, value)
  → ws.send(JSON)
  → [bridge.py]
  → SC or Tidal

SC フィードバック
  → bridge.py: broadcast()
  → ws.onmessage
  → onOscMessage() → UI更新
```

## キーボードショートカット

```
1-4  → シーン選択 (暗い/標準/明るい/高音・静か)
```
