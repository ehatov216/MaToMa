# Knowledge Wiki Ingest Log

このファイルは `knowledge/rag/sources/` への情報追加履歴を記録する。

---

## [2026-04-12] ingest | G1: psych_wood_vibration + psych_modal_vibration (物理振動系)

**ソース**:

- psych_wood_vibration (100件取得)
- psych_modal_vibration (10件取得)

**分類結果**:

- HIGH: 0件
- MEDIUM: 0件
- SKIP: 全10件（ユニーク記事数）

**判断理由**:

- 119件のURL中、重複（ページネーション）を除くとユニーク記事は10件のみ
- うち2件が物理振動研究論文だったが、具体的な数値データ（周波数比・減衰時間）なし
- 残り8件はジャーナルメタデータページ（About, Board, Copyright等）
- SC物理モデリング合成に応用可能な実測値が含まれていなかったため、全件SKIP

**更新したページ**: なし

**ingested_urls.txt への追記**: 110 URL（重複含む全URL）を一括登録

---

## [2026-04-12] ingest | Goshev (2004) & Henrich et al. (2010) — ブルガリア民族音楽 学術論文2本

**ソース**:
- Goshev, Ivan (2004). "Construction and Systematization of Sound Rows in Bulgarian Folk Music."
- Henrich, Nathalie et al. (2010). "Resonance strategies used in Bulgarian women's singing style."

**更新したページ**: `synthesis_bulgarian_voice.md`

**新規追加したセクション**:

### Section 15: テトラコード分類体系（Goshev）
- **ダイアトニック・テトラコード** — Dorius(d-es-f-g) / Phrygius(d-e-f-g) / Lydius(d-e-fis-g) の3型
- **クロマティック・テトラコード** — 増2度を含む3型（Hicaz典型・密集クロマティック・二重増音程）
- **複合音列分類** — ダイアトニック複合・クロマティック複合・バイクロマティック・ペンタトニック
- **マカーム音列の正確な音名**（Goshev 原典表記）: Hidjas/Kardjagar/Myustaar/Hyzam/Sultani Yegyah/Suuzinak の音名列と半音数インデックスの対応表
- **SuperCollider 実装** — `Scale.add` による Hidjas/Suuzinak/Myustaar の登録コード、テトラコード1個分の音域制限による民謡的狭い音域の再現方法

### Section 8 追記: Henrich et al. 精密測定データ
- **テッシトゥーラ実測値** — グループユニゾンD4–A4 / ソプラノソロC4–C5 / アルトA3–A4
- **Teshka vs Leka の声門メカニズム** — Teshka: 高速閉鎖 → **H2（第2倍音）が H1（基音）を振幅で上回る**（音響的重要発見）; Leka: 緩やか閉鎖 → H1 優位
- **SuperCollider 実装** — `\bulgarian_teshka` SynthDef（H2を最大ゲインにしH1を軽くノッチ）・`\bulgarian_leka` SynthDef（SinOsc系でH2弱め）

**出典セクション更新**: 2本の論文を `## 出典` に追加

**ingested_urls.txt への追記**: なし（PDFはURLなし・ローカル提供）

---

## [2026-04-12] update | ブルガリアンボイス — 高度理論・音響・歴史・電脳美学を追加

**更新したページ**: `synthesis_bulgarian_voice.md`

