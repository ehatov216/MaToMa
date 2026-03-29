---
title: Norns SC エンジンパターン — MaToMaへの応用
category: synth
tags: [norns, CroneEngine, ParGroup, MoogFF, PolyPerc, granular, FM, physical-modeling, SelectX, SpecCentroid]
---

## Norns SC パターン集

Monome Norns のコミュニティエンジンから抽出した、
MaToMaのSynthDef設計に直接使えるパターン。

---

### 1. ParGroup — 並列ボイス管理（PolyPercパターン）

ポリフォニーの定番構造。ノートごとに Synth をスポーンし、`doneAction:2` で自動解放。

```supercollider
// グループを作ってその中にボイスをスポーンする
(
var pg = ParGroup.new;

SynthDef(\poly_voice, {
    arg out=0, freq=440, amp=0.3, pw=0.5,
        cutoff=2000, gain=2.0, release=0.5, pan=0;
    var snd, filt, env;

    snd  = Pulse.ar(freq, pw);
    filt = MoogFF.ar(snd, cutoff, gain);
    env  = EnvGen.ar(Env.perc(0.005, release, level: amp), doneAction: 2);

    Out.ar(out, Pan2.ar(filt * env, pan));
}).add;

// ノートごとにスポーン
~playNote = { |freq, amp=0.3, release=0.4, pan=0|
    Synth(\poly_voice, [
        \out, 0, \freq, freq, \amp, amp,
        \release, release, \pan, pan
    ], target: pg);
};

~playNote.(220);
~playNote.(330, pan: 0.5);
~playNote.(440, pan: -0.5);
)
```

---

### 2. コントロールバスによる全ボイス同期更新（PolySubパターン）

パラメーターをバスに書くことで、発音中の全ボイスに即座に反映できる。

```supercollider
(
// パラメーターごとにコントロールバスを用意
var cutBus    = Bus.control(s);
var resBus    = Bus.control(s);
var ampBus    = Bus.control(s);

cutBus.set(2000);  resBus.set(0.3);  ampBus.set(0.5);

SynthDef(\bus_mapped_voice, {
    arg out=0, freq=440, cut=2000, res=0.3, amp=0.5, gate=1;
    var sig, env;
    sig = Saw.ar([freq, freq * 1.005]);
    sig = RLPF.ar(sig, cut, res);
    env = EnvGen.ar(Env.adsr(0.01, 0.1, 0.8, 0.3), gate, doneAction: 2);
    Out.ar(out, sig * env * amp);
}).add;

// ボイス生成時にバスをマップ
~spawnVoice = { |freq|
    var v = Synth(\bus_mapped_voice, [\out, 0, \freq, freq]);
    v.map(\cut, cutBus, \res, resBus, \amp, ampBus);  // バスにマップ
    v
};

// バスを変えると全ボイスに即反映
~setCut = { |hz| cutBus.set(hz) };
~setCut.(800);  // 発音中の全ボイスのカットオフが即変わる
)
```

---

### 3. SelectX — 複数波形のリアルタイムモーフィング

`Select.ar`（ハードスイッチ）ではなく `SelectX.ar`（クロスフェード）で滑らかな波形モーフィング。

```supercollider
SynthDef(\morphing_osc, {
    arg out=0, freq=220, amp=0.3, shape=0, gate=1;
    // shape: 0=sine, 1=triangle, 2=saw, 3=pulse
    var osc1 = SinOsc.ar(freq);
    var osc2 = LFTri.ar(freq);
    var osc3 = Saw.ar(freq);
    var osc4 = Pulse.ar(freq, 0.3);

    var sig = SelectX.ar(shape, [osc1, osc2, osc3, osc4]);
    var env = EnvGen.ar(Env.adsr(0.01, 0.1, 0.8, 0.3), gate, doneAction: 2);

    Out.ar(out, Pan2.ar(sig * env * amp, 0));
}).add;

// shape を 0.0〜3.0 でスムーズに動かすと波形がモーフする
Synth(\morphing_osc, [\shape, 1.5]);  // saw と triangle の中間
```

---

### 4. グレイン合成（Norns Siloパターン）

