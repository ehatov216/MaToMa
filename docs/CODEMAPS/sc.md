<!-- Generated: 2026-03-30 | Files scanned: sc/*.scd (9ファイル) | Token estimate: ~800 -->
# SuperCollider Architecture

## ファイル構成

```
sc/
├── run_headless.scd  (1121行) — 起動スクリプト・全モジュールロード・OSCdef登録
├── drone.scd          (219行) — ドローン SynthDef v3 (自己組織化フィードバック)
├── granular.scd       (241行) — グラニュラーサンプラー Ndef
├── synth.scd           (97行) — FMシンセ SynthDef
├── ambient.scd        (135行) — アンビエントパッド Ndef
├── effects.scd        (366行) — スペクトル処理 + グローバルエフェクトチェーン
├── rhythmic.scd       (438行) — Turing Machineシーケンサー
├── percussion.scd     (764行) — ドラム SynthDef 群 + 22個の OSCdef
└── test_sender.scd     (50行) — OSCテスト送信ユーティリティ
```

## 起動シーケンス (run_headless.scd)

```
1. UDPポート 57200 を開く (MaToMa専用)
2. メモリ拡張: s.options.memSize = 131072 (128MB)
3. 出力デバイス設定を audio_device.txt から読み込み
4. SynthDef/Ndef の定義 (各 .scd ファイルをロード)
5. OSCdef の登録 (Python からのコマンド受信)
6. 起動確認音: 880Hz ビープ音
7. /matoma/ready を Python (port 9000) へ送信
```

## 共有バス一覧

```
~droneBus    Bus.audio(s,2)   — Drone → Granular の素材ルート
~effectBus   Bus.audio(s,2)   — 全音源 → グローバルエフェクト層ルート
~centroidBus Bus.control(s,1) — [Organic Coupling] ドローン明るさ（0=暗〜1=明）
~couplingBus Bus.control(s,1) — [Organic Coupling] 連動強度（0=独立〜1=完全連動）
```

## Organic Coupling アーキテクチャ (2026-03-30追加)

```
\matoma_analyser (SynthDef)
  ← In.ar(~droneBus)
  → 低域/高域エネルギー比 → Lag(2秒平滑化)
  → Out.kr(~centroidBus)

\matoma_granular (SynthDef)
  ← In.kr(~centroidBus)  brightness
  ← In.kr(~couplingBus)  coupling
  → actual_density = density*(1-coupling) + organic_density*coupling
  → Impulse.kr(actual_density) / Dust.kr(actual_density)
```

シーン別 coupling 値:
- 深淵: 0.0（完全独立）
- 浮遊: 0.35（軽い連動）
- 緊張: 0.7（強い連動）
- 崩壊: 0.9（ほぼオーガニック）

OSC: `/matoma/coupling [0.0〜1.0]` → ~couplingBus 直接書き込み

## SynthDef: matoma_basic (synth.scd / FM合成)

```
Parameters:
  freq    = 220Hz       基本周波数
  cutoff  = 1200Hz      フィルターカットオフ
  amp     = 0.6
  chaos   = 0.4         FM変調指数

Signal Chain:
  SinOsc (mod1, ratio=整数) ─┐
  SinOsc (mod2, ratio=非整数) ─┤→ FM加算 → SinOscFB (自己FB)
  WhiteNoise → BPF ──────────┘         ↓
                                      RLPF (cutoff)
                                        ↓
                                    FreeVerb2 (mix=0.45)
                                        ↓
                                     Out
```

## SynthDef: matoma_drone v3 (drone.scd / 自己組織化フィードバック)

```
Parameters:
  freq     = 60Hz     基本周波数
  detune   = 0.25     デチューン幅
  cutoff   = 1800Hz
  drift    = 0.1      LFO速度 (フィルター変調)
  room     = 0.85     GVerb room size
  revtime  = 12.0s    GVerb 残響時間
  amp      = 0.8
  breathe  = 0.55     振幅変調深さ

Signal Chain:
  FreqShift + DelayC + AllpassC (フィードバックネットワーク)
    ↓
  Klank (6倍音) + Resonz (温かみ)
    ↓
  LFO (drift Hz) → RLPF cutoff変調
  LFO (1/12Hz)   → Breathe (振幅変調)
    ↓
  PitchShift Shimmer
    ↓
  FreeVerb2 + GVerb (room, revtime)
    ↓
  Out
```

## Ndef(\granular) (granular.scd)

```
GrainSin / TGrains を使用
Parameters:
  pos     0-1    再生位置
  density 1-50   グレイン/秒
  spread  0-1    ピッチばらつき
  amp     0-1
フィードバック: /matoma/granular/density → Python → ブラウザ表示
```

## Ndef(\ambient) (ambient.scd)

```
Signal Chain:
  Saw × 5本 (detuned unison)
    ↓ LFO変調
  RLPF → GVerb
```

## Ndef(\spectral) (effects.scd)

```
PV_MagSmear (smear 0.1-0.9) — 周波数成分をぼかす
PV_Diffuser (chaos 0.1-0.8) — 位相をランダム化
グローバルエフェクトチェーンも含む
```

## rhythmic.scd — Turing Machineシーケンサー

```
16ステップ固定
mutation_prob — ステップ値の変異確率
trig_prob     — トリガー発火確率
OSCdef でBPM・div・各ステップON/OFF・パラメーター制御
```

## percussion.scd — ドラムシンセ群

```
SynthDef:
  \matoma_perc_kick   — キックドラム
  \matoma_perc_snare  — スネア
  \matoma_perc_hihat  — ハイハット
  \matoma_perc_clap   — クラップ
  (その他パーカッション要素)
22個のOSCdefで各素子を個別制御
```

## OSCdef 一覧 (Python → SC)

```
\matoma_param       /matoma/param            [key, val] → currentSynth.set(key, val)
\matoma_drone       /matoma/drone/param      [key, val] → SynthDef(\matoma_drone).set()
\matoma_granular    /matoma/granular/param   [key, val] → Ndef(\granular).set(key, val)
\matoma_gran_load   /matoma/granular/load    [path]     → Buffer.read(path)
\matoma_spectral    /matoma/spectral/param   [key, val] → Ndef(\spectral).set(key, val)
\matoma_scene       /matoma/scene            [name]     → シーン別パラメーター一括設定
(+ percussion.scd 内 22個のOSCdef)
```
