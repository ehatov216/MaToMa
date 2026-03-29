---
title: SuperCollider UGenカタログ — カテゴリ別リファレンス
category: reference
tags: [UGen, oscillator, filter, noise, reverb, delay, granular, FFT, panning, envelope, LFO]
---

## SuperCollider UGen カテゴリ別カタログ

SCには250以上のUGenがある。カテゴリ別に整理した実用リファレンス。

---

### 1. 発振器（オシレーター）

#### バンドリミット付き（エイリアスなし・音楽用）
```supercollider
SinOsc.ar(freq, phase, mul, add)    // 正弦波
Blip.ar(freq, numHarmonics)         // 整数倍音の合計（add）
Saw.ar(freq)                        // のこぎり波
Pulse.ar(freq, width)               // 矩形波（width=0.5でスクエア）
```

#### LF系（非バンドリミット・高周波でエイリアスあり）
```supercollider
LFSaw.ar(freq)      // LFのこぎり
LFTri.ar(freq)      // LF三角波
LFPar.ar(freq)      // LF放物線（サインの近似）
LFCub.ar(freq)      // LF立方波
LFPulse.ar(freq, iphase, width)     // LF矩形波
VarSaw.ar(freq, iphase, width)      // 可変幅のこぎり/三角
SyncSaw.ar(syncFreq, sawFreq)       // オシレーターシンク
```

#### 複雑な発振器
```supercollider
PMOsc.ar(carfreq, modfreq, pmindex)     // 位相変調
COsc.ar(bufnum, freq, beats)            // バッファ読み・ビート
Klang.ar(`[ [freqs], [amps], [phases] ], freqscale)  // サイン波バンク
Formant.ar(fundfreq, formfreq, bwfreq) // フォルマント合成
```

---

### 2. ノイズ・非周期ソース

```supercollider
WhiteNoise.ar       // 白色雑音（全周波数均等）
PinkNoise.ar        // ピンクノイズ（1/fスペクトル、自然音的）
BrownNoise.ar       // ブラウンノイズ（1/f²、低音豊か）
Dust.ar(density)    // ランダムなインパルス（密度=Hz）
Dust2.ar(density)   // Dustの双極版（-1〜+1）
ClipNoise.ar        // ±1のランダム切り替え
```

#### LFノイズ（制御信号用）
```supercollider
LFNoise0.kr(freq)   // ステップ状ランダム（値を保持してジャンプ）
LFNoise1.kr(freq)   // 線形補間ランダム（滑らか）
LFNoise2.kr(freq)   // 曲線補間ランダム（より滑らか）
LFClipNoise.kr(freq)// ±1のステップランダム
```

---

### 3. フィルター

#### 基本フィルター
```supercollider
LPF.ar(sig, freq)               // 12dB/oct ローパス
HPF.ar(sig, freq)               // 12dB/oct ハイパス
BPF.ar(sig, freq, rq)           // バンドパス（rq=帯域幅比）
BRF.ar(sig, freq, rq)           // バンドリジェクト（ノッチ）
RLPF.ar(sig, freq, rq)          // 共鳴LPF
RHPF.ar(sig, freq, rq)          // 共鳴HPF
```

#### 高品質フィルター（Norns/音楽用）
```supercollider
MoogFF.ar(sig, freq, gain)      // Moogラダーフィルター（最も「アナログ」）
SVF.ar(sig, freq, q, type)      // 状態変数フィルター（LP/HP/BP/Notch）
```

#### スペクトル操作
```supercollider
LeakDC.ar(sig, coef)            // DCオフセット除去（KS弦の後に必須）
Median.ar(length, sig)          // メジアンフィルター（スパイク除去）
```

---

### 4. リバーブ・空間系

```supercollider
FreeVerb.ar(sig, mix, room, damp)           // 基本的なリバーブ
GVerb.ar(sig, roomsize, revtime, damping)   // より豊かなリバーブ
JPverb.ar(sig, t60, damp, size)             // 高品質アルゴリズミックリバーブ（ATK）
Allpass{N,L,C}.ar(sig, maxtime, delaytime, decaytime)  // オールパスフィルター
```

---

### 5. ディレイ・バッファ系

```supercollider
// 単純ディレイ（N=非補間, L=線形, C=3次）
DelayN.ar(sig, maxtime, delaytime)
DelayL.ar(sig, maxtime, delaytime)
DelayC.ar(sig, maxtime, delaytime)

// フィードバックディレイ（コム）
CombN.ar(sig, maxtime, delaytime, decaytime)
CombL.ar(sig, maxtime, delaytime, decaytime)   // KS弦モデルに使う
CombC.ar(sig, maxtime, delaytime, decaytime)

// オールパスディレイ
AllpassN.ar(sig, maxtime, delaytime, decaytime)
AllpassL.ar(sig, maxtime, delaytime, decaytime)