`spray` パラメーターで規則的→ランダムへの密度をコントロールする手法。

```supercollider
SynthDef(\silo_grain, {
    arg out=0, bufnum=0, rate=1, dur=0.1, pos=0.5,
        jitter=0.1, spray=0.5, density=12, amp=0.5, gate=1;
    var trig, sig, env;

    // spray=0: 規則的(Impulse), spray=1: ランダム(Dust)
    trig = SelectX.kr(spray, [
        Impulse.kr(density),
        Dust.kr(density)
    ]);

    sig = GrainBuf.ar(
        numChannels: 2,
        trigger:     trig,
        dur:         dur,
        sndbuf:      bufnum,
        rate:        rate,
        pos:         pos + LFNoise0.kr(6).bipolar(jitter),
        pan:         LFNoise1.kr(4).range(-0.6, 0.6)
    );
    env = EnvGen.ar(Env.adsr(0.5, 0.0, 1.0, 1.0), gate, doneAction: 2);

    Out.ar(out, sig * env * amp);
}).add;
```

---

### 5. FM合成（インデックスエンベロープ付き）

Norns Odashodashoパターン：インデックスが攻撃時に膨らむことで「金属的なアタック」を作る。

```supercollider
SynthDef(\fm_metal, {
    arg out=0, freq=440, mRatio=2.0, cRatio=1.0,
        index=2.0, iScale=5.0,              // iScale: アタック時の最大インデックス倍率
        cAtk=4, cRel=(-4),                  // エンベロープのカーブ
        amp=0.3, atk=0.01, rel=2.0, gate=1;
    var car, mod, env, iEnv;

    // インデックスのエンベロープ（アタック時だけ高くなる）
    iEnv = EnvGen.kr(
        Env([index, index * iScale, index], [atk, rel], [cAtk, cRel])
    );
    env  = EnvGen.ar(
        Env.perc(atk, rel, curve: [cAtk, cRel]), doneAction: 2
    );

    mod  = SinOsc.ar(freq * mRatio, mul: freq * mRatio * iEnv);
    car  = SinOsc.ar(freq * cRatio + mod) * env * amp;

    // 微細なコーラス（Norns Odashodasho由来）
    car  = DelayC.ar(car, 0.03,
        LFNoise1.kr(Rand(5, 10), 0.01, 0.02)
    );

    Out.ar(out, Pan2.ar(car, 0));
}).add;
```

---

### 6. 物理モデリング — Karplus-Strong弦 + Ringz ボディ共鳴

Norns UprightBassパターンをシンプルにしたもの。

```supercollider
SynthDef(\ks_string, {
    arg out=0, freq=110, amp=0.5, brightness=0.6,
        decay=3.0, body=0.3, gate=1;
    var exciter, string, bodyRes, sig, env;

    // エキサイター（弦の弾き）
    exciter = PinkNoise.ar * EnvGen.ar(Env.perc(0.001, 0.01));

    // Karplus-Strong 弦モデル
    string  = CombL.ar(
        exciter,
        maxdelaytime: 1/20,
        delaytime:    1/freq,
        decaytime:    decay * brightness.linlin(0, 1, 1.5, 0.6)
    );
    string  = LPF.ar(string, freq * brightness.linexp(0, 1, 2.5, 12));
    string  = LeakDC.ar(string);  // DCオフセット除去（必須）

    // ボディ共鳴（Ringzで3つのモード）
    bodyRes = Mix([
        Ringz.ar(string, freq * 0.7,  0.3) * 0.4,
        Ringz.ar(string, freq * 1.0,  0.2) * 0.4,
        Ringz.ar(string, freq * 1.55, 0.15) * 0.2
    ]) * body;

    sig = XFade2.ar(string, bodyRes, body * 2 - 1);
    env = EnvGen.ar(Env.adsr(0.001, 0.1, 1.0, 1.5), gate, doneAction: 2);

    Out.ar(out, Pan2.ar(sig * env * amp, 0));
}).add;
```

---

### 7. エフェクトバス構成（Anvilパターン）

ドライシグナルをバスに書き、テールに繋いだエフェクトシンセが読む。

