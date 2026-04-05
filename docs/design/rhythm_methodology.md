# MaToMa リズム方法論

> 作成: 2026-03-31
> 目的: 今後のリズム実装における設計思想・技術的方針の統合文書

---

## 【設計決定】TidalCyclesがクロックのオーナー

> 2026-03-31 確定。この方針を変える場合は必ず理由を記録すること。

```
TidalCycles: クロックを持つ。全タイミングを決定する。
             パターン構造・ms単位のnudge・数学的配置すべてここで行う。

SuperCollider: 音の合成のみ。Tidalから来たOSCに従って鳴らすだけ。
               ただし音色のLFO・カオス・呼吸的密度変動はSC内部で完結してよい。
               （これらはタイミング制御ではなく「音の質感」の制御であるため）
```

**この設計を選んだ理由：**
- TidalのみでAlva Noto的なms単位のずらし（`nudge`）が実現できる
- 2クロック構造（Tidal + SC両方がタイミングを決める）は不安定になりやすい
- まず小さく試して、限界を感じたときに再検討する

**OPN的呼吸リズムの扱い：**
- 「いつトリガーするか」→ Tidalが決める
- 「トリガーされた音がどう呼吸するか（密度・質感の変動）」→ SC内部のLFO/Dustが担う
- 後者はタイミング制御ではなく音色制御なので、クロックの衝突は起きない

---

## 0. 前提：ここまでは「音の原子」を作っていた

MaToMaの音響設計には2段階ある。

```
Phase A（音粒製造）: 精密な音の素材をまず作る
                   → ドローン・グラニュラー・グリッチの音質を磨く
                   → 「音のレゴブロック」を完成させる工程

Phase B（リズム構築）: 完成した音粒を時間軸にどう配置するか
                   → この文書の主題
```

**音粒の完成度がリズムの精度を決める。** 素材が雑だと配置の精密さが死ぬ。

---

## 1. BPMという概念はMaToMaでは使わない

BPMは「人間が踊るための座標系」。MaToMaが扱うのは踊らないための時間。

参照するアーティストたちはそれぞれBPMから別の方法で逃げている：

```
Alva Noto: 1/192拍子の数学的細分割・フィボナッチ列・位相差
           → 「グリッドは使うが、BPMに縛られない」

OPN:       LFO周期（0.05〜0.1Hz = 10〜20秒）による呼吸
           → 「ビートという概念ごと消す」
```

### MaToMaでの適切な時間の単位

| 概念 | 単位 | 例 |
|------|------|----|
| 呼吸・マクロ周期 | 秒・Hz | `LFO 0.08Hz` = 12.5秒周期 |
| 音粒の出現タイミング | 比率・分数 | フィボナッチ列の番目 |
| 偶発的な打突 | 確率・密度 | `Dust.ar(0.1)` = 平均0.1回/秒 |

**問い方を変える：**
- ❌ 「この音は何BPMか？」
- ✅ 「この音の呼吸周期は何秒か？」
- ✅ 「どの数学的比率で配置されているか？」
- ✅ 「1秒あたり平均何回打突するか？」

---

## 2. 二大哲学：数学的骨格（Alva Noto）× 呼吸的筋肉（OPN）

```
Alva Noto: 数学的法則 → 「決定論的複雑さ」（骨格）
           冷たく精密。複合するとカオスになる。

OPN:       呼吸LFO   → 「確率的生物性」（筋肉）
           温かく不規則。でも必ず吸って吐く大きな波がある。
```

この2つは対立ではなく**組み合わせるもの**。

> TidalCyclesでAlva Notoの数学的骨格を、SuperColliderでOPNの呼吸的筋肉を被せる

---

## 3. Alva Noto：数学的骨格の作り方

### 原則：決定論的複雑さ

法則は明快だが、複合すると人間には予測できない複雑さが生まれる。「予測可能で予測不能」。

### 4つの技法

**1. フィボナッチ列による密度配置**

```supercollider
// 1, 1, 2, 3, 5, 8, 13... 番目のグリッドに音粒を置く
var fib = [1, 1, 2, 3, 5, 8, 13, 21, 34];
var grid = 192; // 1拍を192分割
Pbind(
    \dur, Pseq(fib.collect(_ / grid), inf),
    \instrument, \alva_click
).play;
```

**2. データ変換テーブル（MIDIノート → グリッド位置）**

```supercollider
// MIDIノート番号を時間位置に変換
// C3(48)=1/192, D3(50)=3/192, E3(52)=7/192 ...
var noteToGrid = { |note| (note - 48) / 192 };
```

**3. 位相差リズム（同一音粒を複数位相で同時再生）**

```supercollider
// 同じ音粒を8つの位相でずらして同時発火 → 複雑な干渉
8.do { |i|
    var phase = i / 8;
    {
        var env = EnvGen.ar(Env.perc(0.001, 0.01), doneAction: 2);
        SinOsc.ar(880, phase * 2pi) * env * 0.1
    }.play;
};
```

**4. 多重非同期グリッド**

```supercollider
// 公倍数が極めて長い = 実質的に繰り返さないパターン
// グリッド1: 13/72拍子
// グリッド2: 27/128拍子
// グリッド3: 41/192拍子
var clocks = [72, 128, 192].collect { |div|
    TempoClock.new(div / 60) // 各自独立したクロック
};
```

### Alva Noto SCコードの骨格

```supercollider
SynthDef(\alva_click, {
    arg freq = 1000, amp = 0.3, dur = 0.002;
    var env = EnvGen.ar(Env.perc(0.0001, dur), doneAction: 2);
    var sig = SinOsc.ar(freq) * env;
    // ビットクラッシュでデジタルノイズ化
    sig = (sig * 16).round / 16;
    Out.ar(0, sig ! 2 * amp);
}).add;
```