**追加した主な内容**（重複除外後）:
- **スケール・モード詳細** — フリジアン・ドミナント/ドリアン(#6)/ミクソリディアンの音程構造
- **ブルガリアン・マカーム一覧** — Hicaz/Mustear/Karcigar/Huzzam/Sultani Yegah/Hicazkar（等分平均律近似）
- **逆転した和声論理（Kirilov）** — vii→I が優位な終止。Finalis = 2度・7度（主音への解決なし）
- **発声法詳細（Teshka/Leka）** — R1-H2フォルマント同調による音量増幅。テッシトゥーラ D3–D5
- **母音選択** — [α][ε][ο]はR1高→H2同調しやすい。[i][u]は不向き
- **装飾音システム** — Tresene（声門トレモロ）/Glissando（打撃的）/Zadarjane（延長）/Sechene（切断）
- **ドローン分類** — Steady 1-5型 / Variable 1-3型の民俗音楽学的分類
- **クラスターボイシング技法** — 2度積み閉位置。Cmaj9[add13]・Dmin11の具体的配置例
- **Aksak認知心理学的規則** — [3]拍グループ前に[2]×2以上必要
- **アウフタクト禁止** — ブルガリア語語頭強勢によりビート1から始まる
- **モチーフ構造（非AB形式）** — 短い主題の反復変奏。大きな構造変化なし
- **4ステップ作曲方法論** — リズム→マカームメロディ→ドローン/逆転和声→歌唱指示
- **歴史的文脈** — オスマン帝国485年支配・Philip Koutev（1952年合唱団創設）
- **菅野よう子/Ghost in the Shell 電脳化美学** — 有機的声楽×電子音の「電脳化」音響メタファー

---

## [2026-04-12] ingest | ブルガリアンボイス — 作曲・メロディ・リズム・ボイシング

**ソース**: Web調査（Wikipedia / ResearchGate / Chromatone / composerprogrammer.com）

**新規作成したページ**: `synthesis_bulgarian_voice.md`

**要点**:
- **ディアフォニー（2声式ポリフォニー）** — ドローン声部（第2声）＋ソロメロディ（第1声）の2層構造
- **不協和2度の意図的使用** — 長2度・短2度を「解決しない」まま浮かせる。並行4度・5度も基本語法
- **マイクロトーン装飾** — 25cent幅のグレース・ノート（シマー効果）
- **Aksak加算リズム** — 短拍(2)+長拍(3)の加算。7/8(2+2+3)Rachenitsa・9/8(2+2+2+3)Daichovo等
- **発声特性** — ビブラートなし・胸声・1オクタ以内・グリッサンド・装飾音多用
- **SC実装** — `Formlet`/`BPF`声道フィルター、`Lag`グリッサンド、Pbind Aksakリズム構築
- **MaToMa層マッピング** — ドローン層→持続2声, メロディ層→ソロ声部, リズム層→Aksak

---

## [2026-04-11] ingest | FluCoMa公式ドキュメント（sc_flucoma handler）

**ソース**: UnifiedScraper DB `sc_knowledge.db` の `sc_flucoma` ハンドラー（118記事）

**更新したページ**: `plugins_flucoma.md`

**追加した主な技術・クラス**:
- **DataSet** — 音響特徴量の保存とクエリ（addPoint/getPoint/write/read）
- **KNNClassifier** — K近傍法による音色分類（fit/predict、MLPClassifier との違い）
- **スライシング3種の使い分け** — OnsetSlice（スペクトル変化）/ TransientSlice（過渡成分）/ NoveltySlice（構造的セグメント）
- **NMFFilter** — リアルタイム音源分離（学習済みbasesで入力を複数ストリームに分解）
- **NMFMatch** — リアルタイム音色検出（basesとの類似度を継続出力）
- **バッチ処理パターン** — 複数ファイル処理・非ブロッキング処理（`.process()` vs `.processBlocking()`）

**追記した主なコードパターン**:
- DataSet のポイント追加・取得の基本フロー
- KNNClassifier の学習・推論サンプル
- OnsetSlice の10種メトリック（metric 9推奨）
- TransientSlice のパラメーター（order/threshFwd/threshBack）
- NoveltySlice の自己類似度行列（SSM）とkernelSize
- NMFFilter/NMFMatch によるリアルタイムドラム分離・検出
- バッチ処理の並列化パターン

**ingested_urls.txt への追記**: 117件（HIGH 8件、MEDIUM/SKIP 109件）

**備考**:
- `/reference/` 系（BufNMF, HPSS, SpectralShape等）は既存Wikiに概要が存在したため、新規追加は DataSet/KNN/スライシング/NMFリアルタイムに絞った
- `/explore/` 系のPodcast（24件）・アーティスト事例記事は概念的なためSKIP
- MaToMa への示唆として Sonic Anatomy × NMFMatch による音色検出シーン遷移を追記

---

## [2026-04-11] ingest | sc_youtube_eli & sc_sccode ハンドラー

**ソース**: UnifiedScraper DB `sc_knowledge.db` の `sc_youtube_eli` および `sc_sccode` ハンドラー（合計56記事）

**更新したページ**: `sc_livecoding_techniques.md`

**追加した主なテクニック**:
- **Ndef複数レイヤー統合** — `Env.asr().delay(秒数).kr` で個別レイヤーの登場タイミング制御（bass/glass/noise/dm/hh 5層の実践例）
- **Demand.ar + Dseq + fork多重起動** — トリガーごとに周波数を切り替え、fork で時間差起動してポリリズム構築
- **ライブバッファサンプリングエフェクト** — `\go` パラメーターによる録音/ループ再生、ピッチシフト・逆再生・ゲートエフェクト対応

**要旨のみ追記（MEDIUM）**:
- Eli Fieldsteel サンプルローディングパターン（再帰的サンプル辞書構築）
- Paulstretch（超低速ストレッチ、リアルタイム stretch パラメーター変調）
- 量子化ループレコーダー GUI
- FM合成Pbind（Eli Fieldsteel Tutorial 22準拠）
- Abletonアルペジエーター風パターン
- Pbindでのモード/スケール記法
- セルオートマトンによるアルゴリズム作曲（Otomata風）
- Ligeti 100メトロノーム

**ingested_urls.txt への追記**: 56件（HIGH 3件、MEDIUM 9件、SKIP 44件）

**SKIP判定の内訳**:
- YouTube動画（sc_youtube_eli）: 概要ページのみでコード未含（28件）
- sc_sccode: GUIツール・ワンライナー・説明文のみの記事（16件）

**備考**:
- Eli Fieldsteelはコミュニティ内で定評あるSCチュートリアル動画作者だが、DB内の動画はすべて概要ページのみのため実装コード抽出不可
- sccode.orgの記事は短いスニペット中心で、ライブコーディング技法として体系化できるものは3件のみ
- 1-5ih（Ndef valuenoise）は1305行の大規模ライブコーディング実践例で、MaToMaの Sonic Anatomy連動レイヤー制御と相性が良い

---

## [2026-04-12] ingest | Norns エンジンパターン集（Lines forum & GitHub）

**ソース**: Lines forum の Norns エンジン解説スレッド + GitHub monome/dust エンジン実装（30記事）

**更新したページ**: `norns_sc_patterns.md`

**追加した主なパターン**:
1. **CroneEngine ボイラープレート** — `Engine_MySynth : CroneEngine` 命名・`alloc` 初期化フロー・Dictionary + `.keysDo` による全パラメーターのコマンド自動生成
2. **Poll SC → Lua データ転送** — `SpecCentroid.kr.poll` + Lua `poll.set_callback` でリアルタイム解析結果を外部に送信
3. **バスルーティング + 実行順序** — `Group.after` と `addToTail` で信号フロー（voice → efxBus → reverb → out）を保証
4. **Group.set() リアルタイムパラメーター制御** — 発音中の全ボイスに対して `voiceGroup.set(\cutoff, val)` で一括更新

**追記した主なコードパターン**:
- CroneEngine 継承テンプレート（params 辞書 + keysDo 自動コマンド生成）
- SpecCentroid → OSC 送信ループ（Python ブリッジ連携）
- Group/Bus の実行順序制御（voice → efx の順序保証）
- Group.set() による複数 Synth の一括パラメーター変更

**ingested_urls.txt への追記**: 30件（Lines forum スレッド8件、GitHub リポジトリ22件）

**MaToMaへの示唆**:
- Sonic Anatomy 解析結果を Python ブリッジへリアルタイム送信する Poll パターンを Phase 2 に適用可能
- メロディ/ドローン/リズムの各レイヤーを Group 化し、解析結果に応じて `melodyGroup.set(\cutoff, val * 3)` で一括制御
- CroneEngine の Dictionary パターンを TidalCycles OSC パラメーター受信に応用（params 辞書の自動マッピング）

---

## [2026-04-12] ingest | Ableton Learning Synths（design_ableton_learn handler）

**ソース**: UnifiedScraper DB `sc_knowledge.db` の `design_ableton_learn` ハンドラー（70記事）

**更新したページ**: なし（全件SKIP）

**SKIP理由**:

- 69件: Cookieバナーページ（1,000〜2,000文字、実質コンテンツなし）
- 1件: Privacy Policy（8,765文字、法務文書）
- 一部Recipeページ（Old-fashioned computer等）も確認したが、SuperCollider/Tidalに移植可能なコード例や理論的深みが不足

**ingested_urls.txt への追記**: 70件（全件SKIP）

**備考**:

- Ableton Learning Synths は優れた教育教材だが、インタラクティブUI前提の設計でテキスト抽出では価値が失われる
- 基本的なシンセサイザー概念（ADSR・LFO・Filter）は既存Wikiで十分カバー済み

---

## [2026-04-12] ingest | Stanford CCRMA 物理モデリング理論（psych_ccrma handler）

**ソース**: UnifiedScraper DB `sc_knowledge.db` の `psych_ccrma` ハンドラー（1,188記事）

**更新したページ**: `synthesis_physical_modeling.md`

**追加した主なセクション**:

- **学術的背景：Stanford CCRMA（Julius O. Smith III）** — 波動方程式・デジタル導波管・Karplus-Strong・モーダル合成・commuted synthesis・散乱理論の理論的基礎出典を明記

**処理方針**:

- 1,188記事すべてを個別精査せず、**理論的背景の出典**として一括記録
- すでに `synthesis_physical_modeling.md` に含まれている Karplus-Strong・Pluck・Klank・CombL 等の実装の**数学的根拠**として位置づけ
- 実装可能なコード例はほとんど含まれず（学術的な波動方程式・微分方程式・フィルター設計理論が中心）

**主な理論内容**:

- **Digital Waveguide Theory** — 波動方程式の離散化・traveling-wave解法・デジタル導波管の基礎
- **Karplus-Strong Algorithm** — 1983年オリジナル論文の解説 + Extended KS（EKS）のフィルター構成
- **Modal Synthesis** — 共鳴モードの重ね合わせ理論（Klank/Ringzの数学的背景）
- **Commuted Synthesis** — 励振源とレゾネーターの順序入れ替え最適化（ギター・ピアノボディのインパルス応答テーブル化）
- **Scattering Theory** — インピーダンス不連続での反射/透過係数計算（管楽器トーンホール・弦の質量結合）
- **Vocal Tract Modeling (Kelly-Lochbaum)** — 声道の円筒管モデル（1962年、最初期のサンプリング波動モデル）

**CCRMA理論 → SC UGen 対応表を追加**:

| Karplus-Strong → Pluck.ar | Modal Expansion → Klank.ar/DynKlank.ar | Waveguide → CombL.ar/AllpassN.ar | 等

**活用方針を明記**:

- MaToMaでは理論的正確性より**音楽的表現力**を優先
- 厳密な物理モデリングが必要な場合（楽器音の忠実な再現・DSP研究）はCCRMA論文を直接参照

**ingested_urls.txt への追記**: 1,188件（全件処理済みとしてマーク）

**SKIP/MEDIUM/HIGH内訳**:

- **HIGH候補**: 281件（Modal/Waveguide/Resonator/Pluck/Karplus等のキーワード含む）
- **MEDIUM候補**: 903件（理論・数学のみ）
- **SKIP**: 4件（Bibliography/Index/Cookie/Privacy）

**備考**:

- CCRMAは物理オーディオ信号処理（PASP）の世界的権威、Karplus-StrongのEKS論文もここが出典
- Wikiには実装コード例を優先し、数式・証明は出典リンク（<https://ccrma.stanford.edu/~jos/pasp/>）で参照可能とした
- MaToMaでは物理モデリングを「制御されたカオスの一要素」として活用するため、厳密な音響シミュレーションより**有機的な音色変化**の手段として扱う

## [2026-04-12] ingest | Lines (llll.co) — design_lines_synthesis handler

- 更新したページ: `sc_livecoding_techniques.md`
- 追加記事数: 6 件（HIGH）
- ingested_urls.txt 追記: 17 件

### 追加した主な技術・知識

#### License Flash Crash ライブセット
- Phasor ベースの共通時計設計
- Double Modulo によるユークリッドリズム生成
- BufWr.ar によるオーディオレートバッファ録音
- Ndef によるライブモジュール管理
- MouseX.kr によるスイートスポット探索

#### Dronecaster — コミュニティ投稿型エンジン
- DroneDef 設計パターン（hz + amp のみ）
- OSC 経由の動的ロード
- Artisanal Drone Menu（Belong/Hecker/Sachiko/SUNN O)))/Eno/Éliane）

