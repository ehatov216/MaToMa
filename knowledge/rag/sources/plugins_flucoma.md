---
title: FluCoMa — SuperCollider用MLオーディオ解析ツールキット
category: plugin
tags: [flucoma, machine-learning, analysis, spectral, pitch, loudness, MFCC, HPSS, NMF, neural-network]
---

## FluCoMa (Fluid Corpus Manipulation)

FluCoMa は SuperCollider（およびMax/Pd）向けの **機械学習・音声解析ツールキット**。
インストールは Quarks マネージャから：

```supercollider
Quarks.install("FluidCorpusManipulation")
```

---

### 1. リアルタイム音声ディスクリプタ（特徴量抽出）

| UGen | 出力 | 用途 |
|------|------|------|
| `FluidSpectralShape.kr(sig)` | centroid, spread, skewness, kurtosis, rolloff, flatness, crest の7値 | 音の「スペクトル形状」を数値化 |
| `FluidPitch.kr(sig)` | pitch(Hz), confidence(0–1) | 基音推定。confidence が低い = ノイズ/複音 |
| `FluidLoudness.kr(sig)` | loudness(LUFS), truepeak(dBFS) | EBU R128準拠のラウドネス |
| `FluidMFCC.kr(sig, numCoeffs: 13)` | 13次元のMFCC係数 | 音色の輪郭（timber fingerprint） |
| `FluidOnsetSlice.kr(sig)` | onset trigger | アタック検出トリガー |

#### SpectralShape 各値の意味

| 値 | 音のイメージ |
|---|---|
| `centroid` 低い | こもった・暗い音 |
| `centroid` 高い | 明るい・シャリシャリした音 |
| `spread` 大きい | 広帯域ノイズ的 |
| `flatness` 高い | ホワイトノイズに近い（倍音が均等） |
| `flatness` 低い | 純音・倍音が少ない |

#### リアルタイム解析の例
```supercollider
{
    var sig = SoundIn.ar(0);
    var shape = FluidSpectralShape.kr(sig);
    var pitch = FluidPitch.kr(sig);
    var loud  = FluidLoudness.kr(sig);

    // 各値をOSC送信（Python ブリッジ経由でUIに流せる）
    SendReply.kr(Impulse.kr(10), '/analysis', [
        shape[0],  // centroid
        shape[5],  // flatness
        pitch[0],  // pitch Hz
        pitch[1],  // confidence
        loud[0]    // loudness LUFS
    ]);
    sig
}.play;
```

---

### 2. HPSS — 倍音成分とパーカッシブ成分の分離

**Harmonic-Percussive Source Separation**：スペクトログラム上の「水平（=倍音）」「垂直（=打撃音）」を分離する。

```supercollider
// バッファ処理版
(
var src = Buffer.read(s, "~/sample.wav");
var harm = Buffer.new(s);
var perc = Buffer.new(s);
var res  = Buffer.new(s);

Routine {
    FluidBufHPSS.processBlocking(s, src,
        harmBuf: harm,
        percBuf: perc,
        resBuf: res,
        harmFilterSize: 17,
        percFilterSize: 31
    );
    "HPSS done".postln;
}.play;
)
```

用途：
- 倍音成分を取り出して Pitch 精度を上げる
- パーカッシブ成分を取り出してオンセット検出に使う

---

### 3. NMF — 非負値行列因子分解による音源分離

`BufNMF`：バッファ内の音を複数の「隠れた成分」に分解する（ドラムループからキック・スネア・シンバルを分離する、など）。

```supercollider
(
var src     = Buffer.read(s, "~/drums.wav");
var resynth = Array.fill(3, { Buffer.new(s) });
var bases   = Buffer.new(s);
var acts    = Buffer.new(s);

Routine {
    FluidBufNMF.processBlocking(s, src,
        resynth: resynth,
        bases: bases,
        activations: acts,
        components: 3,   // 分解する成分数
        iterations: 100
    );
    "NMF done".postln;
}.play;
)
```

---

### 4. ニューラルネットワーク — MLPClassifier / MLPRegressor

**音色分類**（どの楽器か？）や **パラメーター回帰**（音の特徴からシンセパラメーターを推定）に使う。

```supercollider
// 学習済みモデルでリアルタイム分類
(
var classifier = FluidMLPClassifier.new(s, [13, 8, 4]);
// .fit() で学習、.predict() で推論

// リアルタイム推論
{
    var sig  = SoundIn.ar(0);
    var mfcc = FluidMFCC.kr(sig, numCoeffs: 13);
    var label = FluidMLPClassifier.kr(classifier, mfcc);
    label.poll(1);
}.play;
)
```

---

### 5. オーディオスライシング

| オブジェクト | 検出方式 |
|---|---|
| `FluidAmpSlice` | 振幅エンベロープの変化点 |
| `FluidAmpGate` | 絶対振幅しきい値によるゲート |
| `FluidOnsetSlice` | スペクトル変化によるオンセット |
| `FluidTransientSlice` | 過渡成分（アタック）の検出 |
| `FluidNoveltySlice` | スペクトル新規性（突然の変化） |

---

### 6. データ処理ユーティリティ

| クラス | 用途 |
|---|---|
| `FluidBufStats` | バッファ統計（平均・中央値・標準偏差） |
| `FluidNormalize` | 0–1 スケーリング |
| `FluidStandardize` | 平均0・標準偏差1に正規化 |
| `FluidUMAP` | 高次元特徴量を2次元に次元削減（コーパス可視化） |
| `FluidPCA` | 主成分分析 |
| `FluidKMeans` | k-meansクラスタリング |

---

### MaToMa での活用イメージ

- `FluidSpectralShape` + `FluidPitch` をリアルタイム実行し、その値を Python ブリッジ経由でブラウザUIに表示
- 音の明るさ（centroid）や倍音らしさ（confidence）をシンセパラメーターへフィードバック
- `FluidHPSS` でライブ入力を分解し、倍音成分だけを加工・エフェクト処理

### インストール
```supercollider
Quarks.install("FluidCorpusManipulation");
// 再起動後:
s.reboot;
```
