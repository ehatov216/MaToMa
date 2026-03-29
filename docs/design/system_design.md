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
| Section | 8〜32小節 | **シーンマネージャー**（Python）→ 引力点と揺れ幅を設定 |
| Phrase | 1〜4小節 | **TidalCycles** → リズム・パターン・音程 |
| Parameter | ミリ秒〜秒 | **カオスエンジン**（Python）→ 音色のドリフト |

### 自律変化の4層構造

「Tidalがパラメーターを動かすだけ」では単純すぎる問題を解決するため、
自律変化を4つの異なるメカニズムで重ねる。

```
Fb1（SC内部）          … ミリ秒〜秒：数学的カオスで音色が揺れる
Turing Machine（SC内部）… ステップ単位：パターンが記憶しながら変異する
Chaos Engine + Dejavu  … 秒〜分：記憶付きのゆっくりしたドリフト
Tidal                  … フレーズ：リズム・確率・パターン
```

#### Fb1（SC内部カオス）
- `miSCellaneous_lib` の非線形ODE合成（Lorenz / Duffing / VanDerPol）
- 音色パラメーター（フィルター・音程・密度）を数学的カオス方程式で変化させる
- Droneの共鳴周波数やGranularの粒密度をFb1が駆動
- 「短期は予測不能、長期は境界内」= SPEC.mdの決定論的カオスの直接実装

#### Turing Machine（SC内部・Rhythmic層）
- 参照元: VCV Rack / 2020 Semi Modular のTuring Machineモジュール
- 16ビットのシフトレジスタがリズムパターンを記憶する
- `PROB`パラメーター1つで変化の量を連続制御
  - PROB=0%: 同じループが繰り返される（ミニマル）
  - PROB=50%: 徐々に変化（Autechre的）
  - PROB=100%: 完全ランダム（崩壊）
- シーンと連動: 深淵→PROB低め、崩壊→PROB高め
- Tidalのユークリッドリズム（Pbjorklund2）と組み合わせる

#### カオスエンジン + Dejavu（Python）
- 参照元: Tom Whitwellの「Dejavu」パターン
- 各パラメーターの過去8世代の値を記憶する
- 確率30%で「過去のある瞬間の値」に戻る → 「記憶がある」カオスになる
- 純粋なランダムドリフトより「あの音に戻ってきた」という感覚が生まれる
- Bounded Random Walk + Dejavu = 引力点に引き寄せられながら、過去にも引き寄せられる
- OSC経由でSCにパラメーターを送り続ける（秒〜分スケール）
- ブラウザUIに現在のカオス状態を表示できる
- シーンの境界値（ceiling/floor）を守る役割も担う

### シーンマネージャー（Python）
- シーン = 各パラメーターの「引力点」と「揺れ幅の上限」の束
- 具体的な値ではなく**境界**を定義する
- シーン遷移時: すべてのパラメーターの引力点を新しいシーンの値に向けてスムーズに移行

### TidalCycles
- カスタムOSCでMaToMaのSynthDefを直接叩く（SuperDirt経由ではない）
- Granularへのノートイベント（音程・タイミング）を担当
- Rhythmic/PercussiveのパターンをGranularに送る

### ブラウザUI
- シーン切り替え（Song Formレベルの操作）
- エフェクトパラメーターのリアルタイム操作（即時反映）
- 制御モード ↔ 自律モードの切り替え
- カオスエンジンの現在状態の可視化

---

## シーンの定義（Section層）

シーンは「具体的な音の値」ではなく「境界と引力点」を持つ。

```
シーン例「深淵」:
  Space層の比率: 高（Droneが支配）
  Event層の比率: 低（Rhythmicは控えめ）

  Drone:
    共鳴周波数の引力点: 低域（41Hz中心）
    chaos_width_max: 0.65
    mutation_rate: 遅め

  Granular:
    density_attractor: 低（粒が疎）
    position_range: 広い

  Reverb:
    room_attractor: 0.95（広大な空間）
```

---

## 参照アーキテクチャ

| 参照元 | 採用する概念 | MaToMaでの用途 |
|-------|------------|--------------|
| **Norns / Anvil** | エフェクトバスパターン | Effect Layerの実装構造 |
| **Norns / SpecCentroid** | スペクトル重心をOSCでPythonへ | 音の明るさをUIに可視化 |
| **VCV Rack / Turing Machine** | シフトレジスタ型確率変異 | Rhythmic層のパターン自律進化 |
| **Tom Whitwell / Dejavu** | 過去状態の記憶と確率的回帰 | Chaos Engineの記憶付きドリフト |
| **co34pt** | Pbjorklund2ユークリッドリズム | Tidal + Rhythmic層の設計 |
| **miSCellaneous_lib / Fb1** | 非線形ODE（Lorenzアトラクター等） | 音色の数学的カオス変化 |

---

## 未決定事項

実装に入る前に決める必要があるもの：

- [x] Rhythmic/Percussiveの音源: 全種類を並列に持ち組み合わせる（Sampling+Granular / Klank / FM / Spring / HenonC）
- [ ] Granularで使う外部サンプルの選定基準（倍音豊かな素材とは何か）
- [ ] TidalとMaToMaのOSCプロトコル仕様（アドレス・引数の形式）
- [ ] ブラウザUIのレイアウト（特にエフェクトパネルと可視化の配置）

---

## 実装の優先順位（未確定）

```
Phase 1: 音源の骨格
  Drone（Klankベース）の実装
  Granular（Droneのウェット信号を素材）の実装
  共有リバーブバスの実装

Phase 2: 制御システム
  カオスエンジン（Python）とSC間のOSC接続
  シーンマネージャーの実装
  ブラウザUIとのWebSocket接続

Phase 3: Event層
  TidalとMaToMaのカスタムOSC接続
  Rhythmic/Percussive音源の実装

Phase 4: 洗練
  シーンの調整・追加
  音の磨き込み（ここからが無限）
```