#### Supertonic — Google VAE × SC
- ドラムパフォーマンス VAE（12時間学習）→ 100万リズム生成
- ベイジアン確率テーブル（楽器間のパターン生成）
- Microtonic VST の SC 移植（耳コピ近似）

#### Autoslicer — オンセット検出 × スペクトル分析
- Onset.kr + SendTrig によるリアルタイム検出
- SpecCentroid/SpecFlatness の gated averaging
- リセット可能なアキュムレーター（RunningSum + Latch）
- メタデータ（.csv）付きサンプル保存

#### Engine Thebangs — ワンショット合成
- ラッパー SynthDef + サブグラフファクトリーパターン
- OneShotVoicer によるボイススティーリング（oldest/quietest/random）
- NodeWatcher によるライフサイクル監視

#### fx mod — モジュラーエフェクトシステム
- send/insert スロット設計
- プラグインアーキテクチャ（動的ロード）
- パラレルセンド（send A/B）

### SKIP した記事
- エラー報告・トラブルシューティング: 5 件
- インストール手順のみ: 3 件
- チュートリアル概要・リンク集: 2 件

## [2026-04-12] ingest | Ossia Score Documentation (synth_ossia handler)
- 更新したページ: `synthesis_glitch.md`, `workstation_daw_integration.md`
- 処理記事数: 245件（HIGH: 211件, MEDIUM: 20件, SKIP: 14件）
- 要点:
  - **Bytebeat** — 最小限コードによる合成音楽。整数演算（AND/XOR/シフト）のみで音楽を生成するミニマル言語。Ossia Scoreではタイムライン上で編集・レイヤー再生可能。SC版エミュレーションコード例も追加。
  - **GBAP (Grid-Based Amplitude Panning)** — 規則的スピーカーグリッド上での2D空間パンニング。振幅重み付けで音源位置をリアルタイム制御。MaToMaでは感情価（valence/arousal）をXY軸にマッピングして感情空間の音響化が可能。
  - **Audio Particles** — フォルダー内サンプルをランダムに粒子化して最大128chに散布するグラニュラー合成エンジン。ライブ中のサンプル追加に自動対応。SC生成サンプルとの二重グラニュラーレイヤーに活用可能。
  - **Geo Zones** — 2D空間を複数ゾーンに分割し位置ベースでパラメーター制御。GPS/モーションセンサー連動インタラクティブサウンドスケープに対応。
  - **オーディオエフェクト** — Gamma DSPライブラリベースのFlanger/Echo/Compressor/Limiter/Bitcrushを内蔵。Bitcrushは擬似サンプルレート低下とビット量子化を独立制御可能。
  - OSC/OSCQuery統合により、SC↔Ossia Scoreのリアルタイム双方向通信とパラメーター自動探索が可能。
  - コマンドライン起動（`--no-gui --autoplay`）でヘッドレス実行に対応し、映像インスタレーション向けバックグラウンド動作が可能。

