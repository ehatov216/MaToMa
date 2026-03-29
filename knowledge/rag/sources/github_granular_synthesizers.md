---
title: GitHub Open-Source Granular Synthesizer / Sampler (SuperCollider)
category: reference
tags: [granular, GrainBuf, TGrains, Warp1, github, open-source, scatter, timestretch]
---

## GitHub オープンソース グラニュラーシンセ・サンプラー集

GitHubで公開されているSuperColliderのグラニュラー合成リポジトリの技法まとめ。

---

## リポジトリ一覧

### 1. martinfm / PGranular
**URL:** https://github.com/martinfm/PGranular
**特徴:** GUIフロントエンド付き。ライブパフォーマンス用途。最大10グレインレイヤー同時制御。

**使用UGen:** TGrains2（sc3-plugins拡張版）
**制御:** MIDIコントロール・マウス・DAWオートメーション対応

**パラメーター:**

| パラメーター | 説明 |
|---|---|
| size | グレインの長さ（ミリ秒） |
| position | バッファ内の読み出し位置 |
| amplitude | 音量 |
| pan | ステレオパン |
| pitch | ピッチ（レート倍率） |
| randomization | 各パラメーターへの確率的ゆらぎ |
| LFO | パラメーターへの低周波変調 |

---

### 2. Vasileios / Simple_Sc_Granulator_GUI
**URL:** https://github.com/Vasileios/Simple_Sc_Granulator_GUI
**特徴:** GrainBufを使ったシンプルなGUI付きグラニュレーター。学習用に最適。

**技法:**
- `GrainBuf` + `TRand.ar` による位置スキャッター
- パラメーター：密度（freq）、グレインサイズ（dur）、位置（pos）、スキャッター（spr）、リバース確率

```supercollider
SynthDef(\buff, {
    |freq = 10, dur = 0.1, gate = 1, buff, rate = 1,
     pos = 0, pan = 0, out = 0, spr = 0.05|
    var trig = Impulse.ar(freq);
    // TRandでグレイン位置にランダムスキャッターを加える
    var spread = TRand.ar(spr.neg * 0.5, spr * 0.5, trig);
    var sig = GrainBuf.ar(2, trig, dur, buff, rate, pos + spread, 0, pan);
    var env = EnvGen.kr(
        Env([0.0, 1, 1, 0],
            [0.1, 0.2, 0.2]),
        gate, doneAction: 2
    );
    Out.ar(out, sig * env * 0.5);
}).add;
```

---

### 3. alikthename / Musical-Design-in-Supercollider
**URL:** https://github.com/alikthename/Musical-Design-in-Supercollider
**対象ファイル:** `13_microsound_granular_phrase_sampler.sc`
**特徴:** YouTube「Musical Sound Design In SuperCollider」シリーズ対応コード集。
タイムストレッチ・ピッチシフト・グラニュラーリバーブを実装。

**技法:**
- `GrainBuf` + `Phasor` / `BufRd` を組み合わせたグラニュラー再構成
- `Phasor.ar` でバッファを連続スキャンしてタイムストレッチを実現
- 位置を0〜1正規化して `GrainBuf` の `pos` に渡す

```supercollider
// GrainBuf + Phasor によるタイムストレッチ
Ndef(\granular_reconstruct, {
    var tFreq = 50;          // grain density（グレイン/秒）
    var overlap = 4;
    var bufFrames = BufFrames.kr(~buf);
    // Phasorでバッファをスキャン
    var phasor = Phasor.ar(0, BufRateScale.kr(~buf), 0, bufFrames);
    var pos = phasor / bufFrames;  // 0〜1正規化
    GrainBuf.ar(
        2,                    // チャンネル数
        Impulse.ar(tFreq),    // トリガー（グレイン密度）
        overlap / tFreq,      // グレインサイズ（秒）
        ~buf,
        1,                    // rate（ピッチ）
        pos                   // 位置
    )
});
```

---

### 4. bsnacks000 / TransGrain
**URL:** https://github.com/bsnacks000/transgrain
**特徴:** JIT ProxySpaceを使ったモジュラー型グラニュラーAPI。ライブコーディング対応。

