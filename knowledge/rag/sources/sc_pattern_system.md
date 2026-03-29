---
title: SuperCollider パターンシステム — Pbind / Pdef / Ndef
category: reference
tags: [Pbind, Pdef, Ndef, Pattern, ProxySpace, livecoding, sequence, Pseq, Prand, Pwhite, Pbrown]
---

## SuperCollider パターンシステム

Tidalを使わず、SC単体でシーケンスを組む仕組み。
ライブコーディングの核。ProxySpaceと組み合わせてリアルタイムに書き換えられる。

---

### 1. Pbind — 基本のパターン再生

```supercollider
// 基本形：\instrument（SynthDef名）と各パラメーターをパターンで指定
Pbind(
    \instrument, \default,      // SynthDef名
    \freq,  Pseq([220, 330, 440, 550], inf),  // 周波数を順番に
    \dur,   0.25,               // 音符の長さ（拍）
    \amp,   0.3
).play;
```

#### よく使うキー

| キー | 意味 |
|-----|------|
| `\instrument` | SynthDef名 |
| `\freq` | 周波数（Hz）|
| `\note` | MIDI風ノート（60=C4）|
| `\degree` | スケール上の音度（0=root）|
| `\scale` | スケール（`Scale.minor`等）|
| `\octave` | オクターブ（デフォルト5）|
| `\dur` | 音符の長さ（拍単位、1=1拍）|
| `\amp` | 音量（0〜1）|
| `\pan` | パン（-1〜+1）|
| `\legato` | ゲートの長さ（1=durと同じ）|
| `\sustain` | サステイン時間（秒）|
| `\out` | 出力バス番号 |

---

### 2. Pdef — 名前付きパターン（ライブ差し替え可能）

```supercollider
// Pdef で名前を付けると演奏中に差し替えられる
Pdef(\bass, Pbind(
    \instrument, \default,
    \degree, Pseq([0, 0, 7, 5], inf),
    \octave, 3,
    \dur, 0.5,
    \amp, 0.4
)).play;

// 演奏中に内容を差し替え（次のサイクルから変わる）
Pdef(\bass, Pbind(
    \instrument, \default,
    \degree, Pseq([0, 3, 5, 7, 10], inf),
    \octave, 3,
    \dur, 0.25,
    \amp, 0.5
));

// 停止
Pdef(\bass).stop;
```

---

### 3. Ndef — ライブコーディング用ノードプロキシ

Ndef は Pdef とは異なり、シンセ関数もパターンも受け付け、**クロスフェードで切り替え**られる。

```supercollider
// 起動
Ndef(\a).play;
Ndef(\a).fadeTime = 2;   // クロスフェード時間

// シンセ関数を割り当て（差し替え可能）
Ndef(\a, { SinOsc.ar([350, 351.3], 0, 0.2) });
Ndef(\a, { Pulse.ar([350, 353], 0.4, 0.2) });   // クロスフェードで切り替わる

// Pbind も受け付ける
Ndef(\a, Pbind(\dur, 0.1, \freq, Pbrown(200, 400, 10, inf)));

// 別の Ndef から入力を取る（ルーティング）
Ndef(\reverb, { FreeVerb.ar(Ndef.ar(\dry), 0.5, 0.8) });

// 全停止
Ndef.clear(3);   // 3秒かけて全停止
```

---

### 4. パターンクラス一覧

#### シーケンス系
```supercollider
Pseq([1,2,3], inf)          // 順番に繰り返す（inf=無限）
Pser([1,2,3], 5)            // 順番に5回だけ
Pshuf([1,2,3], inf)         // シャッフルして繰り返す
Pslide([1,2,3,4], inf, 3, 1)// スライドウィンドウ
Place([[1,2],[3],[4,5]], inf)// ラウンドロビン
```

#### ランダム系
```supercollider
Prand([1,2,3], inf)         // ランダム選択（重複あり）
Pxrand([1,2,3], inf)        // ランダム選択（直前と重複なし）
Pwrand([1,2,3], [0.5,0.3,0.2], inf)  // 重み付きランダム
Pwhite(lo, hi, repeats)     // 均一分布ランダム
Pexprand(lo, hi, repeats)   // 指数分布ランダム（高い値が出やすい）
Pbrown(lo, hi, step, repeats)// ブラウン運動（前の値から少しずつ動く）
Pgauss(mean, dev, repeats)  // ガウス分布
```

