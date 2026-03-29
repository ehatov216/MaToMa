---
title: DAW・ワークステーション連携（SuperCollider + 外部ソフト）
category: workstation
tags: [ossia, bespoke, DAW, OSC, MIDI, timeline, integration, workstation]
---

## SuperCollider と外部DAW/ワークステーションの連携

MaToMaのコアパイプライン：

```
SuperCollider ──OSC──→ Python Bridge ──WebSocket──→ Browser GUI
                └──OSC──→ 映像ソフト（TouchDesigner / Hydra）
```

外部DAW・ワークステーションとの接合点は **OSC と MIDI** で統一する。

---

## 1. Ossia Score — タイムライン＋OSCオートメーション

**ossia score** はオープンソースの非線形タイムライン・パッチング環境。
SuperCollider / Max / Pd / TouchDesigner と OSC で直接通信できる。

公式サイト: https://ossia.io

### SC側：OSCサーバーを立てる

```supercollider
// SC で OSCdef を登録して Ossia からの信号を受ける
OSCdef(\ossiaControl, { |msg, time, addr, recvPort|
    var cutoff = msg[1];
    var amp    = msg[2];
    Synth.set(\mySynth, \cutoff, cutoff, \amp, amp);
}, '/matoma/control');

// ポート確認
NetAddr.langPort.postln; // デフォルト 57120
```

### Ossia側の設定

```
Device Explorer → Add Device → OSC
  Host: localhost (127.0.0.1)
  Output port: 57120  ← SC の受信ポート
  Input port:  57121  ← SC から Ossia への送信先（任意）

OSC アドレス例:
  /matoma/control [cutoff: float, amp: float]
  /matoma/scene   [id: int]
  /matoma/random  [seed: float]
```

### CLI（ヘッドレス）起動

```bash
# GUI なしでバックグラウンド実行（映像インスタレーション向け）
ossia-score --no-gui --autoplay /path/to/my-score.score
```

### OSCQuery — 自動パラメーター探索

Ossia は **OSCQuery** プロトコルをサポート。SC 側で OSCQuery サーバーを立てると、
Ossia が自動でパラメーターの名前・型・レンジを検出する。

```supercollider
// OSCQueryServer（Quarkが必要）
OSCQueryServer.new(8080, NetAddr.langPort);
```

---

## 2. Bespoke Synth — モジュラーソフトウェアシンセ

**Bespoke Synth** はモジュラー式ソフトウェアシンセ。OSC と MIDI で SC と連携可能。

- シーケンサー種類: EuclideanSequencer, M185Sequencer, NoteSequencer, NoteCanvas...
- エフェクト: Reverb, Chorus, Bitcrush, Resonator, Ring Modulator...
- Python スクリプティングをサポート

```supercollider
// Bespoke から SC への MIDI 送信を受ける
MIDIClient.init;
MIDIdef.noteOn(\bespokeNote, { |vel, note, chan|
    Synth(\mySynth, [\freq, note.midicps, \amp, vel/127]);
});

// SC から Bespoke への OSC 送信
~bespoke = NetAddr("127.0.0.1", 8000); // Bespoke の OSC ポート
~bespoke.sendMsg('/bespoke/tempocontrol/tempo', 140);
```

---

## 3. SuperCollider ← → TouchDesigner（OSC）

MaToMaの映像連携。SC から OSC でパラメーターを送る。

```supercollider
// TouchDesigner への送信（デフォルトポート 7000）
~td = NetAddr("127.0.0.1", 7000);

// フレームごとに解析値を送信
{
    var sig     = SoundIn.ar(0);
    var shape   = FluidSpectralShape.kr(sig);
    var centroid = shape[0];
    var flatness = shape[5];

    SendReply.kr(Impulse.kr(30), '/td/audio', [centroid, flatness]);
    sig
}.play;

OSCdef(\toTD, { |msg|
    ~td.sendMsg('/audio/centroid', msg[3]);
    ~td.sendMsg('/audio/flatness', msg[4]);
}, '/td/audio');
```

---

## 4. VCV Rack — バーチャルモジュラーシンセ

**VCV Rack** はオープンソースのバーチャルユーロラックシステム。
SC と VCV Rack を組み合わせる方法：

### MIDI経由
```supercollider
// SC → VCV の MIDI CC でパラメーター制御
MIDIClient.init;
~vcvOut = MIDIOut.newByName("VCV Rack", "VCV Rack");
~vcvOut.control(0, 74, (cutoff * 127).asInteger); // CC74 = カットオフ
```

### OSC Bridge（VCV-OSC モジュール使用）
```supercollider
~vcv = NetAddr("127.0.0.1", 7001); // VCV OSC Bridge のポート
~vcv.sendMsg('/vcv/voltage/1', 0.5); // モジュールの入力に電圧を送る
```

---

## 5. SC 内部での DAW的タイムライン設計

外部DAWを使わず、SC 内部でシーン切り替えを管理する MaToMa の方式。

```supercollider
// シーンの定義（MaToMa方式）
~scenes = Dictionary.newFrom([
    \scene_ambient, (
        synth: \sa_ambient_drone,
        params: (freq: 55, amp: 0.3, reverb: 0.8)
    ),
    \scene_glitch, (
        synth: \sa_granular_drone,
        params: (grain_rate: 40, noise_level: 0.7)
    )
]);

// シーン切り替え（クロスフェード付き）
~switchScene = { |fromKey, toKey, xfadeTime = 4|
    var fromScene = ~scenes[fromKey];
    var toScene   = ~scenes[toKey];
    // フェードアウト → フェードイン
    fromScene[\node].set(\gate, 0);
    SystemClock.sched(xfadeTime, {
        ~currentNode = Synth(toScene[\synth], toScene[\params].asPairs);
    });
};
```

---

## OSCポート番号の慣例

| ソフト | 受信ポート（デフォルト） |
|--------|------------------------|
| SuperCollider (sclang) | 57120 |
| SuperCollider (scsynth) | 57110 |
| TouchDesigner | 7000（設定による） |
| Hydra | なし（ブラウザ内） |
| VCV Rack OSC Bridge | 7001（モジュールによる） |
| ossia score | 5678（OSCQuery）|
| Bespoke Synth | 8000 |
