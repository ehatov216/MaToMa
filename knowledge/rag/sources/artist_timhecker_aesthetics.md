# Tim Heckerの音響美学と制作技法

## 概要

Tim Heckerの音楽は、パイプオルガン・ピアノ・雅楽楽器などのアコースティック音源を、Max/MSP・Eventide H3000・グラニュラー合成・スペクトル処理で「制御された崩壊」へと再構築する。

本人の言葉：**「エフェクトを狂ったようにかけ続けて、何が起きているかもう理解できないところまで持っていく。音源が信号処理のプロセスから分離して、夢のような状態の顕現になる」**

---

## 機材

### 楽器・音源

| 音源 | 詳細 |
|------|------|
| **パイプオルガン** | *Ravedeath, 1972*：レイキャビク「Fríkirkjan」教会で2010年7月21日たった1日のセッション |
| **Nord Modular G2** | 「壊れた時のためにもう1台買った」「初期のDSPタイプのシンセで、創造的な形で誤動作する」 |
| **Waldorf Quantum** | 現在のメインシンセ。「アナログとデジタルの最良のアプローチを統合した完璧なシンセに最も近い」 |
| **Moog One** | スコアリング作業用 |
| **ARP Omni** | ヴィンテージストリングシンセ |
| **ヴァージナル** | *Virgins*（2013）の核心音源。「より打楽器的で不規則な響き」 |
| **雅楽楽器（笙・龍笛・篳篥）** | *Konoyo/Anoyo*：東京・慈雲山曼荼羅寺観蔵院で東京楽所と録音 |

### アウトボードエフェクト

| 機材 | 役割 |
|------|------|
| **Eventide H3000 D/SE Ultra-Harmonizer** | 最重要プロセッサ。2025年時点でも「go-to」。ピッチシフト・ディレイ・空間処理 |
| **Eventide H8000** | H3000と並んでラックに設置 |
| **Lexicon PCM-70** | アルゴリズミック・リバーブ |
| **Thermionic Culture Vulture** | 真空管サチュレーション。テープ的な倍音歪み |
| **Echo Fix EF-X2** | テープエコー |
| **ProCo TurboRAT** | 「コンピュータのクリニカルな音をTurboRAT歪みペダルに通してリサンプルする」 |
| **Traynor YGM-4 Studio Mate**（2台） | リアンプ用真空管アンプ |
| **Radial X-AMP** | リアンプ・ボックス |
| **Manley Massive Passive EQ** | マスターチェーンEQ |
| **Burl B2 Bomber ADC** | 高品質AD変換 |

---

## ソフトウェア

| ツール | 役割 |
|--------|------|
| **Max/MSP** | 20年以上のメイン処理ツール。カスタムパッチによるリアルタイムDSP。「バッファを掴んでポーズをかけ、時間にほぼ弾力性を持たせて引き伸ばすことができる」 |
| **ppooll**（Klaus Filip製） | *Konoyo/Anoyo*の録音セッションで使用。雅楽楽器のリアルタイム処理 |
| **NI Reaktor** | 「freaky deaky Reaktor jobbies」。Max/MSPと並ぶ処理プラットフォーム |
| **Logic** | 最終的なアレンジ・コンポジション |
| **Ableton Live** | ライブパフォーマンスでステムを投げ込みMax/MSPで処理 |

プラグイン名を明かすことに消極的：「プラグインについて聞かれなくて幸いだった」→ **個別プラグインより信号チェーン全体の設計が重要**。

---

## 「制御された崩壊」の6つの技法

### 1. ドローン生成：10〜15層のサブレイヤー堆積

**プロセス：**
1. 「結晶化された種子」（メロディックなフック・モチーフ・コード変化）から出発
2. 「本当に物理的に扱い、押し、即興し、叩きつけ、反転させる」
3. 録音・処理し、新しい録音を生成
4. 重ね合わせと削減を反復 → 「すべてが一緒にぼやけ始めるまで」
5. 「出発点はリテラルにもコンピュータのメモリからも消去される」

Jackson Pollockのガーゼ紙重ね技法に喩えられる：「一番上に描き、乾かし、次のページを剥がすと前のページの痕跡があり、それに応じて描く」

### 2. グラニュラー合成

