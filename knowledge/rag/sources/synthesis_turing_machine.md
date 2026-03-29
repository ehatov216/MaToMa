---
title: チューリングマシン型ランダム — シフトレジスタと確率進化
category: synth
tags: [turing-machine, LFSR, shift-register, probability, chaos, controlled-randomness, generative, Dejavu]
---

## チューリングマシン型ランダム（Shift Register Randomness）

**「同じだが少し違う」をアルゴリズムで実現する手法。**
ループする記憶に確率的な変異を加えることで、秩序と混沌の間を漂う。
Autechre・2020 Semi Modular・VCV Rack の Turing Machine に共通する設計原理。

### 基本原理

```
状態 B(t) = [b0, b1, b2, ... b15]  ← 16bitのビット列（メモリ）

1サイクルごとに：
  - 先頭ビット b0 → 出力（ノート/パラメーター）
  - 全体を1つシフト（b0→消滅、b1がb0に...）
  - 末尾に入る新ビット = 確率 PROB で反転、それ以外は b0 をコピー

PROB=0%   → 永遠に同じパターンが繰り返される（ループ）
PROB=50%  → 秩序と混沌の境界（最も音楽的）
PROB=100% → 完全なランダム（予測不能）
```

---

### SC実装① — シンプルなTuringMachine UGen代替

```supercollider
// 16ステップのシフトレジスタ型ランダムメロディ
(
SynthDef(\turing_melody, {
    arg out = 0, rate = 4, prob = 0.5,
        amp = 0.3, gate = 1, baseFreq = 220;
    var clock, idx, bits, note, freq, sig, env;

    clock = Impulse.kr(rate);

    // LocalBuf で16ビットのシフトレジスタを模倣
    // Stepper でステップ位置を追跡
    idx = Stepper.kr(clock, 0, 0, 15);

    // TRand で確率的にビット反転
    // coin: prob の確率で1を返す
    note = Demand.kr(clock, 0,
        Dseq([0,2,3,5,7,8,10], inf)  // マイナースケール
        + Dstutter(16, Dwhite(0, 2, inf))  // 確率的な変異
    );

    freq  = (baseFreq * (2 ** (note / 12))).lag(0.02);
    sig   = Saw.ar([freq, freq * 1.007]) * 0.5;
    sig   = RLPF.ar(sig, freq * 4, 0.3);
    env   = EnvGen.ar(Env.adsr(0.01, 0.1, 0.7, 0.2), gate, doneAction: 2);

    Out.ar(out, sig * env * amp);
}).add;
)
```

---

### SC実装② — Dejavuスタイル（過去の状態を記憶して確率で回帰）

```supercollider
// 過去N世代のパラメーター履歴を持ち、確率で過去に戻る
(
~djv_prob = 0.3;  // 過去に戻る確率
~djv_len  = 8;    // 何世代まで記憶するか
~history  = Array.fill(8, { rrand(0.2, 0.9) });
~current  = 0;

~dejavu = {
    // 現在値を記録
    ~history[~current % ~djv_len] = ~current_val;
    ~current = ~current + 1;

    // 確率で過去の値を使う
    if (1.0.rand < ~djv_prob) {
        // 過去のランダムな世代から取得
        ~history[(~current - rrand(1, ~djv_len)) % ~djv_len]
    } {
        // 新しいランダム値
        1.0.rand
    }
};
)

// SynthDef のパラメーター更新に使う
(
Routine({
    loop {
        var newCutoff = ~dejavu.() * 4000 + 200;
        ~mySynth.set(\cutoff, newCutoff);
        0.25.wait;
    }
}).play;
)
```

---

### SC実装③ — Demand UGen で本格的なシフトレジスタ

```supercollider
// Demand系UGenを使ったシフトレジスタ的パターン生成
(
SynthDef(\shift_register, {
    arg out = 0, rate = 6, prob = 0.4,
        amp = 0.25, gate = 1;
    var clock, trig, note, freq, sig, env, noise_gate;

    clock = Impulse.kr(rate);

    // 確率的なトリガー（prob の確率でイベント発生）
    noise_gate = CoinGate.kr(prob, clock);

    // Drand で「過去のパターン」を模倣（確率的な繰り返し）
    note = Demand.kr(clock, 0, Dseq([
        Drand([0, 3, 5, 7, 10], 1),    // ランダムなノート
        Dstutter(2, Dwhite(0, 12, 1)), // たまに連打
        Drand([0, 7, 12], 1)            // 確定的なアンカー
    ], inf));

    freq  = (220 * (2 ** (note / 12))).lag(0.01);
    sig   = Mix([
        Pulse.ar(freq, 0.3),
        Pulse.ar(freq * 0.5, 0.5) * 0.3  // サブオクターブ
    ]) * 0.4;
    sig   = MoogFF.ar(sig, freq * LFNoise1.kr(0.3).range(2, 8), 2.0);
    env   = EnvGen.ar(Env.perc(0.005, 0.15), noise_gate);

    Out.ar(out, Pan2.ar(sig * env * amp, LFNoise0.kr(rate * 0.5).range(-0.6, 0.6)));
}).add;
)
```

---

### SC実装④ — Tidal連携：パーリンノイズ + 確率変異

Tidalの `perlin` + `degrade` を組み合わせることでソフトウェア的なシフトレジスタに近い挙動を得る。

```haskell
-- Dejavu的なパターン：ゆっくり変化するが確率で突然変異
d1 $ every 8 (degradeBy 0.3)         -- 8サイクルに1回、30%の確率でイベントを消す
   $ every 5 (# speed (irand 2 + 1)) -- 5サイクルごとにランダムな速度変化
   $ s "bd(3,8) ~ sn ~"
   # cutoff (rangex 300 6000 $ slow 16 perlin)  -- perlinがDejavu的な連続変化
   # gain (range 0.6 1.0 $ slow 8 perlin)

-- チューリングマシン的なメロディ（スケール上をランダムに歩く）
d2 $ n (scale "minor" $ wchoose [
        (0, 0.3), (2, 0.2), (3, 0.2),
        (5, 0.15), (7, 0.1), (10, 0.05)
     ])
   # s "supersaw"
   # cutoff (rangex 400 4000 $ slow 12 $ perlin2 (sine * 2) (cosine * 2))
   # room 0.5
```

---

### 確率パラメーターの音楽的マッピング

| prob 値 | 音楽的効果 |
|---------|-----------|
| 0.0〜0.1 | ほぼ固定ループ（ミニマル）|
| 0.2〜0.4 | 緩やかな変化（アンビエント）|
| 0.4〜0.6 | 予測可能な中にサプライズ（Autechre的）|
| 0.7〜0.9 | 構造が崩れ始める（IDM/グリッチ）|
| 1.0 | 完全ランダム（ノイズ）|

**ライブ中の操作戦略：**
- 序盤：`prob` 低め → ループ的・反復的
- 中盤：`prob` 0.3〜0.5 → 徐々に変化を加える
- クライマックス：`prob` を上げて崩壊させ、新シーンへ
