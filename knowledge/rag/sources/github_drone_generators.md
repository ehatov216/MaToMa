---
title: GitHub Open-Source Drone Generator Patches (SuperCollider)
category: reference
tags: [drone, ambient, github, feedback, fm, wavetable, noise-filter, open-source]
---

## GitHub オープンソース ドローンジェネレーター集

GitHubおよびsccode.orgで公開されているSuperColliderのドローン・アンビエントパッチの技法まとめ。

---

## リポジトリ一覧

### 1. danielmkarlsson / a_loss_of_self
**URL:** https://github.com/danielmkarlsson/a_loss_of_self
**特徴:** 「無限の持続時間を持つドローン」。FM + グリッサンド + Pseedで再現可能な無限生成。

**技法:**
- FM合成（SinOsc キャリア + モジュレーター）
- `XLine.ar` によるピッチグリッサンド（freqDeviation → 1.0）
- `Pluck.ar` をピンクノイズで励起してレゾナンス追加
- `AmpCompA.kr` で聴覚補正（高音域の自然な音量補正）
- `Pseed` 固定で毎回同じ「無限の曲」を再現
- 倍音数の逆数（`Pkey(\harmonic).reciprocal`）で音量バランス

```supercollider
SynthDef.new(\als, {
    arg freq = 440, modIndex = 2, phaseModIndex = 2,
        lpfFreq = 18000, resonance = 0, hold = 6.0,
        freqDeviation = 0.975, transitionTime = 0.875;
    var sig, mod, phasemod, env;
    mod = SinOsc.ar(freq/2, 0, Line.ar(0, modIndex, transitionTime) * freq);
    phasemod = SinOsc.ar(freq, 0, phaseModIndex);
    sig = SinOsc.ar(XLine.ar(freqDeviation * freq, freq, 8.0) + mod, phasemod);
    sig = (sig * 0.8) + (Pluck.ar(sig, PinkNoise.ar(), 0.25, freq.reciprocal, 64.0, 0.5) * 0.4);
    sig = RLPF.ar(sig, lpfFreq, Line.ar(1.0, resonance, 8.0));
    sig = tanh(sig * 0.5);
    sig = (sig * 0.75) + (Resonz.ar(sig, freq, 0.1) * 1.125);
    sig = sig * AmpCompA.kr(freq, 12.978271799373);
    sig = Compander.ar(sig, sig, 0.25, 0.33, 1, 0.002, 0.1);
    Out.ar(0, Limiter.ar(sig, 0.1));
}).add;

// Pseedで再現可能な無限シーケンス
Pdef(\alspat, Pseed(2160, Pbind(
    \instrument, \als,
    \dur, Pwhite(0.1, 10.0, inf),
    \midinote, Pstutter(Pwhite(2,7)*2,
        Prand([Pseq([44, 20, 21, 27]), Pseq([32, 20, 39, 40])], inf)
    ),
    \harmonic, Pexprand(1, 9, inf).round,
    \atk, Pwhite(15.0, 45.0, inf),   // 超長アタック（15〜45秒）
    \rel, Pwhite(30.0, 60.0, inf),   // 超長リリース
    \amp, Pkey(\harmonic).reciprocal * 0.75
))).play;
```

---

### 2. minouminou / DroneCollider
**URL:** https://github.com/minouminou/DroneCollider
**特徴:** NI Reaktor Space DroneのSCポート。24声ユニゾン＋Geiger管フィードバック。

**技法:**
- 24声のユニゾン（各Synthが独立したRandIDを持つ）
- `SVF.ar` バンドパスフィルターでWhiteNoiseを整形
- `LocalIn/LocalOut` フィードバックループ（Geiger計数管エミュレーション）
- `TRand.kr` で各ボイスにランダムピッチゆらぎ
- パワースペクトル重み付け `(1/(i+offset))^kDamp` で倍音バランス計算
- `RandID.ir + RandSeed.ir` で各声部のランダムを独立制御

```supercollider
// 各ボイスが独立したランダムシード
SynthDef(\DroneCollider, { |out, voiceid = 1|
    RandID.ir(id: voiceid);
    RandSeed.ir(1, voiceid);

    // Geiger計数管フィードバック（自己発振するパルス）
    var cntFreq = p_to_f.value(LocalIn.ar(1) + IRand(-3, 3) + kDensity);
    var geiger = LFPulse.ar(freq: cntFreq, width: 0.5);
    LocalOut.ar(geiger);

    // ノイズをバンドパスフィルターで整形
    var filterP = p_to_f.value(sout1 + (sout2 * kPitch) + slowRandom);
    var sout3 = SVF.ar(WhiteNoise.ar(), cutoff: filterP, res: filterRes, bandpass: 1);

    // 倍音減衰重みで音量計算
    var sout4 = (1 / (voiceid + kOffset)).pow(kDamp) / voiceConst * kGain.pow(3);

    Out.ar(out, Pan2.ar(sout3 * sout2 * sout4, panLFO));
}).add;

// 24声を一気に生成
(1..24).do { |i| Synth(\DroneCollider, [\voiceid, i]) };
```

---

### 3. frederickk / stjoernuithrott (Engine_SCgazer)
**URL:** https://github.com/frederickk/stjoernuithrott
**特徴:** Norns用。Moffeenzeef Stargazerエミュレーション。ランダム波形テーブル＋デジタルデグレード。

**技法:**
- `Env.asSignal.asWavetable` で90種類のランダム波形を生成
- `VOsc.ar` でウェーブテーブルオシレーター（デチューン2基）
- `Select.kr` でLFO波形をランタイム選択（LFCub/LFTri/LFSaw/LFPulse）
- `Decimator.ar` でビット＆サンプルレート削減（デジタルグリッチ）
- Moogラダーフィルター2段（各LFOで独立変調）

