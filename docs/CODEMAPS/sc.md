<!-- Generated: 2026-04-04 (updated) | Files scanned: sc/*.scd (10ファイル) | Token estimate: ~900 -->
# SuperCollider Architecture

## ファイル構成

```
sc/
├── run_headless.scd  (1459行) — 起動スクリプト・全モジュールロード・OSCdef登録
├── drone.scd          (219行) — ドローン SynthDef v3 (自己組織化フィードバック)
├── granular.scd       (241行) — グラニュラーサンプラー Ndef (バッファベース)
├── gran_synth.scd     (203行) — グラニュラーシンセ SynthDef (バッファ不要・独立型) NEW
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

## Ndef(\granular) (granular.scd / バッファベース)

```
GrainSin / TGrains を使用
Parameters:
  pos     0-1    再生位置
  density 1-50   グレイン/秒
  spread  0-1    ピッチばらつき
  amp     0-1
フィードバック: /matoma/granular/density → Python → ブラウザ表示
```

## SynthDef: matoma_gran_synth (gran_synth.scd / バッファ不要・独立型) NEW

```
設計思想: GrainSin（バッファ不要）を高密度で発火させて
         「途切れない・太い・滑らかな」アンビエントテクスチャ生成

Parameters:
  freq      = 110Hz    基本周波数
  density   = 35       グレイン/秒（同時に ~6粒重なる）
  grainDur  = 0.18s    グレイン長（滑らかさの鍵）
  spread    = 0.2      ピッチ散乱（0=純粋、1=広い）
  panSpread = 0.7      ステレオ広がり
  bright    = 0.4      オクターブ上層の量（0=暗い、1=明るい）
  chaos     = 0.3      有機モジュレーション深さ
  room      = 0.6      リバーブ量
  amp       = 0.4      音量

Signal Chain:
  GrainSin (基音層) + GrainSin (オクターブ上層 × bright)
    ↓
  FreeVerb2 (room パラメーターで空間化)
    ↓
  Env.adsr (attack:2s / release:5s で緩やか立ち上がり・消滅)
    ↓
  Limiter (0.85 で安全制御)
    ↓
  ~effectBus

Layer A: 3階層有機モジュレーション（drone.scd と同設計）
  A1（呼吸, ~0.04 Hz）: density を ±30% chaos で揺らす
  A2（心拍, ~0.15 Hz）: pitch を spread×chaos で揺らす
  A3（神経, ~3 Hz）  : pan をゆっくり動かす
```

## OSCdef: gran_synth (gran_synth.scd) NEW

```
/matoma/gran_synth/start      — SynthDef インスタンス起動 (既起動なら置換)
/matoma/gran_synth/stop       — gate=0 → 5秒フェードアウト
/matoma/gran_synth/param      — [key, val] パラメーター変更
                                 許可リスト: freq, density, grainDur,
                                            spread, panSpread, bright,
                                            chaos, room, amp, gate
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

## rhythmic.scd — リズム系 SynthDef 群（Tidal/Pythonからトリガー）

```
SynthDef:
  \matoma_rhythmic_grain  — グレイン風パーカッシブサウンド
  \matoma_rhythmic_klank  — 金属的共鳴音（Klank）
  \matoma_rhythmic_fm     — FM変調パーカッション
  \matoma_rhythmic_spring — バネ・メタルサウンド（DFM1）
  \matoma_rhythmic_chaos  — カオス風ノイズパーカッション

OSCdef:
  \matoma_rhythmic_trigger  /matoma/rhythmic/trigger [def_num, amp]
                            — SynthDef番号(0-4)とampでトリガー
  \matoma_rhythmic_load     /matoma/rhythmic/load    [sample_path]
                            — サンプルバッファロード（将来拡張用）

注: 旧Turingマシン制御（~turingRegister, ~turingProb等）は削除。
    rhythmicレイヤーはTidalプリセットとChaosEngineに統合済み。
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
\matoma_param            /matoma/param                [key, val] → currentSynth.set(key, val)
\matoma_drone            /matoma/drone/param          [key, val] → SynthDef(\matoma_drone).set()
\matoma_granular         /matoma/granular/param       [key, val] → Ndef(\granular).set(key, val)
\matoma_gran_load        /matoma/granular/load        [path]     → Buffer.read(path)
\matoma_gran_synth_start /matoma/gran_synth/start     —          → SynthDef インスタンス起動 NEW
\matoma_gran_synth_stop  /matoma/gran_synth/stop      —          → gate=0 フェードアウト NEW
\matoma_gran_synth_param /matoma/gran_synth/param     [key, val] → パラメーター変更 NEW
\matoma_spectral         /matoma/spectral/param       [key, val] → Ndef(\spectral).set(key, val)
\matoma_scene            /matoma/scene                [name]     → シーン別パラメーター一括設定
(+ percussion.scd 内 22個のOSCdef)
```
