# MaToMa システム設計ドキュメント

> このドキュメントはSPEC.mdの抽象的なコンセプトを、具体的な設計決定に落とし込んだもの。
> 実装の前に参照し、「全体と矛盾していないか」を確認するための地図として使う。
> 更新日: 2026-03-29

---

## 美学的ビジョン

2つのアーティスト軸の対話として音楽を作る。

| 軸 | アーティスト | 音の性格 |
|----|------------|---------|
| Space層 | Tim Hecker / Aoyama Michiru | 倍音の霧・粒子の場・空間を包む温かさ |
| Event層 | Alva Noto / Autechre | 不規則なリズム・耳を刺す打撃・機械的カオス |

シーンはこの2層の**比率と強度**を定義する。

```
深淵・浮遊 → Space層が支配する（静かな霧）
緊張・崩壊 → Event層が前に出てくる（稲妻が走る）
```

---

## 音源の構成

### Space層

#### Drone
- **役割**: 空間全体を包む倍音の基盤
- **設計方針**: 発振器から「描く」のではなく、共鳴から「育てる」
- **素材**: PinkNoise → Klank（共鳴フィルターバンク）で特定倍音を共鳴させる
- **処理**: Saturation（温かみ）→ Shimmer Reverb（浮遊感）
- **制御**: カオスエンジン（Python）がパラメーターをゆっくりドリフトさせる。Tidalは関与しない

#### Granular
- **役割**: Droneを粒に分解してテクスチャの霧を作る
- **素材**: Droneのリバーブ後（ウェット）信号をリアルタイムでサンプリング
  - 残響ごと粒になるため、すべてが溶け合う（Hecker的密度）
- **将来**: 倍音豊かな外部サンプルも素材として使えるようにする
- **制御**: Tidalがノートイベント（音程・タイミング・密度）を送る。カオスエンジンが粒の揺らぎを担当

### Event層

#### Rhythmic/Percussive
- **役割**: 不規則なリズム・打撃音。Autechre / Alva Noto的な耳への刺激
- **設計方針**: 規則的なビートではなく、確率的に配置された打撃
- **制御**: TidalCycles（カスタムOSC）+ Turing Machine（パターン記憶・変異）

**音源は全種類を並列に持ち、組み合わせて使う：**

| 音源 | 特徴 | 美学的役割 |
|-----|------|----------|
| **サンプリング + Granular** | GrainBufで粒に分解。spray=0で規則的、spray=1でランダム | リズムの骨格。素材を崩して抽象化 |
| **Klank（金属共鳴）** | インパルス→非整数倍音フィルターバンク | Alva Noto的な金属グリッド |
| **FM Percussion** | fm_index>5で倍音が急変する打撃音 | Autechre的な予測不能な音色変化 |
| **Spring / Ringz** | 物理的なバネ・単一共鳴フィルター | 有機的だが金属的な中間的音色 |
| **HenonC / LatoocarfianC** | カオス写像を音源として直接使用 | 機械が壊れているような異物感 |

Tidalが「どの音源を・いつ・どの音程で」を決め、
Turing MachineのPROBが「どれが鳴るか・どう変異するか」を制御する。

---

## シグナルルーティング

```
[PinkNoise]
    ↓
[Klank] ─ 倍音共鳴
    ↓
[Saturation] ─ 温かみ
    ↓
[Shimmer Reverb] ─ 浮遊感
    ↓
[Bus: Wet Drone] ──────────────────────┐
    ↓                                  │
[Granular] ─ Wet Droneを粒に分解       │
    ↓                                  ↓
[個別Reverb]              [個別Reverb]
    ↓                                  ↓
    └─────────────┬────────────────────┘
                  │
[Rhythmic] ← Tidal（カスタムOSC）
    ↓
[個別Reverb]
    ↓
    └─────────────┤
                  ↓
          [Effect Layer]
            ├ Global Delay（奥行き）
            ├ Spectral（Freeze / Blur）
            ├ Wavefolder（倍音追加）
            └ Feedback Loop（自律的なエコー）
                  ↓
            [スピーカー]
```

