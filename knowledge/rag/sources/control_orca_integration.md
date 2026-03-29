---
title: Orca — 2Dグリッドライブコーディングと SC/Tidal 連携
category: workstation
tags: [orca, livecoding, MIDI, OSC, generative, grid, sequencer, non-linear]
---

## Orca（Hundred Rabbits）

2次元のASCIIグリッド上でオペレーターを配置し、信号（Bang）の衝突・移動で
MIDI/OSCメッセージを生成するライブコーディング環境。
**音源は持たない** — SuperCollider / TidalCycles / 外部シンセを「脳」から操る制御装置として使う。

公式: https://100r.co/site/orca.html

---

### 主要オペレーター（アルファベット = 演算子）

| 文字 | 名前 | 機能 |
|------|------|------|
| `D` | Delay | N フレームごとにBangを送る（クロック分周） |
| `R` | Random | 指定範囲のランダム値を出力 |
| `T` | Track | 左のシーケンスから値を読み取る（固定パターン） |
| `C` | Clock | 毎フレームインクリメントするカウンター |
| `I` | Increment | 値を1つずつ増やす |
| `J` | Jumper | 値を右に転送 |
| `F` | If | 2つの値が等しければBangを出力 |
| `B` | Bounce | 0〜maxの間を往復する |
| `E` | East | Bangを東へ移動させる |
| `S` | South | Bangを南へ移動させる |
| `*` | Bang | 隣接するオペレーターを起動する |
| `:` | MIDI | MIDIノートを送信 |
| `;` | UDP | OSCメッセージを送信 |

---

### Orca → SuperCollider 連携

#### 方法1: MIDI経由（最もシンプル）

```supercollider
// SC側：MIDIを受信してSynthを鳴らす
MIDIClient.init;
MIDIdef.noteOn(\orcaNote, { |vel, note, chan|
    Synth(\mySynth, [
        \freq, note.midicps,
        \amp, vel / 127,
        \gate, 1
    ]);
}, chan: 0);

MIDIdef.noteOff(\orcaOff, { |vel, note, chan|
    // ゲート制御（必要であれば）
}, chan: 0);
```

Orcaグリッド側：
```
. . . . . . . . . . . .
. D4 . . . . . . . . . .   ← 4フレームごとにBang
. . * . . . . . . . . .
. . :03C . . . . . . . .   ← ch0, vel3, C4(=MIDI60)を送信
```

#### 方法2: OSC経由（より柔軟）

```supercollider
// SC側：Orca からの UDP/OSC を受信
OSCdef(\orcaMsg, { |msg, time, addr|
    var note = msg[1];
    var vel  = msg[2];
    Synth(\mySynth, [\freq, note.midicps, \amp, vel / 127]);
}, '/orca/note');

// Orcaは ; オペレーターでUDPパケットを送信（localhost:49160がデフォルト）
```

---

### Orca → TidalCycles 連携

TidalとOrcaを組み合わせるには、Orcaで生成したMIDIをTidalに入力するか、
Tidalのパターンの中でOrcaが生成した値をOSCで受け取る。

```haskell
-- SC経由でOrcaのCCをTidalパラメーターに流す
-- SC側でMIDI CCを受けてOSCをTidalに送る
MIDIdef.cc(\orcaCC, { |val, num, chan|
    NetAddr("127.0.0.1", 57120).sendMsg('/ctrl', num, val / 127.0);
}, chan: 0);

-- Tidal側でコントロールバスとして受け取る
d1 $ s "supersaw*4" # cutoff (cF 1000 "74")  -- CC74 = cutoff
```

---

### Orcaでの生成的パターン例

```
チューリングマシン的な確率ループ：

. C . . . . . . . . .
. . T8 0 1 3 5 7 . .   ← 8ステップのシーケンス
. . . * . . . . . . .
. . . :03C . . . . .   ← MIDIノート送信

Rオペレーターでランダム変異：
. R8 . . . . . . . .   ← 0〜8のランダム値
. . J . . . . . . . .  ← 値を転送
. . . :03C . . . . .   ← ランダムなMIDIノート
```

---

### 設計思想：Orcaが示す「非線形制御」

- タイムラインなし → グリッドの状態がシーケンサー
- すべての処理がリアルタイム → 演奏中にオペレーターを書き換えると即反映
- シンプルなロジックの組み合わせ → 予測不能な複雑性が生まれる

**MaToMaでの活用イメージ：**
OrcaでMIDIトリガーやCC値を生成し、SCのOSCdefで受け取って
SynthDefのパラメーターをリアルタイムに変化させる「外部制御脳」として使う。