---

## [2026-04-12] ingest | Nick Collins SuperCollider Tutorial (sc_nick_collins handler)

**ソース**: UnifiedScraper DB `sc_knowledge.db` の `sc_nick_collins` ハンドラー（31記事）

**更新したページ**:

- `synthesis_subtractive_stereo.md` — Line.kr によるフィルタースウィープ、Resonz バンドパスフィルター
- `synthesis_additive.md` — 古典波形の倍音レシピ（Sawtooth/Square/Triangle）、Multichannel Expansion パターン
- `sc_realtime_control.md` — mul・add 引数の基礎（スケーリング・DCオフセット・LFO変換）
- `sc_signal_routing.md` — バス番号構造とマルチチャンネル展開、ノードグラフ実行順序の危険性

**追加した主な技術・知識**:

### サブトラクティブ合成基礎（2.1）

- WhiteNoise → LPF の基本フロー（source + filter model）
- `Line.kr(start, end, dur)` による時間ベースのパラメーター変化（カットオフスウィープ）
- `Resonz.ar(source, freq, Q)` バンドパス共振フィルター
- ネスト記法（UGenを他のUGenの引数に直接挿入）の読み方

### 加算合成基礎（2.1）

- `Mix.fill(n, fn)` によるプログラマティックな倍音構築
- Sawtooth波（全倍音、1/n振幅、符号交互）
- Square波（奇数倍音のみ、1/n振幅）
- Triangle波（奇数倍音、1/n²振幅、符号交互）
- Multichannel Expansion（`[freq1, freq2]` → 自動ステレオ展開）
- `Mix(array)` + `Pan2.ar` で配列をモノラル化→定位制御