**技法:**
- `EnvelopeクラスとGrain Generatorクラスの2種類を組み合わせる設計
- ProxySpaceにロードしてリアルタイムで書き換え可能
- セッターメソッドが `Pseq` / `Prand` などのPatternオブジェクトを受け付ける

```supercollider
(
s.waitForBoot({
    p = ProxySpace(s);
    ~sine = GaussSine(s, p, \gsine);
    ~cloud = CloudEnv(s, p, \genv);
});
)
```

---

### 5. madskjeldgaard / Particular
**URL:** https://github.com/madskjeldgaard/Particular
**特徴:** パーティクルごとにSynthを起動する「言語側グラニュラー」方式。Pbind/Pdefと組み合わせ。

**インストール:**
```supercollider
Quarks.install("https://github.com/madskjeldgaard/Particular.git")
```

**特徴:**
- UGen内部処理ではなくPatternがSynth生成を制御（低密度の粒に向いている）
- グレインのパラメーターをパターンで記述できる（`design_probability_control.md` の思想と一致）

---

### 6. passivist / GRNLR_SC
**URL:** https://github.com/passivist/GRNLR_SC
**特徴:** 卒業論文。JUCEプラグインGRNLRのSCプロトタイプ。グレインエンベロープと補間の実装が参照価値高い。

---

### 7. Xon77 / Live4Life
**URL:** https://github.com/Xon77/Live4Life
**特徴:** 8チャンネル・マルチスピーカー対応の空間的パフォーマンスツール。

**技法:**
- ミクロ（マイクロサウンド）とマクロ（フレーズ）レベルのグラニュレーションを切り替え
- 空間的軌跡アルゴリズムと連動したグレイン拡散
- チャンネルベースとオブジェクトベースの空間化を混在

---

## 主要UGenの技法比較

| UGen | 特徴 | 位置指定 | ピッチ制御 | カスタムエンベロープ | タイムストレッチ |
|------|------|---------|-----------|---------------------|----------------|
| **TGrains** | シンプル・高速。ハニング窓固定 | 秒単位 | rate倍率 | 不可 | 不可 |
| **GrainBuf** | エンベロープ自由・スキャッター設計しやすい | 0〜1正規化 | rate倍率 | 可（envbufnum） | 不可 |
| **Warp1** | 内部で連続グレインを管理。タイムストレッチ専用 | pointer 0〜1 | freqScale倍率 | 可 | 可（本質的機能） |
| **BufGrain** | demand-rate UGenと組み合わせるパターン指向 | 0〜1 | rate | 可 | 条件次第 |

---

## グラニュラー特有のパラメーター設計パターン

```supercollider
// 典型的なグラニュラーSynthDefのパラメーター構成
SynthDef(\granular, {
    |buf,
     density    = 20,    // grains/sec: グレイン密度（10〜100が典型）
     grainSize  = 0.1,   // seconds: グレインサイズ（10〜200ms が典型）
     pos        = 0.5,   // 0〜1: バッファ内読み出し位置
     posScatter = 0.05,  // ±: 位置のランダムゆらぎ（Burial的非グリッド感）
     rate       = 1.0,   // ピッチ倍率（1=原音、0.5=1オクターブ下）
     rateScatter = 0,    // ±: ピッチのランダムゆらぎ
     pan        = 0,     // -1〜1: パン
     amp        = 0.5|

    var trig = Impulse.ar(density);
    var jitteredPos  = pos  + TRand.ar(posScatter.neg,  posScatter,  trig);
    var jitteredRate = rate + TRand.ar(rateScatter.neg, rateScatter, trig);

    GrainBuf.ar(2, trig, grainSize, buf, jitteredRate, jitteredPos,
        -1,  // envbufnum: -1=デフォルトのハニング窓
        pan
    )
}).add;
```

---

## Warp1 によるタイムストレッチ実装

```supercollider
SynthDef(\warp, { arg buffer = 0, envbuf = -1;
    var pointer = Line.kr(0, 1, 15);   // 15秒かけてバッファを移動
    var pitch   = MouseX.kr(0.5, 2);   // マウスでピッチ制御
    var env = EnvGen.kr(
        Env([0.001, 1, 1, 0.001], [0.1, 14, 0.9], \exp),
        doneAction: 2
    );
    var out = Warp1.ar(
        1,        // numChannels
        buffer,
        pointer,  // 0〜1 の位置
        pitch,    // freqScale（ピッチ倍率）
        0.1,      // windowSize（グレインサイズ）
        envbuf,   // -1=デフォルトのハニング窓
        8,        // overlaps（重なり数）
        0.1,      // windowRandRatio（スキャッター量）← Tim Hecker的崩壊感
        2         // interp（補間方式）
    );
    Out.ar(0, out * env);
}).add;
```

---

## バッファ管理パターン

```supercollider
// モノラル強制読み込み（グラニュレーターでは1chが安全）
~buf = Buffer.readChannel(s, "/path/to/file.wav", channels: 0);

// リアルタイム録音 → 同じバッファをグラニュレーション（ライブグラニュラー）
~recBuf = Buffer.alloc(s, s.sampleRate * 4, 1);  // 4秒
SynthDef(\recordIn, {
    RecordBuf.ar(SoundIn.ar(0), ~recBuf, loop: 1);
}).play;

// カスタムグレインエンベロープ（ハニング以外）
~envBuf = Buffer.alloc(s, 1024, 1);
~envBuf.sine1([1]);  // サイン波エンベロープ
// GrainBuf の envbufnum に ~envBuf.bufnum を渡す
```

---

## MaToMaへの応用

| 技法 | 美学的効果 | 参照アーティスト |
|------|-----------|----------------|
| `GrainBuf` + `TRand` スキャッター | グリッドから外れた粒状感 | Burial |
| `Warp1` の `windowRandRatio` | 制御された崩壊テクスチャ | Tim Hecker |
| `TransGrain` (ProxySpace) | ライブ中のリアルタイムパラメーター変更 | Autechre |
| `Particular` + `Pbind` | グレイン密度・ピッチをパターンで確率制御 | Autechre / Alva Noto |
| リアルタイム録音バッファのグラニュレーション | 自分の音を即座にテクスチャ化 | 全般 |

---

## 参考リンク

- [GrainBuf 公式ドキュメント](https://doc.sccode.org/Classes/GrainBuf.html)
- [TGrains 公式ドキュメント](https://doc.sccode.org/Classes/TGrains.html)
- [Warp1 公式ドキュメント](https://doc.sccode.org/Classes/Warp1.html)
- [Buffer Granulation チュートリアル](https://pustota.basislager.org/_/sc-help/Help/Tutorials/Buffer_Granulation.html)
