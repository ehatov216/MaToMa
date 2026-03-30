---
title: SuperColliderにおけるグリッチノイズ生成の技術的考察
category: synthesis
tags: [glitch, post-digital, Gendy, bitcrush, stutter, PlayBuf, FFT, Demand, CoinGate, Latch]
sources:
  - "Kim Cascone: The Aesthetics of Failure (2000)"
  - "jamshark70: crossfade stutter technique (SuperCollider forum)"
  - "SuperCollider Demand-rate UGen documentation"
---

## グリッチ美学の核心

グリッチ・ミュージックは機器の「失敗（failure）」「誤作動（malfunction）」から生じる音響アーティファクトを意図的な作曲素材として使う。
Kim Casconeの「ポスト・デジタル（post-digital）」美学：**エラーを修正すべき問題ではなく、音響探求の源泉として捉える哲学的転換**。

---

## 1. バッファ操作とスタッター（時間領域）

### PlayBuf + Dust による破壊的再トリガー

```supercollider
// 基本的なスタッター（クリックあり）
b = Buffer.read(s, "sound.wav");
{
    var trig = Dust.ar(10);
    var pos = MouseY.kr(0, b.numFrames);
    PlayBuf.ar(1, b, BufRateScale.kr(b), trig, pos, 1);
}.play;
```

**クリックを滑らかにする（jamshark70式クロスフェードスタッター）：**

```supercollider
// ToggleFF で2系統のPlayBufを交互制御
{
    var trig = Dust.kr(8);
    var gate = ToggleFF.kr(trig);
    var gates = [gate, 1 - gate];  // 多チャンネル拡大

    // 2系統のPlayBuf + エンベロープ
    var sigs = PlayBuf.ar(1, b, BufRateScale.kr(b),
        T2A.ar(trig) * gates,
        LFNoise0.kr(0) * b.numFrames,
        1) * EnvGen.ar(Env.asr(0.005, 1, 0.005), gates);

    sigs[0] + sigs[1];
}.play;
```

### ディレイラインによるリピーター（ピッチドリフトなし）

```supercollider
// Changed.kr + Demand.ar でピッチ変化を排除したクリーンなリピート
{
    var sig = SoundIn.ar(0);
    var buf = LocalBuf(s.sampleRate * 2);
    var deltime = MouseX.kr(0.05, 0.5);

    // ポイント：Demand.ar でディレイタイムを瞬間切替（補間なし）
    var deltaA = Demand.ar(T2A.ar(Changed.kr(deltime)), 0, deltime);

    var write = BufWr.ar(sig, buf, Phasor.ar(0, 1, 0, BufFrames.kr(buf)));
    BufRd.ar(1, buf,
        Phasor.ar(0, 1, 0, BufFrames.kr(buf)) - (deltaA * s.sampleRate)
    );
}.play;
```

---

## 2. 確率的合成：Gendyファミリー（最重要グリッチ素材）

ヤニス・クセナキスの動的確率合成。波形の各制御点をランダムウォークさせて音響生成。

### UGen比較

| UGen | 合成の論理 | 音響的特徴 |
|------|-----------|-----------|
| `Gendy1` | 周期と振幅が同時ランダムウォーク | 極めて不安定なピッチ・強いジッター |
| `Gendy2` | Lehmer乱数生成器パラメータ操作可能 | 周期的パターン＋ランダム性の混在 |
| `Gendy3` | 持続時間正規化・指定周波数で発振強制 | 音程感を保ちつつ振幅のグリッチ |

### 確率分布による質感制御

```supercollider
// ampdist / durdist の引数
// 0=LINEAR, 1=CAUCHY, 2=LOGIST, 3=HYPERBCOS, 4=ARCSINE, 5=EXPON, 6=SINUS

// Alva Noto的：CAUCHYで予測不可能な大ジャンプ
Gendy1.ar(ampdist: 1, durdist: 1, adparam: 1.0, ddparam: 1.0,
          minfreq: 20, maxfreq: 1000, ampscale: 0.5)

// 池田良二的：EXPONで鋭い立ち上がりのパーカッシブなグリッチ
Gendy1.ar(ampdist: 5, durdist: 5, initCPs: 2, knum: 2,
          minfreq: 100, maxfreq: 8000, ampscale: 0.3)

// 「デジタルの叫び」：initCPs=1で最もカオスに
Gendy1.ar(initCPs: 1, knum: 1, minfreq: 20, maxfreq: 20000, ampscale: 0.2)
```

---

## 3. デジタル信号劣化

### ビットクラッシュ（量子化ノイズ）

数学的プロセス：`x_quantized = round(x * 2^(bits-1)) * 2^(-(bits-1))`