### mul・add 引数（2.2）

- `mul` — 振幅スケール（y軸拡大縮小）、デフォルトは1.0
- `add` — DCオフセット（y軸平行移動）、デフォルトは0.0
- `*` と `+` 演算子は `mul`・`add` と等価
- LFO出力（-1〜+1）を周波数レンジに変換する典型パターン: `SinOsc.kr(rate, mul: 1700, add: 2000)` → 300〜3700Hz
- `.exprange(min, max)` や `.linlin(in1, in2, out1, out2)` の方が意図が明確

### エンベロープ基礎（3.1）

- `Env.perc(attack, release)` / `Env.linen(a, s, r)` / `Env.adsr(a, d, s, r)` の各エンベロープ形状
- `EnvGen.kr(env, gate, doneAction: 2)` — エンベロープ実行器、`doneAction: 2` でSynth自動解放
- `Line.kr(start, end, dur, doneAction: 2)` — シンプルな直線エンベロープ（Env不要）
- `XLine.kr(start, end, dur, doneAction: 2)` — 指数曲線エンベロープ
- `gate` 引数 + `Env.asr` による sustain ホールド（`.set(\gate, 0)` でリリース開始）
- `releaseNode` と `loopNode` によるエンベロープループ（高速ループでオーディオレート波形生成も可能）

### バス番号体系（6.1）

- デフォルト128バス: 0-7（ハードウェア出力）、8-15（ハードウェア入力）、16-127（内部バス）
- **マルチチャンネル展開ルール**: n チャンネル信号をバス x に出力 → バス x 〜 x+n-1 に展開
- `Out.ar(0, [sig1, sig2])` → バス0とバス1（ステレオ）に自動展開
- `InFeedback.ar(bus, numCh)` — 実行順序問題を回避する遅延読み込み（1サンプル遅延）

### ノードグラフと実行順序（6.3）

- SCサーバーは「ノードグラフ」を上から下へ順番に計算（execution order）
- エフェクトが音源より先に計算されると無音になる（前フレームの値を参照）
- `Group(0)` = RootNode（絶対ルート）、`Group(1)` = default group（全Synthのデフォルト配置先）
- `Synth.head(group, \name)` / `Synth.tail(group, \name)` で明示的順序制御
- `Group.after(sourceGroup)` で音源→エフェクトの順序保証
- `s.queryAllNodes` でノードグラフをデバッグ（または Server ウィンドウで 'N' キー）

**ingested_urls.txt への追記**: 31件（HIGH: 12件、MEDIUM: 8件、SKIP: 11件）

**HIGH記事の内訳**:

- 2.1 Subtractive and Additive Synthesis → `synthesis_subtractive_stereo.md`, `synthesis_additive.md`
- 2.2 Mul and add → `sc_realtime_control.md`
- 3.1 Envelopes → 本Wiki追記（上記）
- 6.1 Buses → `sc_signal_routing.md`
- 6.3 Nodes → `sc_signal_routing.md`