**「シンセは音源として素晴らしい。しかし裸の状態で演奏するのは退屈だ。だから分解して霧にしたり、グラニュレートしたりする。ほとんどスプレーガンのように」**

- *Love Streams*：アイスランドの合唱をグラニュレートして「屈折した忘却の拡散されたビーム」を生成
- Van Halenのギターリフをグラニュレートして「マッチョなギターシュレッドを切り刻む」

### 3. スペクトル処理（FFTベース）

- Max/MSPの`pfft~`オブジェクトファミリー
- ppoollのスペクトル処理モジュール
- SoundHack（Tom Erbe製）

スペクトログラム分析では「2kHz以上の周波数が、500Hz・700Hz・1kHzの倍音帯に関連してオン・オフする」

### 4. リアンプ（物理空間をリバーブとして使用）

**「デジタルの音を部屋の奥にあるアンプに送り出し、最も遠い角にリボンマイクを置いて、それをキャプチャして、さらにプッシュする作業を始める」**

- Alvin Lucierの*I Am Sitting in a Room*を明示的なモデルとして参照
- デジタル→アンプ→部屋→リボンマイク→処理→再びアンプのサイクル
- 各パスが部屋の共鳴を強調し着色を導入する「反復的劣化」

### 5. フィードバックループとリバーブの連鎖

**「3つのディレイ、大量のコンプレッサー、リバーブの信号チェーン。短いルームリバーブから巨大な洞窟へ。そしてそれを1オクターブ下にピッチダウンすると、全く別の場所にいる」**

### 6. ディストーション・サチュレーション

- **バスレベルのディストーション**（個別トラックではなくサミングバスに）→ 素材が密になるほど歪みが増す
- パラレル処理（重度に歪んだ信号 + クリーンな信号のブレンド）

**破壊的ワークフロー：「破壊的に作業していて、400チャンネルの録音が残らないようにしている」** → 不可逆的な処理へのコミットメント

---

## SuperColliderでの再現

### DFM1自己発振フィルターによるオルガン的ドローン

```supercollider
~r = {54};  // 基音周波数（MIDI: F#2）
(
~dfm1 = {arg mult = 1; DFM1.ar(
    SinOsc.ar([~r,~r*1.01]*mult, 0, 0.1),
    (~r*2)*mult,
    LFNoise1.kr(0.05).range(0.9, 4.5),  // レゾナンスを緩やかに変調
    1, 0, 0.0003, 0.5)};
~dfm2 = {arg mult = 2; DFM1.ar(
    SinOsc.ar([~r,~r*1.01]*mult, 0, 0.1),
    (~r*2)*mult,
    LFNoise1.kr(0.06).range(0.9, 2.3),
    1, 0, 0.0003, 0.5)};
~dfm3 = {arg mult = 3; DFM1.ar(
    SinOsc.ar([~r,~r*1.01]*mult, 0, 0.1),
    (~r*2)*mult,
    LFNoise1.kr(0.056).range(0.9, 1.9),
    1, 0, 0.0003, 0.5)};
~dfm4 = {arg mult = 4; DFM1.ar(
    SinOsc.ar([~r,~r*1.01]*mult, 0, 0.1),
    (~r*2)*mult,
    LFNoise1.kr(0.07).range(0.9, 1.5),
    1, 0, 0.0003, 0.5)};
)
// ~r*1.01 の微細デチューンがコーラス効果を生む
// mult 1,2,3,4 で倍音列構造（オルガン的音色）
// 各レイヤーのLFNoise1が異なるレートでレゾナンスを変調 → 非反復的テクスチャ
```

### スペクトル凍結・ぼかし（Hecker的テクスチャの核心）

```supercollider
SynthDef(\spectralHecker, {
    arg buf, freeze=0, smear=10, scramble=0;
    var sig, chain;
    sig = PlayBuf.ar(1, buf, loop:1);
    chain = FFT(LocalBuf(2048), sig);
    chain = PV_MagFreeze(chain, freeze);     // freeze>0でスペクトル凍結
    chain = PV_MagSmear(chain, smear);       // ビン間の平均化（0-100）→ スペクトルのぼかし
    chain = PV_BinScramble(chain, scramble, 0.1, LFNoise0.kr(2));
    sig = IFFT(chain);
    sig = JPverb.ar(sig!2, 8, 0.5, 3, 0.7, 0.8); // 長いリバーブテール
    Out.ar(0, sig * 0.5);
}).add;
```

