---
title: SuperCollider 拡張ライブラリ（Quarks）ガイド
category: plugin
tags: [quarks, plugin, extension, miSCellaneous, Fb1, nonlinear, chaos, DX, wavefolding, dewdrop]
---

## SuperCollider 拡張ライブラリ（Quarks）

Quarks は SuperCollider のパッケージマネージャ。

```supercollider
// Quark一覧をGUIで確認
Quarks.gui;

// 個別インストール
Quarks.install("名前");
s.reboot; // 再起動で有効化
```

---

## 1. miSCellaneous_lib（dkmayer製）

**非線形サウンド・パターン拡張の宝庫。** Autechreスタイルの「制御されたカオス」に直結する。

```supercollider
Quarks.install("miSCellaneous_lib");
```

### 1-1. Fb1 — 非線形ODEフィードバック合成

**カオス性・非線形性を SC で直接実装するための中心クラス。**
ローレンツアトラクター、ヴァン・デル・ポル振動子など有名な力学系が使える。

```supercollider
// ローレンツアトラクター（カオス音響）
{
    var sig = Fb1_Lorenz.ar(
        tMul: 10,      // 時間スケール（速さ）
        // σ=10, ρ=28, β=8/3 がクラシックなカオスパラメーター
        s: 10, r: 28, b: 2.667,
        h: 0.01,       // 積分ステップ（小さいほど安定）
        x0: 0.1, y0: 0, z0: 0  // 初期値
    );
    // x, y, z の3成分を出力。x をオーディオ信号として使う
    sig[0] ! 2 * 0.3
}.play;
```

```supercollider
// ヴァン・デル・ポル振動子（自己振動・非線形）
{
    var mu = MouseX.kr(0.1, 5).poll; // μ=0: 線形, μ大: 非線形/カオス
    var sig = Fb1_VanDerPol.ar(tMul: 200, mu: mu, h: 0.005);
    sig[0] ! 2 * 0.3
}.play;
```

```supercollider
// ダッフィング振動子（混沌と秩序の境界）
{
    var sig = Fb1_Duffing.ar(
        tMul: 100,
        alpha: -1, beta: 1, delta: 0.3, gamma: 0.5, omega: 1.2
    );
    sig[0] ! 2 * 0.2
}.play;
```

#### Fb1 系クラス一覧

| クラス | 力学系 | 音のキャラクター |
|-------|--------|----------------|
| `Fb1_Lorenz` | ローレンツアトラクター | 典型的カオス：予測不能な揺らぎ |
| `Fb1_VanDerPol` | ヴァン・デル・ポル振動子 | 自己振動・非線形倍音 |
| `Fb1_Duffing` | ダッフィング振動子 | カオスと周期の境界 |
| `Fb1_Hopf` | ホップ分岐 | 安定→振動の相転移 |
| `Fb1_SD` | ショウ・ドゥアーン系 | ストレンジアトラクター |
| `Fb1_MSD` | 質量-バネ-ダンパー | 物理的な共鳴 |
| `Fb1_ODE` | 汎用ODE（自分で定義） | 任意の微分方程式 |

### 1-2. DXスイート — クロスフェード・ルーティング

複数シンセ間の動的なクロスフェード・パンニングを制御。

```supercollider
// DXFan: 1入力を複数出力にクロスフェードで分配
{
    var sig = SinOsc.ar(300);
    var pos = LFSaw.kr(0.2).range(0, 3); // 0→1→2→3 へゆっくり移動
    DXFan.ar(sig, pos, size: 4) // 4チャンネルに分配
}.play;
```

```supercollider
// DXMix: 複数入力を1出力にクロスフェードでミックス
{
    var sigs = [SinOsc.ar(200), SawOsc.ar(200), WhiteNoise.ar(0.5)];
    var pos  = LFNoise1.kr(0.1).range(0, 2);
    DXMix.ar(0, \default, pos, sigs)
}.play;
```

### 1-3. WaveFolding — ウェーブフォルディング

波形を折り返す歪み。倍音の複雑な追加に。

```supercollider
// WaveFolding
{
    var sig = SinOsc.ar(220) * MouseX.kr(1, 8); // ドライブ量
    var folded = (sig * 0.25).fold(-1, 1); // 基本的なフォールド
    folded ! 2
}.play;
```

### 1-4. PLxスイート — ライブコーディングパターン

`Pdef` の動的置換に対応した `Pbind` 互換パターン群。

```supercollider
// PLseq: ライブ中に値をリアルタイム差し替え可能なシーケンス
(
p = Pbind(
    \instrument, \default,
    \degree, PLseq(\degs),   // ~degs の配列を参照
    \dur, 0.25
).play;
~degs = [0, 2, 4, 7];  // 実行中に変更可能
)
~degs = [0, 3, 5, 10]; // 即時反映
```

---

## 2. sc3-plugins（公式コミュニティプラグイン集）

SuperCollider の公式拡張 UGen 集。インストール後に多数の UGen が追加される。

```supercollider
// Homebrewでインストール（macOS）
// brew install sc3-plugins
// または SC アプリ同梱版を使う
```

主要な追加 UGen：

| UGen | 用途 |
|------|------|
| `RLPFD` | 共鳴LPFのフィードバック制御版 |
| `MoogFF` | Moogフィルターのデジタル実装 |
| `AnalogFoldOsc` | アナログ的なウェーブフォールド発振器 |
| `AY` | AY-3-8910チップエミュレーター（8bitサウンド） |
| `Lorenz` | ローレンツアトラクター（sc3-plugins版） |
| `HenonC` | エノン写像（カオスマップ） |
| `LatoocarfianC` | ラトゥーカルフィアンアトラクター |

```supercollider
// MoogFFフィルターの例
{
    var sig = Saw.ar(80, 0.5);
    var cutoff = LFNoise1.kr(0.3).exprange(200, 8000);
    MoogFF.ar(sig, cutoff, gain: 3.5) ! 2
}.play;
```

---

## 3. dewdrop_lib（H. James Harkins製）

ライブパフォーマンス向けの SC 拡張。プロセス管理・エフェクト定義。

```supercollider
Quarks.install("dewdrop_lib");
```

### Instr クラス — 引数を動的に設定できるシンセ定義

```supercollider
// Instr: チャンネル数をランタイムで決定できる柔軟なSynthDef
Instr(\reverb, { |in, mix = 0.3, room = 0.8|
    var sig = In.ar(in, 2);
    XFade2.ar(sig, FreeVerb.ar(sig, 1.0, room), mix * 2 - 1)
});

// 実行
Patch(\reverb, [0, 0.4, 0.7]).play;
```

### MixerChannel — チャンネルストリップ

```supercollider
// 4チャンネルのミキサーを作成
m = MixerChannel(\main, s, 2, 2);
m.newPostSend(\reverb, 0.3);  // センドエフェクト
m.play(Synth(\mySynth));
```

---

## インストール確認

```supercollider
// インストール済みQuarksの一覧
Quarks.installed.do { |q| q.name.postln };

// 特定クラスの存在確認
FluidSpectralShape.respondsTo(\kr) // FluCoMaが入っているか
Fb1_Lorenz.respondsTo(\ar)         // miSCellaneous_libが入っているか
```