```supercollider
// 90種類のランダム波形テーブルを生成
~wt = Array.fill(100, {
    var numSegs = rrand(10, 20);
    Env(
        (({rrand(0.0, 1.0)}!(numSegs-1)) * [1, -1]).scramble,
        {rrand(1, 20)}!numSegs,
        'sine'
    ).asSignal(1024).asWavetable;
});

// 3系統のLFO（実行時に波形タイプを選択）
var lfo1 = Select.kr(lfo1type, [LFCub.kr(rate1), LFTri.kr(rate1), LFSaw.kr(rate1), LFPulse.kr(rate1)]);

// デジタルグリッチ：alias（サンプルレート削減）とredux（ビット削減）
var degraded = Decimator.ar(sig, alias * s.sampleRate, redux);
```

---

### 4. sccode.org — Feedback Ambient (rumush)
**URL:** https://sccode.org/1-50D
**特徴:** `LocalIn/LocalOut` フィードバックネットワーク。Burialっぽい浮遊感を最小コードで生成。

**技法:**
- `LocalIn/LocalOut` 自己参照フィードバックループ
- `FreqShift.ar` 微小ピッチシフト（-1Hzで金属的質感）
- 複数段の `DelayC.ar` でノイズフロア生成
- `Ndef` によるライブコーディング対応ホットスワップ

```supercollider
Ndef(\fdb1, {
    var src, freq = 60.midicps, rt = 0.25;
    src = Saw.ar(freq) * Decay.ar(Impulse.ar(rt), 1/rt, 0.25);
    var loc = LocalIn.ar(2) + src;        // フィードバック入力
    loc = FreqShift.ar(loc, -1);          // 微小ピッチシフト（-1Hz）
    loc = loc + DelayC.ar(loc, 0.2, freq.reciprocal);
    loc = DelayC.ar(loc, 4, LFNoise1.ar(rt!2).range(0.25, 2));
    loc = loc + AllpassC.ar(loc, 0.1, LFNoise0.ar(rt!2).range(0.05, 0.1), 4);
    loc = HPF.ar(loc, 100);
    LocalOut.ar(loc * 1.75);             // フィードバック出力（増幅して持続）
    Out.ar(0, Limiter.ar(loc) * 0.5);
}).play
```

---

### 5. sccode.org — Meandering Sines (emergent)
**URL:** https://sccode.org/1-5eE
**特徴:** Brian Eno的アンビエント手法の教科書的実装。8声の揺れるSinOscをPbindでオーバーラップ。

**技法:**
- 8声の `SinOsc` を低速LFOで独立変調（周波数・振幅・パン）
- `Pbindef` で18〜30秒のデュレーション、オーバーラップあり
- コードタイプ（5th, maj6, min6, maj7）からランダム選択
- ASRエンベロープ（アタック3〜4秒）

---

### 6. slopate / Supercollider-Ambient-Music
**URL:** https://github.com/slopate/Supercollider-Ambient-Music
**特徴:** `PartConv.ar` コンボリューションリバーブを活用した空間的パッド。学習用。

**技法:**
- `PartConv.ar` でIRファイルを使ったコンボリューションリバーブ
- デチューンSaw × 3声 + `AllpassC` フェイザー
- `BrownNoise.ar` でフルートのブレスノイズをシミュレート

---

### 7. dkmayer / miSCellaneous_lib
**URL:** https://github.com/dkmayer/miSCellaneous_lib
**スター数:** 75
**特徴:** 包括的SC拡張ライブラリ。ドローン制作に直結する拡張を含む。

含まれる要素:
- グラニュラー合成のパターン統合
- シングルサンプルフィードバック（SSB）
- ウェーブフォールド合成
- `Pbind` ベースの自動パラメーター生成

---

## 技法カテゴリ別まとめ

| 技法 | 主なUGen | 代表例 | 美学的特徴 |
|------|---------|--------|-----------|
| FM・PMドローン | `SinOsc`, `XLine`, `Pluck` | a_loss_of_self | 倍音が変化するロングトーン |
| ノイズ＋バンドパスフィルター | `WhiteNoise`, `SVF`, `RLPF` | DroneCollider | 多声ノイズドローン |
| ウェーブテーブル＋デグレード | `VOsc`, `Env.asWavetable`, `Decimator` | SCgazer | Autechre的な予測不能な倍音 |
| フィードバックネットワーク | `LocalIn/Out`, `FreqShift`, `DelayC` | Feedback Ambient | 自己組織化する浮遊感 |
| 揺れるサイン波 | `SinOsc` × 8 + LFO | Meandering Sines | Eno的最小主義 |
| コンボリューションリバーブ | `PartConv` | SC-Ambient-Music | 空間的厚みのある音 |

---

## MaToMaへの応用

1. **`Pseed` 固定による再現可能な無限生成** — シーン固有のシードを持たせると同じ場の雰囲気が再現できる（a_loss_of_self）
2. **`LocalIn/LocalOut` + `FreqShift(-1Hz)`** — Burial的「浮遊感」を最小コードで実現（Feedback Ambient）
3. **`VOsc` + `Env.asWavetable` ランダム波形** — Autechre的な予測不能な倍音変化（SCgazer）
4. **`RandID/RandSeed` 声部分離** — 多声体でも各声部のランダムを独立制御（DroneCollider）
5. **倍音の逆数補正 `harmonic.reciprocal`** — 上の音ほど自然に小さくなるバランス（a_loss_of_self）