### 設計決定の根拠

| 決定 | 内容 | 理由 |
|-----|------|------|
| Granularの素材 | Droneのリバーブ後 | 残響ごと粒にすることでHecker的な霧の密度が生まれる |
| リバーブ | 各層に個別 + Effect Layerで統合 | 層ごとの空間を保ちつつ、全体の質感を一括で変えられる |
| Spectral | Effect Layer内のエフェクト | 独立した音源ではなくミックスの質感を調整するツール |
| Wavefolder | Effect Layer内 | 倍音の複雑さをエフェクトとして後から追加できる |
| Feedback Loop | Effect Layer内 | 音が自律的にエコーし、予測不能な変化が生まれる |

---

## エフェクト層（Effect Layer）

### 各層の個別Reverb（インサート）
- Drone: 広大な空間（room大・damp小）
- Granular: 中程度（粒の形が残る程度）
- Rhythmic: 短め（打撃の輪郭を保つ）

### Effect Layer（グローバル）
ライブ中にユーザーが操作する場所（UIの最下部に独立配置）

| エフェクト | 役割 | ユーザー操作 |
|-----------|------|------------|
| Global Delay | 空間的な奥行き・反復 | Time / Feedback |
| Spectral Freeze | 瞬間を凍らせる | Freeze量 |
| Spectral Blur | 周波数を拡散させる | Blur量 |
| Wavefolder | 倍音を歪みで追加 | Drive量 |
| Feedback Loop | 自律的なエコー・うなり | Amount / Rate |

---

## 制御システム

### 4つの時間レイヤーと担当コンポーネント

| レイヤー | 時間スケール | 担当 |
|---------|------------|------|
| Song Form | 数分単位 | **人間** → ブラウザUIでシーン切り替え |
| Section | 8〜32小節 | **シーンマネージャー**（Python）→ DNAプロファイルでMarkov上位層の挙動を規定 |
| Phrase | 1〜4小節 | **Multi-timescale Algorithm 中位・下位層** → コード度数・リズム・旋律を自動生成 |
| Parameter | ミリ秒〜秒 | **Multi-timescale Algorithm** → SCパラメーター（音色・テクスチャー）をOSCで送信 |

### Multi-timescale Algorithm（Python）

Sonic Anatomyで抽出したパターンを参照しながら、TidalCyclesのスコアとSCパラメーターの両方を自律的に生成・進化させる3層構造。

| 層 | 時間スケール | アルゴリズム | 出力 |
|---|------------|------------|------|
| 上位層 | 64拍単位 | Markov連鎖 | 調性・スケール |
| 中位層 | 小節単位 | Fractal / Markov | コード度数・和声リズム |
| 下位層 | フレーズ単位 | L-System | リズム・旋律装飾 |

詳細設計（引力点・Gravity Matrix・Dynamic Clamping 等）は `docs/design/autonomous_evolution.md` 参照。

### メロディ6層制御（Melodic Integrity）

アルゴリズム生成時の調性崩壊を防ぐための6層制御階層。
Layer 1（調性コンテキスト）→ Layer 6（アーティキュレーション）の順に制約を適用し、
最終出力は必ずScale Quantizerを通過する。詳細は `docs/design/autonomous_evolution.md` 参照。

### シーンマネージャー（Python）

- シーン = **DNAプロファイル**（Markov挙動・引力点・SCプロファイルの束）
- 具体的な音の値ではなく、アルゴリズムが動ける**空間の形**を定義する
- 5シーン: `warm` / `void` / `vast` / `lost` / `peak`
- シーン遷移時: DNAプロファイルが切り替わり、アルゴリズムの挙動がスムーズに移行する

### TidalCycles