**MEDIUM記事（追記保留、将来的に必要に応じて追加）**:

- 2.3 Controlling Synths — `.set(\param, value)` / `gate` 制御基礎
- 2.5 More Synthesis Examples — FM・AM変調の基本
- 5.1 Buffers and Sound Files — `Buffer.read` / `PlayBuf.ar` / `RecordBuf.ar`
- 6.2 Control Buses — `Bus.control` の使い方
- 6.4 Effects 1 — エフェクトチェーン設計
- 9.3 Probability Distributions — `exprand` / `gauss` / `linrand` 確率分布
- 12.1 FFT — `FFT` / `PV_UGens` の基礎
- 4.x Interaction / GUI 関連記事

**SKIP記事（インストール・環境設定等）**: 11件

**MaToMa への示唆**:

- `Line.kr` による決定的な時間変化と `lfo_rate` による周期的変化を使い分ける（Line: 場面転換、LFO: 呼吸）
- マルチチャンネル展開ルールを理解し、内部バス番号を `Bus.audio(s, numCh)` で自動割り当てする
- ノードグラフの実行順序を必ず明示的に制御（`~sourceGroup` と `~effectGroup` の分離）
- エンベロープループ（`loopNode`）を使うと LFO の代わりに複雑な制御信号を生成できる（Autechre的）

## [2026-04-12] ingest | Tidal Blog TOPLAP + GitHub Gists（E2）

**ソース**:
- `tidal_blog_toplap`: 30記事（TOPLAP blog、2014-2025年）
- `tidal_github_gist`: 11記事（GitHub gists）

**更新したページ**: なし

**処理**: SKIP 41件

**理由**:
- 既存Wiki（`tidal_mini_notation.md`, `tidal_pattern_functions.md`, `tidal_sc_superdirt.md`）とほぼ完全に重複
- tidal_blog_toplap はイベント告知・コミュニティ活動が中心（30件中26件）
- 技術的コード例を含む記事も既存Wikiにカバー済み（whenmod/stack/striate/slowspread/chop 等）
- tidal_github_gist は Strudel（JS版Tidal）またはインストールスクリプトが主体で、MaToMa（SC + Tidal連携）に直接関係しない

**ingested_urls.txt への追記**: 41件（全件URL登録のみ）

**備考**:
- 既存Wikiは2026年初頭に構築済みで、Tidalの基本〜中級機能を十分カバー
- 今後新しいTidal記事を見つけた場合は、「既存Wikiにない関数・パターン」のみを厳選して追記する方針

---

## [2026-04-12] ingest | artist_alvanoto_wikipedia + electronica + experimental_music + ikeda + glitch（E1・5件）

**ソース**: UnifiedScraper DB `sc_knowledge.db` の日本語Wikipedia記事5件
- アルヴァ・ノト（Carsten Nicolai）
- エレクトロニカ
- 実験音楽
- 池田亮司
- グリッチ（用語）

**更新したページ**:
1. `artist_alvanoto_aesthetics.md`
2. `artist_ikeda_aesthetics.md`
3. `generative_music_theory.md`
4. `synthesis_glitch.md`

**追加した主な内容**:

### artist_alvanoto_aesthetics.md
- Carsten Nicolaiの経歴（1965年カール＝マルクス＝シュタット生・旧東ドイツ出身・造園建築学）
- 音楽手法の核心：ループ回路オシレータ・**シーケンサー不使用**・クリック/グリッチを根源的リズム要素として扱う・日常デジタル音の引用
- コラボレーション：池田亮司のCyclo.ユニット、坂本龍一のV.I.R.U.S.
- Raster-Notonレーベル創設（Olaf Bender、Frank Bretschneider）
- エレクトロニカとグリッチの歴史的文脈：1990年代後半ロンドン/ドイツ発祥・Mille PlateauxのClicks & Cutsシリーズ（2000年前後）・OvalのCD読み取りエラーによるグリッチ発見
- MaToMaへの示唆：シーケンサーを使わない即興変調、日常デジタル音の引用、クリックを共鳴体として扱う設計

### artist_ikeda_aesthetics.md
- 人物：1966年岐阜県生、パリ+カタルーニャ拠点、ダムタイプ舞台音楽担当
- 音響アプローチ：超音波・周波数重視の物理的・数学的アプローチ
- 代表作：matrix（2001）・dataplex（2005）・test pattern（2008）・supercodex（2013）
- MaToMaへの示唆：超高域（15kHz+）と超低域（20Hz台）の同時使用、データソニフィケーションのバイナリ変換→素数ポリリズム、ダムタイプ舞台経験と「時間の彫刻」設計