// バッファ再生
BufRd.ar(numChannels, bufnum, phase)
BufWr.ar(inputArray, bufnum, phase)
RecordBuf.ar(inputArray, bufnum)
PlayBuf.ar(numChannels, bufnum, rate, trigger, startPos, loop)
```

---

### 6. グレイン合成

```supercollider
TGrains.ar(numCh, trigger, bufnum, rate, centerPos, dur, pan, amp)
GrainBuf.ar(numCh, trigger, dur, sndbuf, rate, pos, pan)
GrainSin.ar(numCh, trigger, dur, freq, pan, amp)
GrainFM.ar(numCh, trigger, dur, carFreq, modFreq, index, pan)
GrainIn.ar(numCh, trigger, dur, in, pan, amp)
```

---

### 7. パンニング・ルーティング

```supercollider
Pan2.ar(monoSig, pos)           // モノ→ステレオ（pos: -1〜+1）
Pan4.ar(monoSig, xpos, ypos)    // 4チャンネルクワッドパン
PanAz.ar(numChans, sig, pos)    // 任意チャンネル数のアジマスパン
Balance2.ar(left, right, pos)   // ステレオのパン
Splay.ar(arrayOfSigs)           // 配列の信号を均等にステレオ展開
Mix.ar(arrayOfSigs)             // 配列の信号を1つにミックス
XFade2.ar(inA, inB, pan)        // クロスフェード（pan=-1でA、+1でB）
```

---

### 8. エンベロープ・制御

```supercollider
// エンベロープジェネレーター
EnvGen.ar(env, gate, levelScale, levelBias, timeScale, doneAction)
EnvGen.kr(env, gate)            // 制御レート版（より軽い）

// エンベロープ形状（Envクラス）
Env.perc(atk, rel, level, curve)        // パーカッシブ
Env.adsr(atk, dec, sus, rel)            // サステイン付き
Env.asr(atk, sus, rel)                  // アタック・サステイン・リリース
Env.new([levels], [times], [curves])    // カスタム
Env.linen(atk, sus, rel)                // 線形（台形）

// カーブ値の意味
// 0: 線形, -2〜-5: 指数的（急な立ち上がり）, 2〜5: 指数的（ゆっくり立ち上がり)
// \sin, \cos, \wel, \step: 特殊カーブ

// Decayシリーズ（エンベロープフォロワー的な用途）
Decay.ar(trigger, decayTime)
Decay2.ar(trigger, attackTime, decayTime)
```

---

### 9. トリガー・カウンター・ゲート

```supercollider
Impulse.ar(freq)                // 定期的なインパルス
Impulse.kr(freq)                // 制御レート版（クロック用途）
TRand.kr(min, max, trigger)     // トリガーごとにランダム値
TIRand.kr(min, max, trigger)    // 整数版
CoinGate.kr(prob, trigger)      // 確率ゲート（probの確率で通過）
PulseCount.ar(trigger, reset)   // トリガーをカウント
PulseDivider.ar(trigger, div)   // トリガーをN分周
Stepper.kr(trigger, reset, min, max, step)  // ステップカウンター
```

---

### 10. スムージング・ラグ

```supercollider
Lag.kr(sig, lagTime)            // 一方向ラグ（変化を遅らせる）
Lag3.kr(sig, lagTime)           // よりスムーズなラグ
LagUD.kr(sig, lagUp, lagDown)   // 上昇・下降で異なる時定数
VarLag.kr(sig, time, curvature) // 可変ラグ（時間自体もパターン可）
Slew.kr(sig, upSlew, downSlew)  // スルーリミター
```

---

### 11. FFT・スペクトル処理（PV_UGen）

```supercollider
// 基本
FFT(localBuf, sig)              // 時間→周波数領域
IFFT(chain)                     // 周波数→時間領域

// スペクトル処理（chainを渡して変換）
PV_MagAbove(chain, threshold)   // しきい値以上の倍音だけ残す
PV_MagBelow(chain, threshold)   // しきい値以下の倍音だけ残す
PV_BrickWall(chain, wipe)       // スペクトルを端から消す
PV_MagFreeze(chain, freeze)     // スペクトル凍結（freeze>0で止める）
PV_RandComb(chain, wipe, trigger)    // ランダムな倍音を消す
PV_MagSmear(chain, bins)        // 倍音をぼかす
PV_Diffuser(chain, trigger)     // 位相をランダム化（グリッチ感）
PV_MagShift(chain, stretch, shift)   // 倍音をシフト（ピッチシフタ）
PV_MagMul(chainA, chainB)       // 2つのスペクトルを掛け算
PV_Add(chainA, chainB)          // 2つのスペクトルを足す

// 分析
SpecCentroid.kr(chain)          // スペクトル重心（音の「明るさ」）
SpecFlatness.kr(chain)          // スペクトル平坦度（ノイズ度）
```

---

### 12. UGen の ar/kr の使い分け

| | `.ar` | `.kr` |
|---|---|---|
| レート | オーディオレート（44100 Hz） | 制御レート（~689 Hz）|
| CPU | 重い | 軽い |
| 用途 | 音声信号 | パラメーター制御 |
| 判断基準 | 出力が音として聞こえる | 速い変化が不要なパラメーター |

```supercollider
// 実践例：LFOは .kr で十分
{
    var cutoff = LFNoise1.kr(0.5).range(200, 4000);  // 制御レートで十分
    var sig    = Saw.ar(220);                          // 音声はar必須
    RLPF.ar(sig, cutoff, 0.3) ! 2
}.play;
```