#### 反復系
```supercollider
Pn(pat, repeats)            // パターンをN回繰り返す
Pstutter(n, pat)            // 各値をn回繰り返す
Pdrop(n, pat)               // 最初のn個を捨てる
Pfin(n, pat)                // n個で止める
```

#### 時間・デュレーション系
```supercollider
Pbjorklund2(k, n, length, offset)  // ユークリッドリズム（Bjorklundクオーク必要）
// k=hit数, n=総ステップ数 → dur配列を返す
// 例: Pbjorklund2(3,8)/4 → 8分音符3拍子を4分音符に正規化
```

#### 条件・変換系
```supercollider
Pif(condition, truePattern, falsePattern)   // 条件分岐
Pkey(\keyName)                              // 同じPbind内の他のキーを参照
Pfunc({ |ev| ev[\freq] * 2 })              // 関数で動的に値を計算
Plazy({ Pseq([1.0.rand, 2.0.rand], inf) }) // 遅延評価
```

---

### 5. ProxySpace — ライブコーディング環境

```supercollider
// ProxySpaceを起動（全グローバル変数~xxxをNodeProxyにする）
p = ProxySpace.push(s);
p.clock.tempo = 2.0;    // BPMを120に（2.0 = 120BPM）

// ~変数名でパターンを定義・再生
~kick = Pbind(\instrument, \default, \dur, 1, \freq, 80, \amp, 1);
~kick.play;

// ライブ中に差し替え（次のサイクルから変わる）
~kick = Pbind(\instrument, \default, \dur, 0.5, \freq, 80, \amp, 1);

// 停止
~kick.stop;

// ProxySpaceを終了
p.pop;
```

---

### 6. スケールと音程

```supercollider
// 組み込みスケール
Scale.minor       // ナチュラルマイナー
Scale.major       // メジャー
Scale.dorian      // ドリアン
Scale.phrygian    // フリジアン
Scale.chromatic   // 半音階（全12音）
Scale.directory   // 全スケール一覧を表示

// \degree で使う（0=ルート、7=オクターブ上のルート）
Pbind(\scale, Scale.minor, \degree, Pseq([0,2,3,5,7],inf), \octave, 4, \dur, 0.25).play;

// 複数の音を同時（コード）
Pbind(\degree, Pseq([[0,2,4],[3,5,7],[4,6,8]],inf), \dur, 1).play;

// ChordSymbol クオーク使用（コード名で指定）
Pbind(
    \scale, Scale.chromatic,
    \degree, Pseq([\Am7, \Em7, \Dm7, \G7].chordProg, inf),
    \dur, 2
).play;
```

---

### 7. Pkey — パターン内の値を参照

```supercollider
// \dur と同じ値を \sustain に使う
Pbind(
    \instrument, \default,
    \dur, Pwhite(0.1, 0.5),
    \sustain, Pkey(\dur),    // \dur と同じ値
    \freq, 440
).play;

// \rate から \pos を計算（逆再生時の開始位置）
Pbind(
    \instrument, \bplay,
    \rate, Prand([-1, 1], inf),
    \pos, Pkey(\rate).linlin(-1, 1, 0.99, 0),  // -1なら0.99、+1なら0
    \dur, 0.25
).play;
```

---

### 8. ライブコーディングの実践パターン（co34ptスタイル）

```supercollider
// BPMを設定してProxySpaceを起動
p = ProxySpace.push(s);
p.clock.tempo = 2.4;     // 144 BPM

// ユークリッドリズムでキック
~k = Pbind(\instrument, \default, \freq, 60, \amp, 1,
    \dur, Pbjorklund2(3, 8) / 4);
~k.play;

// 重み付きランダムでハイハット
~h = Pbind(\instrument, \default, \freq, 8000, \amp, 0.5,
    \dur, Pwrand([0.25, Pseq([0.125], 4), Pseq([0.25/3], 3)],
                 [0.6, 0.3, 0.1], inf));
~h.play;

// ランダムウォーク的なメロディ（Pbrown）
~mel = Pbind(\instrument, \default,
    \scale, Scale.minor,
    \degree, Pbrown(0, 7, 1, inf),
    \octave, Pwrand([4, 5], [0.7, 0.3], inf),
    \dur, Pwhite(0.125, 0.5).round(0.125),
    \amp, 0.4,
    \legato, 0.8);
~mel.play;

// normalizeSum で整数比のリズム
~hat = Pbind(\instrument, \default, \freq, 6000, \amp, 0.3,
    \dur, Pseq((1..16).normalizeSum, inf) * 4);
~hat.play;
```