**PV_MagSmear**（ビン間の平均化）がHeckerの最も特徴的な質感「スペクトルのぼかし」を生成する。

### フィードバック・ドローン（Lucierスタイル）

```supercollider
SynthDef(\feedbackDrone, {
    arg freq=60, fbAmt=0.85, filterFreq=800, amp=0.3;
    var sig, fb;
    fb = LocalIn.ar(2);
    fb = HPF.ar(fb, 40);
    fb = LPF.ar(fb, filterFreq + LFNoise1.kr(0.1).range(-200,200));
    sig = SinOsc.ar([freq, freq*1.005], 0, 0.1) + (fb * fbAmt);
    sig = sig + (AllpassC.ar(sig, 0.5,
        LFNoise1.kr(0.1).range(0.01,0.5), 3) * 0.3);
    sig = tanh(sig * 1.5);   // ソフト・サチュレーション
    sig = LeakDC.ar(sig);
    LocalOut.ar(sig);
    Out.ar(0, Limiter.ar(sig * amp));
}).add;
```

### グラニュラー・テクスチャ・クラウド

```supercollider
SynthDef(\grainCloud, {
    arg buf, rate=1, pos=0.5, grainDur=0.1, density=20, amp=0.3,
        posRand=0.1, pitchRand=0.1;
    var sig, trig;
    trig = Dust.kr(density);  // 不規則なグレイン発火（Dustで非周期的に）
    sig = GrainBuf.ar(2, trig, grainDur, buf,
        rate * LFNoise1.kr(0.3).range(1-pitchRand, 1+pitchRand),
        pos + LFNoise1.kr(0.5).range(posRand.neg, posRand),
        pan: LFNoise1.kr(0.5).range(-1,1)
    );
    sig = JPverb.ar(sig, 5, 0.9, 4, 0.8);
    Out.ar(0, sig * amp);
}).add;
```

### 推奨シグナルチェーン（全体）

```
音源（Buffer/DFM1/FM）
→ GrainBuf / Paulstretch（極端なタイムストレッチまたはグラニュラー走査）
→ FFTスペクトル処理（PV_MagSmear → PV_MagFreeze → PV_BinScramble → IFFT）
→ tanh サチュレーション
→ RLPF（LFNoise1で変調）
→ LocalIn/LocalOut フィードバック + AllpassC
→ JPverb（t60: 5〜15秒）
→ Compander + LeakDC + Limiter
```

---

## Paulstretch実装（SuperCollider）

```supercollider
SynthDef(\paulstretchMono, {
    |out=0, bufnum, envBufnum, pan=0, stretch=50, window=0.25, amp=1|
    var trigPeriod, sig, chain, trig, pos, fftSize;
    fftSize = 2**floor(log2(window*SampleRate.ir));
    trigPeriod = fftSize/SampleRate.ir;
    trig = Impulse.ar(1/trigPeriod);
    pos = Demand.ar(trig, 0, demandUGens: Dseries(0, trigPeriod/stretch));
    sig = [
        GrainBuf.ar(1, trig, trigPeriod, bufnum, 1, pos, envbufnum: envBufnum),
        GrainBuf.ar(1, trig, trigPeriod, bufnum, 1,
            pos+(trigPeriod/(2*stretch)), envbufnum: envBufnum)
    ] * amp;
    sig = sig.collect({ |item, i|
        chain = FFT(LocalBuf(fftSize), item, hop:1.0, wintype:-1);
        chain = PV_Diffuser(chain, 1 - trig);  // ランダム位相シフト
        item = IFFT(chain, wintype:-1);
    });
    Out.ar(out, Pan2.ar(Mix.new(sig), pan));
}).add;
// stretch=50: 50倍に引き伸ばし。100〜1000xも有効
```

---

## 推奨プラグイン（Ableton/DAW環境）

### 最重要（Hecker的サウンドの核心）

