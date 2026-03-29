---
title: 確率ベースのパラメーター制御設計 — 生成音楽の構造化
category: design
tags: [probability, generative, parameter-lock, ratchet, polyrhythm, controlled-chaos, design-pattern]
---

## 確率ベースのパラメーター制御

非線形・生成的な音楽制作における設計パターン集。
2020 Semi Modular / Fors Opal / TidalCycles / SC すべてに共通する考え方。

---

### 1. 確率トリガー — イベントを間引く

「全部鳴らさない」ことで生まれるグルーヴ。

```supercollider
// CoinGate: prob の確率でBangを通過させる
{
    var clock = Impulse.kr(8);
    var trig  = CoinGate.kr(0.6, clock);  // 60%の確率で通過
    var freq  = TRand.kr(200, 800, trig);
    var sig   = SinOsc.ar(freq) * Decay.kr(trig, 0.1);
    sig ! 2
}.play;
```

```haskell
-- Tidalでの確率トリガー
d1 $ degradeBy 0.4 $ s "hh*8"      -- 40%消す
d1 $ s "bd? ~ sn? ~"               -- ? = 50%で鳴る
d1 $ sometimesBy 0.3 (# gain 0) $ s "hh*8"  -- 30%でゲインを0に
```

---

### 2. パラメーターロック — ステップごとに値を固定

各ステップに固有のパラメーターを割り当てる（Elektron / Opal の手法）。

```supercollider
// ステップごとに異なるフィルターカットオフ
(
var steps = [800, 400, 2000, 600, 4000, 300, 1200, 800];  // 8ステップのパラメーターロック

SynthDef(\param_locked, {
    arg out = 0, rate = 4, amp = 0.25;
    var clock, idx, cutoff, sig, env;

    clock  = Impulse.kr(rate);
    idx    = Stepper.kr(clock, 0, 0, 7);

    // ステップごとのカットオフをDemandで読む
    cutoff = Demand.kr(clock, 0,
        Dseq(steps, inf)
    );

    sig = Saw.ar(220) * 0.5;
    sig = RLPF.ar(sig, cutoff.lag(0.02), 0.3);
    env = EnvGen.ar(Env.perc(0.01, 0.12), clock);

    Out.ar(out, sig * env * amp ! 2);
}).add;
Synth(\param_locked);
)
```

```haskell
-- Tidalでのパラメーターロック的表現
d1 $ s "bd ~ sn ~"
   # cutoff "800 400 2000 600"   -- ステップごとに異なるカットオフ
   # gain "1 0.7 1 0.8"
   # pan "0 -0.5 0.3 0.7"
```

---

### 3. ラチェット — 1ステップを細分化して連打

```supercollider
// ラチェット的な細分化
{
    var base_clock = Impulse.kr(2);
    var ratchet    = Impulse.kr(base_clock * TRand.kr(1, 4, base_clock));
    var sig = SinOsc.ar(440) * Decay.kr(ratchet, 0.05) * 0.3;
    sig ! 2
}.play;
```

```haskell
-- Tidalでのラチェット
d1 $ s "bd ~ sn ~"
d1 $ ply "1 1 3 1" $ s "bd ~ sn ~"  -- snを3連打
d1 $ every 4 (ply 3) $ s "bd sn"    -- 4サイクルに1回だけ3連打
```

---

### 4. ポリリズム / ポリメトリック — 異なる長さのループを重ねる

```supercollider
// 3:4のポリリズム
(
var clock3 = Impulse.kr(3);   // 3拍子
var clock4 = Impulse.kr(4);   // 4拍子

{
    var sig3 = SinOsc.ar(220) * Decay.kr(clock3, 0.1) * 0.3;
    var sig4 = SinOsc.ar(330) * Decay.kr(clock4, 0.05) * 0.2;
    (sig3 + sig4) ! 2
}.play;
)
```

```haskell
-- Tidalでのポリメトリック
d1 $ s "[bd*3, cp*4, hh*7]"   -- 3:4:7のポリリズム

-- 異なる長さのシーケンスを走らせる（いずれ位相がずれる）
d1 $ s "{bd cp hh}%4"         -- 3要素を4ステップで割り付け
d2 $ s "{bd cp hh sn}%3"      -- 4要素を3ステップで
```

---

### 5. 構造化されたランダム — 「偶然の形」を設計する

完全ランダムではなく、スケール・確率・範囲を制限した「形のあるランダム」。

```supercollider
// 音階上のランダムウォーク（隣接音に移動する確率が高い）
(
var scale = [0, 2, 3, 5, 7, 8, 10, 12];  // マイナースケール
var pos   = 0;

SynthDef(\random_walk, {
    arg out = 0, rate = 3, amp = 0.2, gate = 1;
    var clock, step, note, freq, sig, env;

    clock = Impulse.kr(rate);

    // 隣接方向への確率的な移動（±1が多く、±2が少ない）
    step  = Demand.kr(clock, 0,
        Dwrand([-2,-1,-1, 0, 1, 1, 2], [0.1, 0.25, 0.25, 0.05, 0.2, 0.1, 0.05], inf)
    );

    // スケールから音を選ぶ（はみ出したら折り返す）
    note  = Demand.kr(clock, 0,
        Dseq([0, 2, 3, 5, 7, 8, 10], inf)  // スケールをサイクル
    );

    freq  = (220 * (2 ** (note / 12))).lag(0.02);
    sig   = Saw.ar([freq, freq * 1.005]) * 0.4;
    sig   = RLPF.ar(sig, freq * 3, 0.4);
    env   = EnvGen.ar(Env.adsr(0.01, 0.05, 0.8, 0.3), gate, doneAction: 2);

    Out.ar(out, sig * env * amp);
}).add;
)
```

```haskell
-- Tidalでの構造化ランダム（スケール上のwchoose）
d1 $ n (scale "minor" $ wchoose [
        (0, 0.3), (2, 0.2), (3, 0.2),
        (5, 0.15), (7, 0.1), (10, 0.05)  -- 低音寄りに確率を重み付け
     ])
   # s "supersaw"
   # room 0.4
```

---

### 6. 複数の確率層を重ねる（MaToMa的アーキテクチャ）

```haskell
-- 3層の確率制御：マクロ（シーン）/ メゾ（フレーズ）/ ミクロ（イベント）

-- ミクロ: 個別イベントの確率
d1 $ degradeBy 0.2           -- 20%消す
   $ s "bd(3,8) ~ sn ~"
   # gain "1 0.8 1 0.7"

-- メゾ: フレーズ単位の変形
   $ every 4 (jux rev)       -- 4サイクルに1回左右反転
   $ every 7 (fast 2)        -- 7サイクルに1回2倍速

-- マクロ: シーン全体の確率（ライブ中に手動で変える）
-- xfadeIn 1 8 $ ...         -- 8サイクルかけてシーン切り替え
```

---

### 確率制御のライブ操作戦略

| フェーズ | 操作 |
|---------|------|
| 序盤（0〜5分） | prob低め、degrade少なめ → ループ・反復で場を作る |
| 展開（5〜15分） | every, perlin, wchoose → 少しずつ変化を加える |
| クライマックス | prob高め、fast, jux → 構造を崩し始める |
| 着地 | 新シーンへ xfadeIn、または silence で一度リセット |
