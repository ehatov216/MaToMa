---
title: ライブコーディング実践技法 — リズム・ピッチ・パターン（co34pt）
category: reference
tags: [livecoding, rhythm, euclidean, Pbjorklund2, Pwrand, ProxySpace, pitch, scale, co34pt, normalizeSum]
---

## ライブコーディング実践技法（co34ptスタイル）

ライブパフォーマンスで使われる、SCのリズム・ピッチ生成の実践ノウハウ。

---

### 1. ユークリッドリズム（Pbjorklund2）

「k個のヒットをn個のステップに均等配置する」アルゴリズム。
単純な数字の組み合わせから複雑なリズムが生まれる。

**インストール：**
```supercollider
Quarks.install("Bjorklund");
```

```supercollider
// 基本：Pbjorklund2(k, n) → dur配列を返す
// /4 で4分音符単位に正規化
Pbind(\dur, Pbjorklund2(3, 8) / 4).play;   // ← 3ヒット / 8ステップ = [3,3,2]/4

// kをランダムにして毎回違うリズムを生成
~k = Pbind(\instrument, \default, \freq, 60, \amp, 1,
    \dur, Pbjorklund2(Pwhite(1, 8), Pwhite(1, 16)) / 4);

// offsetでスタート位置をずらす（複数パターンの位相差）
// .asStream を付けるとoffsetでPwhiteが使えるようになる
~c1 = Pbind(\dur, Pbjorklund2(5, 16, inf, Pwhite(0, 8).asStream) / 4);
~c2 = Pbind(\dur, Pbjorklund2(5, 16, inf, Pwhite(1, 15).asStream) / 4, \rate, 1.1);
```

#### 収束と発散（ライブの核心技）

変数 `l` を使って全パターンを同じリズムに収束させ、その後バラバラにする：

```supercollider
// 発散：各パターンが独自のランダムリズムを持つ
l = Pbjorklund2(Pwhite(3, 10), 16) / 4;
(
~sn = Pbind(\instrument, \default, \freq, 400, \amp, 1, \dur, l);
~h  = Pbind(\instrument, \default, \freq, 6000, \amp, 0.6, \dur, l);
~mel = Pbind(\degree, Pwhite(-2, 5), \scale, Scale.minor, \dur, l, \amp, 0.4);
~sn.play; ~h.play; ~mel.play;
)

// 収束：一つの固定リズムに統一
l = Pbjorklund2(Pseq([3, 8, 2, 5, 9], inf), 16) / 4;
// 個別に評価するとバラバラになる（発散）
~sn = Pbind(\instrument, \default, \freq, 400, \amp, 1, \dur, Pbjorklund2(Pwhite(2, 8), 16) / 4);
```

---

### 2. Pwrand — 重み付きランダム

「一番出やすいもの・たまに出るもの」を制御できる、最も音楽的なランダム。

```supercollider
// トラップ系ハイハット：4分音符が多く、たまに8分音符になる
~h = Pbind(\instrument, \default, \freq, 8000, \amp, 0.6,
    \dur, Pwrand([
        0.25,               // 4分音符（60%）
        Pseq([0.125], 4),   // 8分音符×4（30%）
        Pseq([0.25/3], 3),  // 3連符（9%）
        Pseq([0.0625], 4)   // 16分音符×4（1%）
    ], [0.6, 0.3, 0.09, 0.01], inf));

// キックドラムに時々バリエーション
~k = Pbind(\dur,
    Pwrand([1, Pseq([0.75], 4), Pbjorklund2(3, 8, 1) / 4],
           [0.9, 0.08, 0.02], inf));
```

---

### 3. .normalizeSum — 整数比リズム

配列の要素が全部で1になるよう正規化。複雑なリズムを指定した拍数に収める。

```supercollider
// 1〜16の整数を16拍に均等に配置
~h = Pbind(\instrument, \default, \freq, 8000,
    \dur, Pseq((1..16).normalizeSum, inf) * 4,  // 16拍分
    \amp, Pwhite(0.2, 1));

// 1〜200で超高密度リズム（倍音的に聞こえる）
~h = Pbind(\dur, Pseq((1..200).normalizeSum, inf) * 16);

// 実用的な例：5〜10拍を8拍に収める
~mel = Pbind(\dur, Pseq((1..8).normalizeSum, inf) * 8);
```

---

### 4. .round — ランダムを拍に揃える

`Pwhite` をそのまま使うとビートと無関係な長さになる。`.round` で揃える。

```supercollider
// NG: 拍と無関係なランダム（ダンス音楽ではアウト）
~bad = Pbind(\dur, Pwhite(0.1, 0.5));

// OK: 8分音符単位に揃える
~ok  = Pbind(\dur, Pwhite(0.1, 0.5).round(0.125));

// 実用例：各パーツを適切な単位に揃える
(
~sn  = Pbind(\dur, Pwhite(1, 5.0).round(1));      // 全音符単位
~h   = Pbind(\dur, Pwhite(0.25, 0.75).round(0.25)); // 4分音符単位
~t   = Pbind(\dur, Pwhite(0.5, 2).round(0.5));     // 2分音符単位
)
```