- Multi-timescale AlgorithmがTidalスコアをリアルタイムで生成する（手書き `.tidal` ファイルは使わない）
- カスタムOSCでMaToMaのSynthDefを直接叩く（SuperDirt経由ではない）
- Granularへのノートイベント（音程・タイミング・密度）を担当

### ブラウザUI

```
[パターン選択パネル]  ← Sonic Anatomyカタログから人間が選択
SCENE: [warm] [void] [vast] [lost] [peak]
BPM / DRIVE / FREEZE / MASTER（グローバル操作）
```

- シーン切り替え（Song Formレベルの操作）
- エフェクトパラメーターのリアルタイム操作（即時反映）
- アルゴリズムの現在状態の可視化

---

## シーンの定義（Section層）

シーンは「DNAプロファイル」として定義する。具体的な音の値ではなく、
Multi-timescale Algorithmが動ける**空間の形**（Markov挙動・引力点・SCプロファイル）を束にしたもの。

```
シーン例「void」:
  Markov挙動:
    調性変化確率: 低（長時間同じスケールに留まる）
    コード度数: I中心（解決感・静止感）
  
  Space層の比率: 高（Droneが支配）
  Event層の比率: 低（Rhythmicは控えめ）

  引力点:
    Drone共鳴周波数: 低域（41Hz中心）
    Granular密度: 低（粒が疎）
    Reverbルームサイズ: 0.95（広大な空間）
  
  SCプロファイル:
    mutation_rate: 遅め
    chaos_width_max: 0.65
```

詳細なシーンDNAは `docs/design/autonomous_evolution.md` 参照。

---

## 参照アーキテクチャ

| 参照元 | 採用する概念 | MaToMaでの用途 |
|-------|------------|--------------|
| **Norns / Anvil** | エフェクトバスパターン | Effect Layerの実装構造 |
| **Norns / SpecCentroid** | スペクトル重心をOSCでPythonへ | 音の明るさをUIに可視化 |
| **VCV Rack / Turing Machine** | シフトレジスタ型確率変異 | Multi-timescale AlgorithmのL-System下位層に吸収 |
| **Tom Whitwell / Dejavu** | 過去状態の記憶と確率的回帰 | Multi-timescale Algorithmの引力点設計に反映 |
| **co34pt** | Pbjorklund2ユークリッドリズム | Tidal + Rhythmic層の設計 |
| **miSCellaneous_lib / Fb1** | 非線形ODE（Lorenzアトラクター等） | SCパラメーター制御（Multi-timescale Algo下位） |

---

## 未決定事項

実装に入る前に決める必要があるもの：

- [x] Rhythmic/Percussiveの音源: 全種類を並列に持ち組み合わせる（Sampling+Granular / Klank / FM / Spring / HenonC）
- [ ] Granularで使う外部サンプルの選定基準（倍音豊かな素材とは何か）
- [ ] TidalとMaToMaのOSCプロトコル仕様（アドレス・引数の形式）
- [ ] ブラウザUIのレイアウト（エフェクトパネルとアルゴリズム状態可視化の配置）
- [ ] Multi-timescale AlgorithmからTidalへのスコア送信プロトコル（リアルタイム更新の仕組み）
- [ ] SCENEのエネルギー操作コントロールの詳細（SCENE切り替え時のパラメーター詳細は未設計）

---

## 実装の優先順位（未確定）

```
Phase 1: 音源の骨格
  Drone（Klankベース）の実装
  Granular（Droneのウェット信号を素材）の実装
  共有リバーブバスの実装

Phase 2: 制御システム
  Multi-timescale Algorithm（Python）の基礎実装
  シーンマネージャー（DNAプロファイル）の実装
  SC間のOSC接続・ブラウザUIとのWebSocket接続

Phase 3: Event層 + アルゴリズム統合
  TidalとMaToMaのカスタムOSC接続
  Rhythmic/Percussive音源の実装
  Sonic Anatomyパターンとの接続

Phase 4: 洗練
  シーンDNAの調整・追加
  メロディ6層制御のチューニング
  音の磨き込み（ここからが無限）
```