### generative_music_theory.md
- John Cageの「結果を予知できない行為」定義→MaToMaの自律モード正当化
- 歴史的系譜テーブル：Musique concrète（Pierre Schaeffer）・Fluxus・Brian Eno/Robert Fripp・ミニマル音楽（La Monte Young/Terry Riley/Steve Reich）・フリージャズ（Ornette Coleman）
- エレクトロニカとの接続：John Cage → Musique concrète → Brian Eno → Autechre/Alva Noto という系譜が「制御されたカオス」哲学の源流
- MaToMaへの示唆：Musique concrèteの「録音音を素材として扱う」手法はSonic Anatomyサンプルのグレイン化と一致、Brian EnoのテープディレイはLocalInフィードバック設計と直結

### synthesis_glitch.md
- グリッチの語源3説：ドイツ語 glitschen（滑る）・イディッシュ語 gletshn（横滑り）・NASA宇宙飛行士用語（1960年代John Glenn使用）
- バグとグリッチの違いテーブル：bug=再現可能な修正対象、glitch=一時的で美を持つ偶発性
- 関連用語：サーキットベンディング（Reed Ghazala・1960年代）・ビデオゲームグリッチ
- MaToMaへの示唆：語源「滑る」「横滑り」はChaosEngineのFb1・DXクロスフェード・ウェーブフォールディングと一致、NASA「軽微な異常」は「制御されたカオス」哲学そのもの、サーキットベンディングの物理的ランダム性をSCの確率的UGen（CoinGate・TChoose・Gendy3）で再現

**ingested_urls.txt への追記**: 5件
- https://ja.wikipedia.org/wiki/%E3%82%A2%E3%83%AB%E3%83%B4%E3%82%A1%E3%83%BB%E3%83%8E%E3%83%88
- https://ja.wikipedia.org/wiki/%E3%82%A8%E3%83%AC%E3%82%AF%E3%83%88%E3%83%AD%E3%83%8B%E3%82%AB
- https://ja.wikipedia.org/wiki/%E5%AE%9F%E9%A8%93%E9%9F%B3%E6%A5%BD
- https://ja.wikipedia.org/wiki/%E6%B1%A0%E7%94%B0%E4%BA%AE%E5%8F%B8
- https://ja.wikipedia.org/wiki/%E3%82%B0%E3%83%AA%E3%83%83%E3%83%81

**備考**:
- 全4ファイルに「Wikipedia 追加情報」セクションを新規追加（既存内容と重複しない形で構成）
- Wikiの変換義務に従い、単なるコピーではなくMaToMa視点での整理・技術的接続点の明示・「MaToMaへの示唆」サブセクションの追加を実施
- エレクトロニカ記事の歴史的文脈は `artist_alvanoto_aesthetics.md` に統合（Alva Notoとの直接関連が強いため）
- Markdown linter警告（MD022/MD032/MD060等）は機能に影響しないため未修正

---

## [2026-04-12] ingest | E3: Brian Eno + Monoskop + TOPLAP + Cycling74

**ソース**:
- `gen_brianeno` (2記事) — Brian Eno講演録・生成音楽哲学
- `gen_monoskop` (6記事) — サウンドアート百科事典
- `gen_toplap_wiki` (18記事) — TOPLAPライブコーディングWiki
- `gen_cycling74` (10記事) — Max/MSP/Cycling '74記事

**更新したページ**: `generative_music_theory.md`

**新規作成したページ**: `sound_art_taxonomy.md`

**要点**:
- **Brian Eno生成音楽講演（1996）の哲学的要点を構造化** — プロセスが作曲する・アフリカ音楽からの影響・「音楽＝場所」メタファー・Sseyo Koan技術詳細・庭師メタファー・MaToMaへの4層マッピング（Song Form/Section/Phrase/Parameter）
- **サウンドアート用語・アーティスト分類** — Sound art/Sound installation/Sound sculpture/Sound walk/Sonic art/Audio artの定義、Alvin Lucier/Christina Kubisch/Francisco López/Peter Ablinger/David Tudor/Maryanne Amacher/Nicolas Collins/Eliane Radigue/Pauline Oliveros/La Monte Youngの作品とMaToMa接点
- **TOPLAP学術論文6本を参考文献に追加** — Alex McLean（2004 MSc, 2011 PhD）・Sam Aaron（2016 PhD）・Nick Collins（2011論文）・Thor Magnusson・Caroline Jarvald・TOPLAP Manifesto（2004）
- **Cycling '74記事10件は全てSKIP** — jweb/metering/custom UI objects/sfizz~等、Max/MSP特化でSC/Tidal/Pythonスタックと非互換

**HIGH/MEDIUM/SKIP内訳**:
- HIGH: 2件（Brian Eno講演・Monoskop Sound art）
- MEDIUM: 1件（TOPLAP学術論文リスト）
- SKIP: 33件（TOPLAP Wikiナビゲーション・イベント履歴・Cycling '74記事全件）

**ingested_urls.txt への追記**: 3件（HIGH/MEDIUM処理済み）
- https://inmotionmagazine.com/eno1.html
- https://monoskop.org/Series:Sound_art
- https://toplap.org/wiki/Videos,_Articles_and_Papers