```supercollider
(
var efxBus = Bus.audio(s, 2);

// エフェクトシンセを先に（テールに）配置
SynthDef(\reverb_tail, {
    arg in, out=0, mix=0.3, room=0.8;
    var sig = In.ar(in, 2);
    var wet = JPverb.ar(sig, t60: room, damp: 0.1);
    Out.ar(out, XFade2.ar(sig, wet, mix * 2 - 1));
}).add;

// ボイスシンセはバスに書く
SynthDef(\dry_voice, {
    arg out, freq=440, amp=0.3, rel=0.5;
    var sig = Saw.ar([freq, freq*1.006]) * 0.5;
    var env = EnvGen.ar(Env.perc(0.01, rel, level:amp), doneAction: 2);
    Out.ar(out, sig * env);
}).add;

s.sync;

// 順序：dry_voice → efxBus → reverb_tail → hardware out
var efx = Synth(\reverb_tail, [\in, efxBus, \out, 0, \mix, 0.4]);
~play = { |freq, amp=0.3|
    Synth(\dry_voice, [\out, efxBus, \freq, freq, \amp, amp], addAction: \addToHead);
};
)
```

---

### 8. スペクトル分析 → OSCフィードバック（ポーリングパターン）

音の明るさをリアルタイム計測してPythonブリッジに送る。

```supercollider
// SpecCentroid でスペクトル重心を計測し、OSCでPythonへ
(
var analysBus = Bus.audio(s, 1);

SynthDef(\brightness_tracker, {
    arg in, out_centroid, out_amp;
    var sig   = In.ar(in);
    var chain = FFT(LocalBuf(2048), sig);
    Out.kr(out_centroid, SpecCentroid.kr(chain));
    Out.kr(out_amp,      Amplitude.kr(sig, 0.01, 0.1));
}).play;

// 定期的にOSCで送信
~brightBus = Bus.control(s);
~ampBus    = Bus.control(s);

OSCdef(\poll, {}, '/dummy');  // ポーリングループ
Routine({
    loop {
        ~brightBus.get({ |v|
            NetAddr("127.0.0.1", 8765).sendMsg('/analysis/centroid', v);
        });
        ~ampBus.get({ |v|
            NetAddr("127.0.0.1", 8765).sendMsg('/analysis/amp', v);
        });
        0.1.wait;
    }
}).play;
)
```

---

### 9. LagUD — 攻撃と減衰で異なるスムージング

`LagUD` は上昇・下降の速度を別々に設定できる。カットオフの「すっと上がって、ゆっくり下がる」に最適。

```supercollider
SynthDef(\lag_filter, {
    arg out=0, freq=220, amp=0.3, cutoff=4000, gate=1;
    var sig, filt, env;
    // カットオフ: 0.01秒で上昇、0.5秒でゆっくり下降
    var smoothCut = LagUD.kr(cutoff, lagTimeU: 0.01, lagTimeD: 0.5);
    sig  = Saw.ar([freq, freq * 1.004]);
    filt = RLPF.ar(sig, smoothCut, 0.4);
    env  = EnvGen.ar(Env.adsr(0.01, 0.1, 0.8, 0.3), gate, doneAction: 2);
    Out.ar(out, filt * env * amp);
}).add;
```

---

### MaToMa で使うべきパターン選択ガイド

| 目的 | 使うパターン |
|------|------------|
| ポリフォニックな音源 | `ParGroup` + `Env.perc(doneAction:2)` |
| ライブ中のパラメーター一括変更 | コントロールバス + `.map()` |
| 波形のなめらかな切り替え | `SelectX.ar` |
| Autechre的なグリッチ感 | `spray` パラメーター (Impulse ↔ Dust) |
| 金属的なアタック | FMインデックスエンベロープ (`iScale`) |
| 有機的な弦・共鳴音 | KS弦 (`CombL`) + Ringz ボディ |
| 音の明るさをUIに表示 | `SpecCentroid.kr(FFT(...))` + OSCポーリング |
| エフェクトの順序を守る | 送りバス + `addToTail` でエフェクトを後置 |
