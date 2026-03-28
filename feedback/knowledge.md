# フィードバック知識ベース

> Claudeが試行ログから蒸留した法則をここに書く。
> 「良くなった」が1回確認されたらすぐ記録する。

---

## 言葉とパラメーターの対応

> SCコードを書く前に必ずここを参照する。
> 日本語フィードバック → 英語SCテクニック → 具体的なUGenの3層構造。

### 明るさ・色

| 日本語 | 英語キーワード | SC実装 | 参照ファイル |
|--------|--------------|--------|------------|
| 明るい・透き通った | bright, open | cutoff ↑ (2000Hz+), RHPF でローカット | synthesis_subtractive_stereo.md |
| 暗い・こもった | dark, muffled | cutoff ↓ (300-600Hz), LPF | synthesis_subtractive_stereo.md |
| 温かい | warm | LFTri or SinOsc, tanh saturation, cutoff 800-1200Hz | synthesis_ambient_drone.md |
| 冷たい・無機質 | cold, metallic | FM変調, WhiteNoise + BPF | synthesis_fm.md |
| ざらざら・ノイズっぽい | gritty, noisy | PinkNoise/BrownNoise mix, noisiness ↑ | synthesis_subtractive_stereo.md |

### 空間感・残響

| 日本語 | 英語キーワード | SC実装 | 参照ファイル |
|--------|--------------|--------|------------|
| 霞む・残響が長い | long reverb, diffuse | **GVerb(revtime: 8-15, roomsize: 80-100)** | synthesis_ambient_drone.md |
| 包まれる・天井が高い | enveloping, tall space | GVerb roomsize ↑, mix: 0.6+ | synthesis_ambient_drone.md |
| 広い | wide, spacious | Splay.ar, stereo detune ±Hz | synthesis_ambient_drone.md |
| ドライ | dry | FreeVerb mix: 0.1以下 | synthesis_subtractive_stereo.md |
| リバーブが短い | short reverb | FreeVerb2(room: 0.4, damp: 0.7) | synthesis_subtractive_stereo.md |

### 質感・動き

| 日本語 | 英語キーワード | SC実装 | 参照ファイル |
|--------|--------------|--------|------------|
| 粒状・グレイン | granular, grainy | GrainSin, TGrains, Dust | synthesis_granular.md |
| 揺れる・脈打つ | pulsing, undulating | LFNoise1.kr + cutoff mod, SinOsc.kr LFO | synthesis_ambient_drone.md |
| 漂う・浮遊感 | floating, drifting | 遅いLFO (0.01-0.05Hz), detuned unison | synthesis_ambient_drone.md |
| 立ち上がりが遅い | slow attack | EnvGen attack: 3.0-8.0 | synthesis_ambient_drone.md |
| グリッチ | glitch, spectral | PV_* UGens, FFT処理 | synthesis_spectral.md |
| シマー | shimmer | PitchShift(shift: 2.0) + reverb mix | synthesis_ambient_drone.md |

### リバーブ選択ガイド（重要）

| 目的 | 使うUGen | 設定例 |
|------|---------|-------|
| 残響 < 2秒、自然な響き | FreeVerb2 | room: 0.6, damp: 0.4 |
| 残響 2-8秒、広いホール | FreeVerb2 | room: 0.92, damp: 0.1 |
| **残響 8秒+、霞む・天井が高い** | **GVerb** | **revtime: 12, roomsize: 100** |
| コンボリューション、超リアル | Convolution2 | IRバッファが必要 |

---

## drone

### 効いた操作

| 反復 | 意図 | SC実装 | 結果 |
|------|------|--------|------|
| 005 | 霞む・残響が長い・天井が高い・漂う | FreeVerb2 → **GVerb(revtime: 12, roomsize: 100)** に切り替え | ✅ better |

### 効かなかった操作

| 反復 | 意図 | 試したこと | 理由 |
|------|------|-----------|------|
| 001 | 明るく・包まれる | cutoff 800→1800Hz, FreeVerb room 0.6→0.8 | パラメーター変更のみで構造変えず |
| 002 | モジュレーション・複雑さ | shimmer/chorus/subパラメータ追加 | 音の出口（リバーブ）が変わっていない |
| 004 | 霞む・残響 | BrownNoise + FreeVerb2(damp高め) | FreeVerb2では残響が短すぎる |

### 警告（悪化パターン）

| 反復 | 試したこと | なぜ悪かったか |
|------|-----------|--------------|
| 003 | FM変調 + ピンポンディレイ | FM変調は「ノイズ・こもった感」と方向が違う（金属的になる） |

### まだ分からないこと

- 「温かみ・心安らかさ」をGVerb上でどう出すか（iteration 5以降の課題）
- ノイズ成分とアンビエントの最適なバランス

---

## 共通パターン

### 効いた操作
_（まだデータなし）_

---

_最終更新: 2026-03-28_