```supercollider
// 正確な実装
var bits = 4;  // 4ビット = 激しい歪み
var quantized = sig.round(2 ** (1 - bits));

// より簡略な実装
var crushed = (sig * (2 ** bits)).round / (2 ** bits);
```

**ビット数の音響効果：**
- 16 bit → ほぼ原音
- 8 bit → ヴィンテージデジタル質感
- 4 bit → 激しい歪み・量子化ノイズが支配的
- 1 bit → 矩形波に近い（1か-1しかない）

### ダウンサンプリング（エイリアシング）

```supercollider
// Latch.ar でサンプルレートを意図的に下げる
var resampleRate = MouseX.kr(100, 44100);
var crushed = Latch.ar(sig, Impulse.ar(resampleRate));
// → ナイキスト超の成分が可聴帯域に「折り返し」→ 金属的エイリアシングノイズ
```

---

## 4. 需要レート（Demand-rate）UGenによるアルゴリズム制御

### CoinGate：確率的リズム生成

```supercollider
// スパースなクリック（Alva Noto的）
{
    var trig = Impulse.ar(20);
    var gate = CoinGate.ar(0.05, trig);  // 5%の確率で通過
    Ringz.ar(gate, 3000, 0.01);  // 高周波共振で「デジタルの粒」
}.play;

// 高密度グリッチバースト
{
    var trig = CoinGate.ar(0.3, Impulse.ar(100));
    Ringz.ar(trig, [1200, 2400, 4800], 0.005).sum;
}.play;
```

### Demand/Duty：構造的グリッチシーケンス

```supercollider
// リズム構造を持つグリッチ（単なるカオスでない）
{
    // Dseqで持続時間を定義、Dwhiteで周波数をランダム選択
    var trig = Duty.ar(
        Dseq([0.1, 0.05, 0.2, 0.01], inf),  // リズム構造
        0,
        Dwhite(100, 2000, inf)               // 周波数のランダム選択
    );
    Ringz.ar(T2A.ar(trig), trig, 0.02);
}.play;

// DemandEnvGen：不規則なエンベロープで「グリッチグルーヴ」
{
    var sig = Saw.ar(110);
    var env = DemandEnvGen.ar(
        Dwhite(0.0, 1.0),        // ランダムレベル
        Dwhite(0.001, 0.1),      // ランダム持続時間
        Dseq([1, 2, 4], inf)     // エンベロープ形状
    );
    sig * env;
}.play;
```

---

## 5. スペクトル領域グリッチ（FFT/PV系）

```supercollider
| UGen | 動作 | 音響的効果 |
|------|------|-----------|
| PV_BinScramble | 周波数ビンをシャッフル | 調波構造を破壊→金属的ノイズ |
| PV_RandComb | ランダムにビンを間引く | 信号の密度を削ぎ落とす・中空な質感 |
| PV_MagFreeze | 振幅スペクトルを凍結 | 時間停止感・スタティックな持続音 |
| PV_BrickWall | 帯域を完全にカット | デジタルな歪み |

// 例：スペクトル破壊
{
    var sig = SoundIn.ar(0);
    var chain = FFT(LocalBuf(2048), sig);
    chain = PV_BinScramble(chain, 0.5, 0.1);  // 50%のビンをシャッフル
    chain = PV_RandComb(chain, 0.4, Impulse.kr(2));
    IFFT(chain);
}.play;
```

---

## 6. 実装上の注意点

### LocalBufの活用
- リアルタイムリピーター・FFT処理には `LocalBuf` でSynthDef内にカプセル化
- グローバル `Buffer.alloc` より効率的

### オーディオレート駆動
- グリッチの鋭さのためモジュレーターはARで動かす（KRでは粗すぎる）

### 安全性の確保
```supercollider
// シグナルパスの最終段に必ずLimiter
sig = Limiter.ar(sig, 0.95, 0.01);
// またはソフトクリッピング
sig = sig.tanh;
```

---

## MaToMaへの実装指針

**多層グリッチ設計（推奨）：**

```
Layer A: Gendy確率ノイズ（素材層） → 最もグリッチ的な素材
Layer B: バッファスタッター（時間破壊） → 音の断片化
Layer C: ビットクラッシュ + Latch（信号劣化） → デジタル質感
Layer D: CoinGate + Ringz（確率的リズム） → 構造的グリッチ
Layer E: PV_RandComb / PV_BinScramble（周波数破壊） → スペクトルグリッチ

制御パラメーター：
- density (0〜1): CoinGateの確率 → グリッチの頻度
- intensity (0〜1): 各レイヤーの強度
- mode (0〜4): 主要な技法の選択
- mix (0〜1): dry/wet
```