---

### 5. レイヤリング技法

**「1つが良ければ、たくさんはもっと良い」（zimoun的思想）**

```supercollider
// 同じリズムを微妙に違うピッチで重ねる
(
p.clock.tempo = 2.3;
~k  = Pbind(\freq, 60,  \amp, 1, \dur, Pbjorklund2(3, 8) / 4);
~k2 = Pbind(\freq, 72,  \amp, 0.8, \dur, Pbjorklund2(3, 8) / 4, \rate, 1.2);
~k3 = Pbind(\freq, 48,  \amp, 0.6, \dur, Pbjorklund2(3, 16, inf, Pwhite(1, 8).asStream) / 4);
~k.play; ~k2.play; ~k3.play;
)

// 微妙に違う長さのリズムを重ねる（位相がずれていく）
(
~t  = Pbind(\dur, Pseq([1, 1, 1, 0.5], inf),  \amp, 1);
~t2 = Pbind(\dur, Pseq([1, 1, 1, 0.25], inf), \amp, 0.8, \rate, 1.1);
~t3 = Pbind(\dur, Pseq([1, 1, 1, 0.75], inf), \amp, 0.6, \rate, 0.9);
~t.play; ~t2.play; ~t3.play;
)
```

---

### 6. Prewrite — 確率的ツリーリズム

再帰的なリズム構造。ある値から別の値へ確率的に遷移する。

```supercollider
// Prewrite: 第1引数=開始値, 第2引数=遷移ルール, 第3引数=深さ
l = Prewrite(1,     // 1から始まる
    (1:  [0.25, 2],         // 1は確率的に0.25か2に
     0.25: [1, 0.75, 0.1],  // 0.25からの遷移
     0.1: [0.5, 1, 2],
     2:   [0.5, 0.75, 1]),
    4);                     // 深さ4

~h = Pbind(\dur, l / 2, \amp, 1);   // 速いバージョン
~c = Pbind(\dur, l * 2, \amp, 0.8); // 遅いバージョン
```

---

### 7. ピッチ配置の技法

#### スケールと \degree

```supercollider
// 基本：Scale.minor + degree（音度）で指定
Pbind(\scale, Scale.minor, \degree, Pseq([0, 2, 3, 5, 7], inf), \dur, 0.25).play;

// Pbrown でスケール上をランダムウォーク
Pbind(\scale, Scale.minor, \degree, Pbrown(0, 7, 1, inf), \dur, 0.25).play;

// Pwrand でコード優先（特定の音が出やすい）
Pbind(
    \scale, Scale.minor,
    \degree, Pwrand([0, 2, 3, 5, 7, 10], [0.3, 0.2, 0.2, 0.15, 0.1, 0.05], inf),
    \octave, Pwrand([4, 5], [0.7, 0.3], inf),
    \dur, Pbjorklund2(Pwhite(4, 8), 16) / 4
).play;
```

#### ピッチとリズムの連動（Pkey）

```supercollider
// リズムが変わるとピッチも変わる（連動）
~mel = Pbind(
    \scale, Scale.minor,
    \degree, Pwhite(0, 7),
    \dur, Pbjorklund2(Pwhite(3, 8), 16) / 4,
    \octave, Pwrand([3, 4, 5], [0.2, 0.6, 0.2], inf),
    \amp, Pexprand(0.1, 0.8)  // 指数分布で強弱をつける
);
```

#### 倍音列をピッチに使う

```supercollider
// 倍音列のスケール（より原始的な響き）
~harm = Pbind(
    \freq, Prand([1,2,3,4,5,6,7,8,9,10,11,12], inf) * 55,  // 55Hz(A1)の倍音
    \dur, Pbjorklund2(Pwhite(3, 8), 16) / 4,
    \amp, 0.3
);
```

---

### 8. ライブ中のクイックレシピ

```supercollider
// BPM設定
p.clock.tempo = 140/60;

// ユークリッドキック
~k = Pbind(\instrument, \default, \freq, 60, \amp, 2,
    \dur, Pbjorklund2(3, 8) / 4);

// 重み付きハイハット
~h = Pbind(\instrument, \default, \freq, 9000, \amp, Pexprand(0.2, 0.8),
    \dur, Pwrand([0.25, 0.125, 0.5], [0.5, 0.35, 0.15], inf));

// スケールランダムウォークメロディ
~m = Pbind(
    \scale, Scale.dorian,
    \degree, Pbrown(0, 9, 1, inf),
    \octave, Pwrand([4, 5], [0.6, 0.4], inf),
    \dur, Pwhite(0.125, 0.5).round(0.125),
    \amp, 0.35, \legato, 0.7);

// コード（長めのdur）
~c = Pbind(
    \scale, Scale.dorian,
    \degree, Pwrand([[0,2,4],[3,5,7],[5,7,9]], [0.5,0.3,0.2], inf),
    \octave, 3,
    \dur, Pwhite(3, 7).round(1),
    \amp, 0.3, \legato, 0.9);

~k.play; ~h.play; ~m.play; ~c.play;
```
