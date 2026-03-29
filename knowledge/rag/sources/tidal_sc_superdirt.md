---
title: TidalCycles × SuperCollider — SuperDirt連携・カスタムSynthDef・エフェクト
category: tidal
tags: [tidal, superdirt, SynthDef, effects, MIDI, OSC, custom-synth, audio-effects]
---

## TidalCycles × SuperCollider 連携

TidalCycles は SuperDirt（SuperCollider上で動くQuark）を通じて音を出す。
カスタム SynthDef を SuperDirt に登録することで、独自の音源を Tidal から呼べる。

---

### 1. カスタム SynthDef の SuperDirt への登録

```supercollider
// 基本構造：必須引数は out, bufnum, sustain, pan, freq, amp
SynthDef(\mysynth, { |out, freq = 440, amp = 0.3, pan = 0, sustain = 1, gate = 1,
                      cutoff = 2000, res = 0.3, atk = 0.01, rel = 0.5|
    var sig, env, filt;

    env  = EnvGen.ar(Env.adsr(atk, 0.1, 0.8, rel), gate, doneAction: 2);
    sig  = Saw.ar([freq, freq * 1.008], amp); // デチューン2声でステレオ感
    filt = RLPF.ar(sig, cutoff.lag(0.1), res);

    Out.ar(out, Pan2.ar(filt * env, pan));
}).add;

// SuperDirt に登録（SuperDirt 起動後に実行）
~dirt.soundLibrary.addSynth(\mysynth);
```

Tidal から使う：
```haskell
d1 $ n "0 3 5 7" # s "mysynth"
   # cutoff "1000 2000 4000 800"
   # res 0.5
   # sustain 0.3
```

---

### 2. SuperDirt 標準シンセ一覧と主要パラメーター

#### サブトラクティブ系

| シンセ名 | 特徴 | 主なパラメーター |
|---------|------|----------------|
| `supersaw` | デチューンsaw、フィルターLFO | `voice`(デチューン), `semitone`(2nd osc), `resonance`, `lfo`, `rate` |
| `supersquare` | Moogライクなスクエア波 | `voice`(パルス幅), `resonance`, `lfo`, `rate` |
| `superpwm` | PWM（位相変調パルス） | `voice`(位相シフト速度), `resonance`, `lfo` |
| `superreese` | Reeseベース風 | `accelerate`, `voice`, `detune` |
| `supertron` | フィードバックPWM | `voice`(声数), `detune`, `accelerate` |
| `superzow` | フェーズドソー | `detune`, `slide`, `decay` |
| `superhoover` | Hooverリード | `slide`(ピッチグライド), `decay` |

#### 加算・その他

| シンセ名 | 特徴 | 主なパラメーター |
|---------|------|----------------|
| `supergong` | 倍音の足し算でゴング | `voice`(トーン), `decay` |
| `superchip` | Atari STチップエミュ | `slide`, `pitch2`, `pitch3`, `voice` |
| `superfm` | 6オペレーターFM | `voice`, `detune` |

#### アンビエント系

| シンセ名 | 特徴 |
|---------|------|
| `supercomparator` | 比較回路風グリッチ |
| `superkick` | キックドラム |
| `supersnare` | スネア |
| `superhhat` | ハイハット |

---

### 3. SuperDirt エフェクト一覧

#### 空間系

```haskell
-- リバーブ
d1 $ s "arpy*4" # room 0.5 # size 0.8   -- room(0-1), size(深さ)

-- ディレイ
d1 $ s "arpy*4" # delay 0.5 # delaytime 0.25 # delayfeedback 0.4
-- lock 1 で delaytime をBPM同期
d1 $ s "arpy*4" # delay 0.6 # delaytime (1/8) # lock 1

-- レスリー（回転スピーカー）
d1 $ s "arpy*4" # leslie 0.7 # lrate 6.7 # lsize 0.5
-- lrate: 6.7=fast, 0.7=slow

-- フェイザー
d1 $ s "arpy*4" # phaserrate 2 # phaserdepth 0.8
```

#### フィルター系

```haskell
-- ローパスフィルター
d1 $ s "saw*4" # cutoff 800 # resonance 0.4

-- ハイパスフィルター
d1 $ s "saw*4" # hcutoff 400 # hresonance 0.3

-- バンドパスフィルター
d1 $ s "saw*4" # bandf 1000 # bandq 0.5

-- DJフィルター（0〜0.5=LPF, 0.5〜1=HPF）
d1 $ s "saw*4" # djf (slow 4 $ range 0.1 0.9 sine)

-- ボウエル（フォルマントフィルター）
d1 $ s "gtr*5" # vowel "a e i o u"
```