| プラグイン | 価格 | 役割 |
|-----------|------|------|
| **Valhalla Supermassive** | 無料 | 巨大なリバーブ/ディレイ。アンビエントドローンに最適 |
| **ValhallaShimmer** | ~$50 | Eventide Blackholeに最も近い。Feedback 0.0・Diffusion 0.618で「Paulstretchとほぼ同一の効果」 |
| **Eventide Blackhole** | $69-199 | Heckerの音のDNA。超拡散エーテルリバーブ。Freeze機能 |
| **Eventide H3000 Native** | — | Hecker確認済みハードウェアのプラグイン版 |
| **Eventide MangledVerb** | — | リバーブ→ディストーション。Hecker的な「圧縮/歪んだリバーブ」に直結 |

### スペクトル処理

| プラグイン | 価格 | 役割 |
|-----------|------|------|
| **SoundHack +bubbler** | 無料 | 8chグレインで極めて密なクラウド生成 |
| **SoundHack +spectralcompand** | 無料 | 513バンドスペクトルコンプレッサー/エクスパンダー |
| **SoundHack ++spiralstretch** | 有料 | 極端なタイムストレッチ |
| **GRM Tools Evolution** | €240-550 | 「聞いた中で最高のスペクトルフリーズ効果」 |
| **Michael Norris SoundMagic Spectral** | 無料（macOS AU） | 23の無料スペクトル処理。SpectralDroneMaker・SpectralFreezing・SpectralBlurringなど |

### その他

| プラグイン | 役割 |
|-----------|------|
| **NI Reaktor** | Hecker本人が使用確認済み |
| **FabFilter Saturn 2** | マルチバンドサチュレーション。温かい歪み |
| **Soundtoys Crystallizer** | グラニュラー的なリバースエコー+ピッチシフト |
| **Paulstretch**（無料スタンドアロン） | 30秒の即興を10-30分に引き伸ばし処理 |

---

## 音響特性とミキシング方針

- **低域が非常に豊か**（特にパイプオルガンのサブベース）
- **高域は処理により減衰**しメロディはテクスチャに従属
- ダイナミクスの幅が大きい：静寂な箇所と圧倒的なノイズピークの対比
- ラウドネス：**-14〜-16 LUFS**程度（ラウドネス・ウォーズからの意識的距離）
- ECMレコードのアプローチを参照：「大規模アンサンブルの録音に含まれる風通しの良いパワー」

---

## 4アーティスト比較

| 軸 | Autechre | Burial | Alva Noto | **Tim Hecker** |
|----|----------|--------|-----------|----------------|
| 音源 | FM・デジタル合成 | Foley・ボーカル断片 | サイン波・クリック | アコースティック楽器（オルガン・雅楽） |
| 処理の方向 | アルゴリズム生成 | 手作業コラージュ | 還元・精密 | **破壊・崩壊・再構築** |
| リバーブの役割 | FDN・空間制御 | 霧で包む | 沈黙との対比 | **物理空間を楽器として使う（リアンプ）** |
| ノイズの意味 | エラーの音楽化 | 記憶の劣化 | 物理的現象 | **崩壊のテクスチャ・時間の痕跡** |
| 時間軸 | 非線形・確率的 | 失われた過去 | 現在・構造 | **積層・反復的変容** |
| 核となる美学 | 機械の超知性 | 傷つく個人の記憶 | 臨床的な科学的探究 | **「制御を手放す」夢のような状態** |

---

## MaToMaへの実践的示唆

- [ ] 音源をそのまま鳴らすのではなく「霧にする・グラニュレートする」工程があるか？
- [ ] PV_MagSmearで「スペクトルのぼかし」を使っているか？（Hecker最特徴）
- [ ] `tanh`や`distort`でサチュレーションをバスレベルで適用しているか？
- [ ] LocalIn/LocalOutのフィードバックで「部屋の共鳴」をシミュレートしているか？
- [ ] JPverbのt60を5秒以上に設定した巨大なリバーブテールを使っているか？
- [ ] 「破壊的ワークフロー」として処理済み音を不可逆的にコミットして次の素材にしているか？
- [ ] 「1オクターブ下にピッチダウン」（`PitchShift.ar(sig, pitchRatio:0.5)`）を活用しているか？

**Tim Heckerの核心：「トリックの一部は自分自身を見失い、制御しないことだ」**
