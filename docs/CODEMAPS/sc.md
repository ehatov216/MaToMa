<!-- Generated: 2026-03-29 | Files scanned: sc/*.scd | Token estimate: ~450 -->
# SuperCollider Architecture

## ファイル構成

```
sc/
├── run_headless.scd   — 起動スクリプト・全モジュールロード
├── drone.scd          — ドローン定義 (Ndef)
├── granular.scd       — グラニュラーサンプラー
├── synth.scd          — FMシンセ SynthDef
├── ambient.scd        — アンビエントパッド
└── test_sender.scd    — OSCテスト送信ユーティリティ
```

## 起動シーケンス (run_headless.scd)

```
1. UDPポート 57200 を開く (MaToMa専用)
2. メモリ拡張: s.options.memSize = 131072 (128MB)
3. SynthDef/Ndef の定義 (各 .scd ファイルをロード)
4. OSCdef の登録 (Python からのコマンド受信)
5. 起動確認音: 880Hz ビープ音
6. /matoma/ready を Python へ送信
```

## SynthDef: matoma_basic (FM合成)

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

## Ndef(\drone) (ドローン・アンビエント)

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
  LFSaw × 5本 (各周波数=freq × [1,1+detune, 0.5, 2, 1+detune/2])
    ↓ Mix
  LFO (drift Hz, SinOsc) → RLPF cutoff変調
  LFO (1/12Hz, SinOsc)   → Breathe (振幅変調)
    ↓
  GVerb (room, revtime)
    ↓
  Out
```

## OSCdef 一覧 (Python → SC)

```
\matoma_param       /matoma/param       [key, val] → ~currentSynth.set(key, val)
\matoma_drone       /matoma/drone/param [key, val] → Ndef(\drone).set(key, val)
\matoma_granular    /matoma/granular/param [key, val] → Ndef(\granular).set(key, val)
\matoma_gran_load   /matoma/granular/load  [path]    → Buffer.read(path)
\matoma_spectral    /matoma/spectral/param [key, val] → Ndef(\spectral).set(key, val)
```

## グラニュラー (granular.scd)

```
Ndef(\granular):
  GrainSin / TGrains を使用
  Parameters:
    pos     0-1    再生位置
    density 1-50   グレイン/秒
    spread  0-1    ピッチばらつき
    amp     0-1
  フィードバック: /matoma/granular/density → Python → ブラウザ表示
```

## スペクトル (spectral.scd or run_headless.scd)

```
Ndef(\spectral):
  PV_MagSmear (smear)  — 周波数成分をぼかす
  PV_Diffuser (chaos)  — 位相をランダム化
  Parameters:
    smear  0.1-0.9
    chaos  0.1-0.8
```