---

## 4. OPN：呼吸的筋肉の作り方

### 原則：確率的生物性

生き物の律動がリズムになる。心臓の拍動や呼吸のような「有機的な周期」が先にあって、音粒はその波に乗って揺れる。「予測不能だが予測可能」。

### 3つの技法

**1. 密度呼吸（LFO駆動）**

```supercollider
// トリガー密度がLFOで呼吸する
// 約10〜20秒周期で粒の発生頻度が4〜12に変動
var breathRate = 0.08; // Hz = 12.5秒周期
var density = LFPulse.ar(breathRate).range(4, 12);
var trig = Dust.ar(density);

// 効果：「吸気（粒密集）→ 呼気（粒希薄）」の波
```

**2. 吸引・排出エンベロプ（空間の呼吸）**

```supercollider
var breath = SinOsc.ar(0.08).range(0, 1); // 0=呼気, 1=吸気

// 吸引フェーズ: フィルタが閉じ、音が内側に引っ込む
var cutoff = breath.linexp(0, 1, 800, 200);
var sig = RLPF.ar(source, cutoff, 0.3);

// 排出フェーズ: 空間が広がる
var reverb = FreeVerb.ar(sig, mix: 1 - breath * 0.8, room: 0.9);
```

**3. 半意識的打突（条件付きDust）**

```supercollider
// 呼吸が閾値を超えたときだけ偶発的にクリックが入る
// 「深夜に突然意識が戻る」感覚
var breath = SinOsc.ar(0.08).range(0, 1);
var awakening = Select.ar(breath > 0.7, [0, Dust.ar(0.1)]);
```

### OPN SCコードの骨格

```supercollider
SynthDef(\opn_breath, {
    arg amp = 0.4, breathHz = 0.08;
    var breath = SinOsc.ar(breathHz).range(0, 1);
    var density = LFPulse.ar(breathHz).range(3, 10);
    var trig = Dust.ar(density);
    var grain = GrainSin.ar(2, trig, 0.1 + (breath * 0.15), 200 + (breath * 300));
    var wet = FreeVerb2.ar(grain[0], grain[1], mix: 0.6, room: 0.8 + (breath * 0.15));
    Out.ar(0, wet * amp);
}).add;
```

---

## 5. 秩序と無秩序の行き来

これがMaToMaのリズム設計の核心。

```
秩序（骨格）                     無秩序（筋肉）
    │                                │
    ▼                                ▼
数学的グリッド               確率・LFO・呼吸
フィボナッチ配置             Dust・ランダム密度
位相差の重ね                 半意識的打突
    │                                │
    └──────────┬───────────┘
               │
               ▼
        MaToMaのリズム
    「予測可能で予測不能」
    「予測不能だが予測可能」
```

### 行き来のコントロール設計

```supercollider
// order_chaos: 0.0 = 完全秩序（数学的）/ 1.0 = 完全無秩序（呼吸的）
var order_chaos = \order_chaos.kr(0.5);

// 秩序側: フィボナッチトリガー
var fib_trig = /* 上記フィボナッチ実装 */;

// 無秩序側: 呼吸トリガー
var breath_trig = /* 上記呼吸実装 */;

// 混合
var trig = SelectX.ar(order_chaos, [fib_trig, breath_trig]);
```

### 具体的なシーン設計案

| シーン名 | order_chaos値 | 説明 |
|---------|--------------|------|
| CRYSTALLINE | 0.0〜0.2 | 数学的グリッドが支配。冷たく精密。|
| BREATHING | 0.4〜0.6 | 両者が混合。緊張と弛緩が共存。|
| ORGANIC | 0.8〜1.0 | 呼吸が支配。温かく不規則。|
| COLLAPSE | 動的に変化 | 秩序から無秩序へ崩壊していく。|

---

## 6. MaToMaでの実装方針

### 優先順位

| 優先 | 実装項目 | 対応技法 |
|------|---------|---------|
| 🔴 高 | Dustベースの呼吸リズム基盤 | OPN：密度呼吸 |
| 🔴 高 | フィボナッチ列トリガー | Alva Noto：数学的配置 |
| 🟡 中 | order_chaosパラメーター（0〜1で行き来） | 秩序↔無秩序の混合 |
| 🟡 中 | 多重非同期グリッド（3クロック） | Alva Noto：位相差 |
| 🟢 低 | 条件付き打突（覚醒演出） | OPN：半意識的打突 |

### 変数命名規則

```supercollider
// BPMを連想する変数名は使わない
// ❌ tempo, bpm, beats_per_bar
// ✅ breathHz, density, period, ratio, phase

var breathHz = 0.08;      // 呼吸の周期（Hz）
var grainDensity = 8;     // 粒の密度（個/秒）
var mathRatio = 1/192;    // 数学的配置の比率
var orderChaos = 0.5;     // 秩序↔無秩序（0〜1）
```

### 参照すべきRAGファイル

実装前に必ず読むファイル：

| 意図 | ファイル |
|------|---------|
| リズム哲学（Alva Noto） | `artist_alvanoto_aesthetics.md` |
| リズム哲学（OPN） | `artist_opn_aesthetics.md` |
| 確率制御・Dust・ポアソン | `design_probability_control.md` |
| ユークリッドリズム・ライブコーディング | `sc_livecoding_techniques.md` |
| Pbind・パターンクラス | `sc_pattern_system.md` |
| リアルタイム制御・Lag | `sc_realtime_control.md` |

---

## 7. 設計の核心（一行要約）

> **数学が骨格を作り、呼吸が肉付けし、その行き来がライブを作る。**