**備考**:
- Brian Eno講演の元ファイル（31,227文字、HTML断片・伝記混在）を7セクション構造化（核心定義・歴史的文脈・アフリカ音楽の影響・「音楽＝場所」・Sseyo Koan・庭師メタファー・MaToMa応用）
- `sound_art_taxonomy.md` は既存Wikiの空白領域（サウンドアート分類・空間音響アーティスト・Sound Installationの系譜）を埋めるために新規作成
- TOPLAP Wikiの18記事中16件は管理ページ・イベント履歴・メンバーリストで実装価値なし
- Cycling '74記事は全てMax/MSP特化でSC移植不可（jweb/metering/custom UI objects等）

---

## [2026-04-12] ingest | G4: psych_timing_jp + psych_msp_theory (タイミング心理/Max理論)

**ソース**:
- psych_timing_jp: 339記事（音楽心理学・リズム知覚・タイミング許容閾値）
- psych_msp_theory: 203記事（Miller Puckette "Theory and Techniques of Electronic Music"・Max/MSP理論）

**更新したページ**:
- `design_probability_control.md`
- `generative_music_theory.md`

**分類結果**:
- HIGH: 2件（リズム知覚論文1件、Max/MSP→SC概念対応）
- MEDIUM: 0件（大半が既存Wikiでカバー済み）
- SKIP: 540件（psych_timing_jp: 338件心理学専門記事、psych_msp_theory: 202件重複技術記事）

**追加した主な内容**:

### design_probability_control.md に追加
- **リズム知覚・タイミング許容閾値（音楽心理学）** セクション（新規追加、Related Pages直前）
- タイミング閾値テーブル（0ms/10ms/15ms/20ms/30ms/40ms → 機械的/自然/知覚境界/グルーヴ崩壊/ディレイ/破綻）
- TidalCycles humanization code（`nudge "0 <[-0.01 0.01]*perlin>"`）
- SuperCollider Lag parameter design（lagtime: 0.01-0.04 range）
- Latency tolerance for real-time recording（15ms threshold）
- Chaos Engine rate design（10Hz=natural, 50Hz=glitch, 100Hz=texture）
- Academic background（JND: 5-10ms, IOI tolerance: ±10ms, Groove window: 10-20ms）
- **出典**: 柚木優・音楽心理学研究論文（https://yugo-music.jp/article-10718.html）

### generative_music_theory.md に追加
- **Max/MSP → SuperCollider 概念対応** セクション（新規追加、Related Pages直前、176行追加）
- 10種の概念対応テーブル:
  1. Basic structure (patcher→SynthDef, metro→TempoClock/Impulse.kr)
  2. Signal generation (cycle~→SinOsc.ar, saw~→Saw.ar, etc.)
  3. Envelope/control (line~→Line.kr, adsr~→EnvGen.kr)
  4. Sample playback (groove~→BufRd.ar/PlayBuf.ar)
  5. Delay/reverb (tapin~/tapout~→DelayL.ar/DelayN.ar, etc.)
  6. Filters (lores~→RLPF.ar, hip~→RHPF.ar, etc.)
  7. Polyphony (poly~→Group+Synth management)
  8. Pattern generation (urn→Pshuf/Prand, drunk→Pbrown)
  9. FFT/spectral (fft~→FFT.ar, ifft~→IFFT.ar, etc.)
  10. MIDI/OSC (notein→MIDIdef.noteOn, udpsend→NetAddr.sendMsg)
- Design philosophy comparison（visual vs text-based, real-time vs server/client）
- **出典**: Miller Puckette "Theory and Techniques of Electronic Music" (2007)、Stanford CCRMA docs

**ingested_urls.txt への追記**: 542件（全記事URL一括登録）

**処理方針**:
- psych_timing_jp の339記事中、リズム知覚閾値の実用データ（±10ms groove tolerance等）を抽出した論文1件のみHIGH、残り338件（脳科学・認知科学専門記事）はSKIP
- psych_msp_theory の203記事は個別のMax/MSP技術記事だったが、既存Wiki（`sc_ugen_catalog.md`、`synthesis_*.md`等）とほぼ重複していたため、重複を避けて**概念対応の高レベルマッピングテーブル**のみ新規作成
- Wiki変換義務に従い、Max/MSP→SC対応テーブルは単なる翻訳ではなく「設計哲学の違い」（visual/text, real-time/client-server）まで明記

**MaToMa への示唆**:
- リズム知覚閾値データにより、Chaos Engine の変調速度を「自然（10ms）」「グルーヴ（20ms）」「グリッチ（40ms+）」の3段階に調整可能
- Max/MSP概念対応により、既存のMax/MSPコード例（TOPLAP論文・Cycling '74記事等）をSCに即座に移植可能
- TidalCycles の `nudge` パラメーターと `perlin` を組み合わせることで、機械的グリッドから有機的グルーヴへの微調整が可能（±10ms幅）