#### 歪み系

```haskell
-- Distort（高調波豊か）
d1 $ s "bd*4" # distort 0.3

-- Triode（真空管風歪み）
d1 $ s "bd*4" # triode 0.5

-- Shape（アンプ型サチュレーション）
d1 $ s "bd*4" # shape 0.3

-- Bitcrusher
d1 $ s "arpy*4" # crush 4   -- 4bit相当
```

#### ピッチ・モジュレーション系

```haskell
-- トレモロ
d1 $ s "arpy*4" # tremolodepth 0.5 # tremolorate 4

-- リングモジュレーション
d1 $ s "arpy*4" # ring 0.5 # ringf 300 # ringdf 0.1

-- フリクエンシーシフター
d1 $ s "arpy*4" # fshift 50 # fshiftnote 2

-- Octer（倍音追加）
d1 $ s "bass3*4" # octer 0.5 # octersub 0.3
```

#### スペクトル系（Mads Kjeldgaard）

```haskell
-- スペクトルディレイ
d1 $ s "arpy*4" # xsdelay 4 # tsdelay 0.5

-- Freeze（スペクトル凍結）
d1 $ s "arpy" # freeze 1

-- スペクトルLPF/HPF（0〜1のスペクトル割合）
d1 $ s "arpy*4" # lbrick 0.3   -- 下30%をカット
d1 $ s "arpy*4" # hbrick 0.7   -- 上30%をカット

-- コムフィルター
d1 $ s "arpy*4" # comb 5
```

---

### 4. MIDI外部デバイスへの送信

```supercollider
// SC側の初期化
MIDIClient.init;
~midiOut = MIDIOut.newByName("IAC Driver", "Bus 1");
~dirt.soundLibrary.addMIDI(\mydevice, ~midiOut);
~midiOut.latency = 0.1;
```

```haskell
-- Tidalからの送信
d1 $ n "0 2 4 7" # s "mydevice"
d1 $ n "c4 d4 e5 g3" # s "mydevice"

-- CC送信
d1 $ ccv (range 0 127 sine) # ccn 74 # s "mydevice"
```

---

### 5. OSC送信（TouchDesigner / Hydra等への連携）

```haskell
-- Haskell設定ファイル (BootTidal.hs) にターゲット追加
let target = Target {
      oName = "visualiser",
      oAddress = "localhost",
      oPort = 7000,
      oLatency = 0.1,
      oSchedule = Live,
      oWindow = Nothing,
      oHandshake = False,
      oBusPort = Nothing
    }

let oscplay = OSC "/play" $ ArgList [
      ("s",       Nothing),
      ("pan",     Just $ VF 0.5),
      ("cutoff",  Just $ VF 1000),
      ("gain",    Just $ VF 1.0)
    ]

let td = (target, [oscplay])
stream <- startStream defaultConfig [td]
let d1 = streamReplace stream 1 . (|< orbit 0)
```

---

### 6. SuperDirt SynthDef の設計パターン

**音を豊かにするコツ（SuperDirt向け）：**

```supercollider
// デチューン2〜3声でユニゾン厚みを出す
SynthDef(\fattylead, { |out, freq=440, amp=0.3, pan=0, sustain=1, gate=1,
                        detune=0.015, cutoff=3000, res=0.3|
    var sigs, env, sig;

    // 3声デチューン（微妙にずらしてステレオ広がりを作る）
    sigs = [
        Saw.ar(freq * (1 - detune)),
        Saw.ar(freq),
        Saw.ar(freq * (1 + detune))
    ];

    // サチュレーション → フィルター → エンベロープ
    sig  = Mix(sigs) * 0.33;
    sig  = (sig * 2).tanh;          // ソフトクリッピングで倍音追加
    sig  = RLPF.ar(sig, cutoff.lag(0.05), res);
    env  = EnvGen.ar(Env.adsr(0.01, 0.1, 0.8, 0.3), gate, doneAction: 2);

    Out.ar(out, Pan2.ar(sig * env * amp, pan));
}).add;

~dirt.soundLibrary.addSynth(\fattylead);
```

```haskell
d1 $ n "0 3 5 7" # s "fattylead"
   # detune 0.02
   # cutoff (range 800 4000 $ slow 8 sine)
   # res 0.4
   # room 0.3
```
