# Claude Code Instructions

## 出力言語

**すべての出力は日本語で行うこと。**

コード・コメント・変数名・ファイル名はこの限りではないが、
ユーザーへの説明・回答・要約・エラーメッセージの解説など、
テキストとして出力するものはすべて日本語を使用する。

---

## コミュニケーションスタイル

### 前提：ユーザーの技術的背景
- プログラミング・SuperCollider・音響合成の専門知識はほとんどない
- 対話を重ねるごとに理解が深まる「学習伴走型」を目指す

### 話し方の原則

1. **「何をしているか」を日常言語で先に説明し、専門用語は後から添える**
   - OK: 「音の明るさを測る値が低い（こもった音）ので、フィルターを調整します。これを spectral centroid・RLPF と呼びます」

2. **技術用語は初出時のみ日常語で補足し、2回目以降は定着を前提に使う**

3. **抽象的な概念は音の体験に例える**
   - 例: 「リバーブ = お風呂で声を出したときの響き」

4. **一度に伝える情報量を絞り、要点から入る**

---

## SuperCollider の操作方法

**ユーザーは原則 SuperCollider を直接操作しない。**

Claude が `sclang`（SuperCollider の言語インタープリタ）をコマンドラインから呼び出し、
SuperCollider を操作する。

- SCコードを実行するときは `sclang` コマンドを Bash ツールで直接実行する
- ユーザーに「SuperCollider を開いて実行してください」と指示しない
- テスト音を鳴らしたら、必ず停止してから次の処理へ進む（`s.freeAll` など）

---

## プロジェクト参照ルール

### セッション開始時に必ず行うこと
1. `SPEC.md` を読み、プロジェクトの目的・制約・コアパイプラインを確認する
2. `docs/CODEMAPS/` が存在する場合は読み、実装の現在地を把握する
3. `feedback/knowledge.md` を読み、過去の試行で得られた法則を把握する
4. `feedback/logs/` 内の直近3ファイルを確認し、前回セッションの文脈を把握する

### 音響系コードを書く前に必ず行うこと（MANDATORY）

> SuperCollider・TidalCycles・その他の音響/音楽生成コードすべてに適用する。

1. **ユーザーの意図を `feedback/knowledge.md` の「言葉とパラメーターの対応」で確認する**
2. **`knowledge/rag/sources/` の該当ファイルを Read ツールで直接読む**（先行技術・コードスニペットを必ず確認してから実装する）

   | モジュール／意図 | 読むファイル |
   |----------------|------------|
   | ドローン・アンビエント・持続音 | `synthesis_ambient_drone.md` |
   | グレイン・粒状・断片的 | `synthesis_granular.md` |
   | FM・金属的・倍音豊か | `synthesis_fm.md` |
   | スペクトル・周波数変換・グリッチ | `synthesis_spectral.md` |
   | サブトラクティブ・フィルター・クラシックシンセ | `synthesis_subtractive_stereo.md` |
   | 加算合成・倍音積み上げ | `synthesis_additive.md` |
   | ウェーブテーブル | `synthesis_wavetable.md` |
   | 物理モデリング・弦・管 | `synthesis_physical_modeling.md` |
   | パーカッション・打楽器 | `synthesis_percussion.md` |
   | カオス・非線形・Fb1・DXクロスフェード・ウェーブフォールド | `plugins_sc_quarks.md` |
   | 音声解析・ML・スペクトル特徴量・HPSS・ニューラルネット | `plugins_flucoma.md` |
   | DAW連携・OSC・Ossia Score・TouchDesigner・VCV Rack | `workstation_daw_integration.md` |
   | Tidalパターン記法・ミニ記法・ユークリッド | `tidal_mini_notation.md` |
   | Tidalパターン関数・every・perlin・degrade・トランジション | `tidal_pattern_functions.md` |
   | Tidal×SC連携・SuperDirt・カスタムSynthDef・エフェクト | `tidal_sc_superdirt.md` |
   | チューリングマシン・シフトレジスタ・Dejavu的ランダム | `synthesis_turing_machine.md` |
   | Orca連携・2DグリッドライブコーディングとSC/Tidal制御 | `control_orca_integration.md` |
   | 確率制御設計・パラメーターロック・ラチェット・ポリリズム | `design_probability_control.md` |
   | Norns SCパターン・ParGroup・SelectX・KS弦・SpecCentroid | `norns_sc_patterns.md` |
   | UGenカタログ・発振器・フィルター・FFT・パンニング一覧 | `sc_ugen_catalog.md` |
   | Pbind/Pdef/Ndef・パターンクラス・スケール・ProxySpace | `sc_pattern_system.md` |
   | ユークリッドリズム・Pwrand・normalizeSum・レイヤリング | `sc_livecoding_techniques.md` |
   | Autechre美学・Dry/Wet判断・FM哲学・ストカスティック設計 | `artist_autechre_aesthetics.md` |
   | Autechre制作技法・FM実装・FDN・ユークリッドリズム・機材詳細 | `artist_autechre_production.md` |
   | Burial美学・非グリッドリズム・Foley・ハウントロジー・Wet霧 | `artist_burial_aesthetics.md` |
   | Alva Noto美学・還元主義・120bpmグリッド・グリッチ・沈黙設計 | `artist_alvanoto_aesthetics.md` |
   | Tim Hecker美学・制御された崩壊・グラニュラー・スペクトル処理・リアンプ | `artist_timhecker_aesthetics.md` |
   | GitHubドローン事例・Pseed・フィードバックループ・多声ノイズ | `github_drone_generators.md` |
   | GitHubグラニュラー事例・GrainBuf・Warp1・スキャッター設計 | `github_granular_synthesizers.md` |

3. **ユーザーの日本語フィードバックを英語のSCテクニックに変換してから実装する**
   - 変換表は `feedback/knowledge.md` の「言葉とパラメーターの対応」を参照
   - 変換表にない語は `feedback/vocabulary.md` の「日英マッピング」を参照

4. **参照したファイルのコード例を基にして実装する（ゼロから書かない）**
   - すでに出来上がっている技術・スニペットがあれば、それを流用・改変する形で進める
   - 新規実装は RAG にない場合のみ許可

### フィードバックセッション中のルール
- 変更前に「仮説：〇〇だからこうする」を1行で述べる
- ユーザーの評価（良くなった／変わってない／悪くなった）を受けたら `feedback/logs/YYYY-MM-DD.json` に即記録する
- 「変わってない」が2回続いたら別のアプローチを提案する
- **「良くなった」が1回でも確認されたら、使ったSCテクニックを `feedback/knowledge.md` の「言葉とパラメーターの対応」に即記録する**（従来の「3回」ルールを廃止）
- 詳細は `feedback/README.md` を参照

### 実装時のルール
- 実装内容が `SPEC.md` の制約・コンセプトと矛盾しないか常に確認する
- 機能を追加・削除したら `/update-codemaps` を実行して `docs/CODEMAPS/` を更新する
- `SPEC.md` に追記していいのは「コードを読んでも分からないWhy」だけ
- `SPEC.md` が200行を超えそうになったら、超えた部分を `docs/adr/` に移すことを提案する
