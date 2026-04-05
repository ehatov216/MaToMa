# MaToMa 自律進化システム 設計書

> 作成: 2026-03-30
> 更新: 2026-03-30（TidalCycles統合レイヤーを追加）
> ステータス: 設計完了・未実装
> 関連SPEC: SPEC.md § コアコンセプト：制御されたカオス

---

## 1. 設計哲学：羊飼いモデル

### なぜこの設計か

現状のMaToMaは「パラメーター操作型シンセサイザー」と同じ構造になっている。
ユーザーが触らない限り音は変化しない。これは SPEC.md の「パラメーターが自律的にゆっくり変化し続ける」というコンセプトと矛盾する。

### 羊飼いモデルとは

プレーヤーは「演奏家」でも「庭師」でもなく**羊飼い**として設計する。

- 羊（音）は自律的に動く意志を持っている前提から始まる
- 羊飼いは群れの方向を少し修正するだけで、一匹一匹の動きは制御しない
- 庭師は植えた植物に責任を持つが、羊飼いは羊が羊として動く自由を信頼する

### 羊飼いの道具（許容される操作）

| 道具 | 音楽的役割 |
|------|-----------|
| 犬（シーン切り替え） | 群れの方向を根本的に変える |
| 笛①②③（3本のスライダー） | 全体に合図を送る |
| 牧草地の柵（Limiter/Clip） | 自動。ユーザーは操作しない |

### 設計判断の基準

新機能を追加するとき、常にこの問いで判断する：
> 「これは羊飼いの道具か？それとも羊を直接操る鎖か？」

鎖が増えるほどシステムは元のシンセサイザーに戻る。

---

## 2. 全体アーキテクチャ：5層構造（Tidal統合版）

```
┌─────────────────────────────────────────────────┐
│  Layer 3: 人間の制御（マクロ境界）                 │
│  シーン選択 / CHAOS / DENSITY / TENSION / BPM    │
│  「動ける範囲」と「どのパターンを使うか」を設定する  │
└──────────────┬────────────────┬─────────────────┘
               │                │
        シーン選択          CHAOSパラメーター
               │                │
               ▼                ▼
┌─────────────────────────────────────────────────┐
│  Layer T: TidalCycles（秩序の担い手）             │
│  ドラムパターン / コード進行 / ルートノート          │
│  「音楽的な骨格（ORDER）」を定義する               │
│                                                 │
│  CHAOS低: パターンをほぼそのまま再生               │
│  CHAOS中: degradeBy / sometimes でパターンを間引く │
│  CHAOS高: every N (fast 2) / jux rev で崩す      │
└───────────────────────┬─────────────────────────┘
                        │ OSC（note / trigger / timing）
                        ▼
┌─────────────────────────────────────────────────┐
│  Layer 2: シーンDNA（チューリング遺伝子 = B）      │
│  Tidalのノートを受け取り、微細変異を加える           │
│  「Tidalが決めた方向の周辺を漂う」                 │
└───────────────────────┬─────────────────────────┘
                        │ アトラクター値（中心値）
                        ▼
┌─────────────────────────────────────────────────┐
│  Layer 1: 自律代謝（呼吸する有機体 = A）           │
│  LFNoise3階層がパラメーターを常時揺らす            │
│  「その周辺でどう揺れるか」を決める                 │
│  + 安全制御（Limiter / LeakDC / Clip）           │
└───────────────────────┬─────────────────────────┘
                        │ 最終パラメーター値
                        ▼
┌─────────────────────────────────────────────────┐
│  Layer 0: 音響合成（既存SynthDef）                │
│  Drone / Granular / Percussion / Effects        │
└─────────────────────────────────────────────────┘
```

### 各レイヤーの責任

| レイヤー | 何を決めるか | 誰が決めるか | 時間スケール |
|---------|-----------|-----------|-----------|
| Layer 3 | 動ける範囲・使うパターン | ユーザー | 任意（操作時のみ） |
| Layer T | 音楽的骨格（リズム・コード） | Tidalパターン定義 | 小節・フレーズ単位 |
| Layer 2 | Tidalの周辺を漂う | シーンDNA（自律） | 数分単位 |
| Layer 1 | その周辺でどう揺れるか | LFNoise（自律） | 秒〜数十秒単位 |
| Layer 0 | 実際に音を出す | 既存SynthDef | ミリ秒〜秒 |

---

## 3. Layer T 詳細設計：TidalCycles（秩序の担い手）

### 概念：骨格があるから崩れが聴こえる

TidalCyclesはMaToMaの「音楽的な秩序（ORDER）」を担う。
骨格があるからこそ、CHAOSがそれを崩したとき「崩れた」と聴こえる。
完全ランダムでは崩れたとも感じない。

これはジャズのコード進行と同じ原理：コードは固定、即興は自由、調性は守られる。

### Tidal環境（Sonic Anatomyから継承）

Sonic Anatomyプロジェクト（`/Users/yusuke.kawakami/dev/Sonic Anatomy`）で
構築済みの環境をベースにする。

```
接続方式:
TidalCycles → SuperDirt → SC SynthDef
             (OSC port 57120)

実績:
- setcps (BPM/60/4) でテンポ設定
- n "<g'min ...>" でコード進行
- s "matoma_drone" のようなカスタムSynthDefを呼び出す
```

### シーンごとのTidalパターン定義

各シーンは `.tidal` ファイルとして定義する。
SCENEを切り替えるとTidalが別のパターンブロックに移行する。

#### ambient.tidal（骨格例）
```haskell
-- BPM設定
setcps (72/60/4)

-- ドラム骨格: 疎なキック、ほぼ無音に近い
d1 $ s "matoma_kick? ~ ~ ~  ~ ~ matoma_kick? ~"
   # gain 0.6

-- コード進行: Cm → Eb → Bb → Fm（4小節で一周）
d2 $ n "<c3'min eb3'maj bb2'maj f3'min>"
   # s "matoma_drone"
   # sustain 4.0

-- ベースルート: ゆっくり変化するルートノート
d3 $ n "<c2 eb2 bb1 f2>"
   # s "matoma_granular"
   # sustain 2.0
```

#### tension.tidal（骨格例）
```haskell
setcps (92/60/4)

-- ドラム: 密度が上がる、不規則なアクセント
d1 $ s "matoma_kick ~ matoma_snare ~  matoma_kick matoma_kick ~ matoma_snare"
   # gain 0.75

-- コード: 緊張感のある音程（半音・tritone含む）
d2 $ n "<c3'dim f#3'dim eb3'aug b2'dim>"
   # s "matoma_drone"
   # sustain 2.0

d3 $ n "<c2 f#1 eb2 b1>"
   # s "matoma_granular"
   # sustain 1.5
```

### CHAOSパラメーターがTidalに作用する方法

CHAOSの値に応じて、Python側がTidalのパターンを動的に変形する。

```
CHAOS = 0.0〜0.3（低）: 骨格をほぼそのまま再生
  → そのままのパターン

CHAOS = 0.3〜0.6（中）: 音を間引き、たまに変形
  → degradeBy 0.2
  → sometimesBy 0.1 (jux rev)

CHAOS = 0.6〜0.85（高）: 大きく崩す
  → degradeBy 0.4
  → every 3 (fast 2)
  → sometimesBy 0.3 (rev)

CHAOS = 0.85〜1.0（限界）: 骨格が判別ギリギリ
  → degradeBy 0.6
  → every 2 (fast 2)
  → jux (fast 1.5)
```

実装イメージ（Python側でTidalコードを動的生成）：
```python
def apply_chaos_to_tidal(pattern: str, chaos: float) -> str:
    if chaos < 0.3:
        return pattern
    elif chaos < 0.6:
        return f"degradeBy {chaos * 0.5:.2f} $ sometimesBy {chaos * 0.15:.2f} (jux rev) $ {pattern}"
    elif chaos < 0.85:
        return f"degradeBy {chaos * 0.6:.2f} $ every 3 (fast 2) $ {pattern}"
    else:
        return f"degradeBy {chaos * 0.65:.2f} $ every 2 (fast 2) $ jux (fast 1.5) $ {pattern}"
```

### MaToMa SynthDefのTidal対応

既存のSynthDef名をSuperDirtに登録することで、
Tidalから `s "matoma_drone"` のように呼び出せる。

| Tidalでの名前 | 対応するMaToMa SynthDef |
|-------------|------------------------|
| `matoma_drone` | `\matoma_drone`（drone.scd） |
| `matoma_granular` | `\matoma_granular`（granular.scd） |
| `matoma_kick` | `\matoma_kick`（percussion.scd） |
| `matoma_snare` | `\matoma_snare`（percussion.scd） |

### 未解決：Tidal→SC接続方式の選択

**選択肢A: SuperDirt経由（推奨・実績あり）**
- Sonic Anatomyで動作確認済みの方式
- Tidalの全機能が使える
- MaToMaのSCサーバーとSuperDirtを共存させる必要がある
- ポート競合の可能性あり（要調査）

**選択肢B: 直接OSC**
- TidalからMaToMaのOSCdef（port 57200）に直接送る
- SuperDirtが不要でシンプル
- Tidalの一部機能（エフェクトチェーン等）が使えなくなる

→ **Phase 3の実装時に判断する**

---

## 4. Layer A 詳細設計：呼吸する有機体

### 概念

生き物の身体のように、3つの時間スケールで常に微細変化する。
ユーザーは気づかないうちに音が変化しているが、「誰かが操作した」とは感じない。

### 3階層の定義

#### A1: 呼吸（Breathing）
```
速度:    0.01~0.05 Hz（20〜100秒周期）
担当:    feedback_amt / room_size / overall level
振れ幅:  中心値の ±10〜20%
感覚:    肺が膨らんでは縮む、極めてゆっくりしたうねり
```

#### A2: 心拍（Heartbeat）
```
速度:    0.1~0.5 Hz（2〜10秒周期）
担当:    cutoff / reverb_mix / grain density
振れ幅:  中心値の ±20〜30%
感覚:    規則正しくはないが、リズムがある変化
```

#### A3: 神経（Neural）
```
速度:    1~5 Hz（0.2〜1秒周期）
担当:    micro-pitch detune / pan / grain spray
振れ幅:  中心値の ±3〜8%（非常に微細）
感覚:    体の細かい震え。意識しないと気づかない
```

### SuperCollider実装イメージ

```supercollider
// Layer Aの実装パターン（SynthDef内に埋め込む）
// centerVal: Layer Bから受け取るアトラクター値
// breathSpeed/Depth, heartSpeed/Depth, neuralSpeed/Depth: シーンDNAから来る

var breath  = LFNoise1.kr(breathSpeed).range(
                centerVal * (1 - breathDepth),
                centerVal * (1 + breathDepth));

var heart   = LFNoise1.kr(heartSpeed).range(
                centerVal * (1 - heartDepth),
                centerVal * (1 + heartDepth));

var neural  = LFNoise2.kr(neuralSpeed).range(
                centerVal * (1 - neuralDepth),
                centerVal * (1 + neuralDepth));

// 3階層の合成（呼吸が主、心拍が副、神経が微細）
var finalVal = breath * 0.6 + heart * 0.3 + neural * 0.1;
```

### パラメーターとレイヤーの対応表

| パラメーター | 担当レイヤー | 振れ幅 |
|------------|-----------|-------|
| feedback_amt | A1（呼吸） | ±15% |
| room_size | A1（呼吸） | ±15% |
| cutoff | A2（心拍） | ±25% |
| reverb_mix | A2（心拍） | ±20% |
| grain_density | A2（心拍） | ±25% |
| pitch_detune | A3（神経） | ±5% |
| pan | A3（神経） | ±8% |
| grain_spray | A3（神経） | ±5% |

---

## 5. Layer B 詳細設計：チューリング遺伝子

### 概念

Eurorackの「Turing Machine」モジュールに着想を得た設計。
シフトレジスタがゆっくり変異するパターンを保持し、ループしそうでしない「既視感のある新しさ」を生む。

完全ランダムでも完全ループでもない、その中間の状態を実現する。

### シフトレジスタの動作

```
初期状態: [1200, 800, 1600, 900, 1200, 700, 1400, 1000]  ← 8ステップ
                 ↓ clockRate Hz でステップを進む
Step 3で変異が発生(prob = 0.05):
変異後:   [1200, 800, 1600, 950, 1200, 700, 1400, 1000]  ← Step4が950に
                 ↓ ゆっくりと変化していく
数分後:   [1100, 850, 1550, 950, 1200, 720, 1380, 1050]  ← 少しずつ変わった
```

### SuperCollider実装イメージ

```supercollider
// Layer Bの実装パターン（独立したSynthとして動作）
// SCのBufferにパラメーター列を保持し、OSCで値を送り出す

SynthDef(\turing_gene, {
    arg out = 0, clockRate = 0.1, mutationProb = 0.05, bufnum;

    var clock = Impulse.kr(clockRate);
    var step  = Stepper.kr(clock, 0, 0, numSteps - 1);

    // BufferからステップのAttractor値を読む
    var attractor = BufRd.kr(1, bufnum, step, 1, 2);

    // 確率的変異: mutationProbの確率でランダム値に差し替え
    var mutation = TRand.kr(minVal, maxVal, CoinGate.kr(mutationProb, clock));
    var mutated  = Select.kr(CoinGate.kr(mutationProb, clock), [attractor, mutation]);

    // 変異した値をBufferに書き戻す
    BufWr.kr(mutated, bufnum, step);

    // Layer Aへ: スムージングしてアトラクター値を出力
    Out.kr(out, mutated.lag(2.0));
}).add;
```

### DNA パラメーターの意味

| DNA パラメーター | 役割 | 値の範囲 |
|----------------|-----|---------|
| `mutationProb` | 何%のステップが変異するか | 0.01（ほぼ不変）〜0.30（頻繁に変異） |
| `scale` | 音程が選べる音階 | 例: [0,2,3,5,7,8] = ナチュラルマイナー |
| `stepCount` | ループの長さ | 8（短い・親しみやすい）〜16（長い・予測困難） |
| `clockRate` | ステップが進む速度 | 0.05〜0.3 Hz |

---

## 6. Layer 3 詳細設計：3本の笛

### 笛①: CHAOS（カオス） — 0.0〜1.0

**音楽的意味**: 群れをどれだけ自由に動かすか

```
CHAOS = 0.0: 音がほぼ変化しない。反復・瞑想的
CHAOS = 0.5: 緩やかに変化。予測できるが固定でない
CHAOS = 1.0: 音が常に変化する。予測不能・緊張感
```

**内部マッピング**:
| 内部パラメーター | 計算式 |
|----------------|-------|
| B.mutationProb | `0.01 + chaos * 0.29` |
| A1.breathDepth | `0.08 + chaos * 0.17` |
| A2.heartDepth | `0.15 + chaos * 0.25` |
| A1.breathSpeed | `0.015 + chaos * 0.035` |

---

### 笛②: DENSITY（密度） — 0.0〜1.0

**音楽的意味**: 音の重なりをどれくらいにするか

```
DENSITY = 0.0: 音数が少ない。静寂が多い。Burialの霧
DENSITY = 0.5: 中程度の豊かさ
DENSITY = 1.0: 音が重なり合う。Autechreの密な織り
```

**内部マッピング**:
| 内部パラメーター | 計算式 |
|----------------|-------|
| Granular grain数 | `10 + density * 190` grains/sec |
| Drone oscillator数 | `1 + floor(density * 3)` 本 |
| Rhythmic event prob | `0.1 + density * 0.7` |

---

### 笛③: TENSION（テンション） — 0.0〜1.0

**音楽的意味**: 音の重力・緊張感

```
TENSION = 0.0: 重心が低い・温かい・着地している感覚
TENSION = 0.5: 中立
TENSION = 1.0: 高域・鋭い・宙に浮いている感覚・不安定
```

**内部マッピング**:
| 内部パラメーター | 計算式 |
|----------------|-------|
| ピッチ中心 | `30 + tension * 90` Hz（低→高） |
| フィルターの明るさ | `300 + tension * 3700` Hz |
| Reverb dry/wet | `0.7 - tension * 0.5`（wet→dry） |
| Grain spray | `0.1 + tension * 0.6` |

---

## 7. シーン定義（DNAプロファイル）

シーンは「パラメーターの値の集合」ではなく「振る舞いのプロファイル」として定義する。

```json
{
  "scenes": {
    "warm": {
      "description": "眠る生き物。Tim Hecker低域のような温かく重心の低い場所",
      "artist_ref": "Tim Hecker — 低域持続音、霧の中の暖かさ",
      "dna": {
        "mutationProb": 0.03,
        "scale": [0, 2, 3, 5, 7, 8],
        "stepCount": 8,
        "mutation_bars": 8
      },
      "metabolism": {
        "breathSpeed": 0.02,
        "breathDepth": 0.10,
        "heartSpeed": 0.15,
        "heartDepth": 0.18,
        "neuralSpeed": 1.5,
        "neuralDepth": 0.04
      },
      "defaults": {
        "chaos": 0.2,
        "density": 0.3,
        "tension": 0.1,
        "bpm": 60
      }
    },

    "void": {
      "description": "空虚で不穏な空間。Alva Notoの空白と緊張感",
      "artist_ref": "Alva Noto — 還元的、間、クリックの孤独",
      "dna": {
        "mutationProb": 0.10,
        "scale": [0, 1, 5, 6, 10],
        "stepCount": 10,
        "mutation_bars": 6
      },
      "metabolism": {
        "breathSpeed": 0.04,
        "breathDepth": 0.16,
        "heartSpeed": 0.28,
        "heartDepth": 0.22,
        "neuralSpeed": 2.5,
        "neuralDepth": 0.06
      },
      "defaults": {
        "chaos": 0.4,
        "density": 0.2,
        "tension": 0.5,
        "bpm": 75
      }
    },

    "vast": {
      "description": "荘厳で天井の高い空間。Tim Hecker教会のような広がり",
      "artist_ref": "Tim Hecker — Virgins期、大聖堂残響、倍音の積み上げ",
      "dna": {
        "mutationProb": 0.05,
        "scale": [0, 2, 4, 7, 9],
        "stepCount": 8,
        "mutation_bars": 8
      },
      "metabolism": {
        "breathSpeed": 0.025,
        "breathDepth": 0.14,
        "heartSpeed": 0.2,
        "heartDepth": 0.20,
        "neuralSpeed": 2.0,
        "neuralDepth": 0.05
      },
      "defaults": {
        "chaos": 0.25,
        "density": 0.45,
        "tension": 0.3,
        "bpm": 55
      }
    },

    "lost": {
      "description": "漂流する孤独。Burial深夜の迷子感",
      "artist_ref": "Burial — 非グリッドリズム、深夜、Foley、哀愁",
      "dna": {
        "mutationProb": 0.08,
        "scale": [0, 2, 3, 7, 8],
        "stepCount": 12,
        "mutation_bars": 6
      },
      "metabolism": {
        "breathSpeed": 0.03,
        "breathDepth": 0.12,
        "heartSpeed": 0.18,
        "heartDepth": 0.19,
        "neuralSpeed": 1.8,
        "neuralDepth": 0.045
      },
      "defaults": {
        "chaos": 0.35,
        "density": 0.30,
        "tension": 0.25,
        "bpm": 65
      }
    },

    "peak": {
      "description": "絶頂・高揚。Autechreの頂点のような制御された爆発",
      "artist_ref": "Autechre — Confield期、変異する複雑リズム、高密度",
      "dna": {
        "mutationProb": 0.25,
        "scale": [0, 1, 3, 5, 6, 8, 10],
        "stepCount": 16,
        "mutation_bars": 2
      },
      "metabolism": {
        "breathSpeed": 0.07,
        "breathDepth": 0.30,
        "heartSpeed": 0.5,
        "heartDepth": 0.35,
        "neuralSpeed": 4.5,
        "neuralDepth": 0.09
      },
      "defaults": {
        "chaos": 0.8,
        "density": 0.6,
        "tension": 0.5,
        "bpm": 110
      }
    }
  }
}
```

---

## 8. 安全制御設計

クリッピング・フィードバック発振を防ぐ多層防衛。

### 防衛ライン一覧

```
[Layer B の変異値]
     └─ Clip(value, sceneMin, sceneMax)
        → シーンが許可する範囲外に出ない

[Layer A の LFNoise 値]
     └─ .range(0.0, 1.0) でスケーリングしてから適用
        → 負の値・1超えの値が出力されない

[Feedback パス]
     └─ LeakDC.ar(feedback_signal)
        → DCオフセットの蓄積を防ぐ（発振の根本原因）

     └─ feedback_amt に Clip.ar(0.0, 0.72) を適用
        → 物理的に発振しない上限を設ける

[SynthDef 最終出力（最終防衛線）]
     └─ Limiter.ar(sig, 0.9, 0.01)
        → 何があっても音量が 0.9 を超えない
```

### CoreAudio 起動問題への対処（既知制約）

**問題**: scsynth 起動時に portaudio が CoreAudio を初期化し、他のアプリの音声ストリームが切断される可能性がある。

**設計上の含意**:
- MaToMa の起動はライブ前に完了させる（本番中の再起動は禁止）
- Layer A/B の自律システムは「一度起動したら止めない前提」で設計する
- シーン切り替えは再起動なしで行えるよう設計する

---

## 9. UI 再設計

### Before（現在）：約25パラメーター

```
Drone:     freq / feedback / shimmer / room / amp
Granular:  density / spray / pos / size / room / amp
Rhythmic:  prob / bpm / amp
Effects:   delay(time・feedback・mix) / spectral(freeze・blur)
           saturation(drive・mix) / chorus(amount・rate)
DroneGen:  freq / amp / damp × 4種
```

大半が「鎖」= Layer A/B が担うべきパラメーター。

---

### After（設計後）：8コントロール

```
┌─────────────────────────────────────────────────┐
│  SCENE:  [warm] [void] [vast] [lost] [peak]      │  ← 犬
├─────────────────────────────────────────────────┤
│  CHAOS    ──────●──────  0.4                   │  ← 笛①
│  DENSITY  ────●────────  0.3                   │  ← 笛②
│  TENSION  ─●──────────  0.2                   │  ← 笛③
├─────────────────────────────────────────────────┤
│  BPM      ────────●────  80                    │  ← テンポ
│  DRIVE    ──●──────────  0.2                   │  ← 音の質感
│  FREEZE   [  OFF  ]                            │  ← 瞬間を止める
│  MASTER   ──────────●──  0.8                   │  ← 全体音量
└─────────────────────────────────────────────────┘
```

### 削除するパラメーター（Layer A/Bに委ねる）

| 削除するパラメーター | 委ねる先 |
|-------------------|---------|
| freq（Drone・DroneGen） | Layer B（DNA が音程中心を決める） |
| feedback（Drone） | Layer A1（呼吸が揺らす）+ 安全制御 |
| shimmer | Layer B（シーンDNAの一部） |
| room（全層） | Layer A1（呼吸が揺らす） |
| spray / pos / size | Layer A2/A3（心拍・神経が担う） |
| prob（Rhythmic） | CHAOS 笛にマッピング |
| delay time/feedback | Layer A が管理・発振防止 |
| chorus amount/rate | Layer A が管理 |
| amp（各層） | MASTER に統合 |

### 残すパラメーター（羊飼いの道具）

| 残すコントロール | 理由 |
|----------------|-----|
| SCENE selector | 「犬」= 群れの方向を変える |
| CHAOS | 自律性の強さを大局的に決める |
| DENSITY | 音の重なりは音楽的意図と直結 |
| TENSION | 感情の弧は人間が担う |
| BPM | テンポは音楽的な基準点 |
| DRIVE | 音の質感（warm/harsh）はキャラクター |
| FREEZE | 「瞬間を止める」= 音楽的な指示 |
| MASTER | 物理的な音量は人間が管理 |

---

## 10. 実装順序（推奨）

段階的に実装し、各段階で「良くなった/変わった」を確認する。

### Phase 1: 安全制御の整備（先行）
既存コードに安全制御だけ追加する。音の変化は最小限。
- [ ] 全SynthDef出力に `Limiter.ar(sig, 0.9)` を追加
- [ ] Droneの feedback パスに `LeakDC.ar` + `Clip(0, 0.72)` を追加
- [ ] 動作確認: フィードバックを最大にしても発振しないことを確認

### Phase 2: Layer A の実装（呼吸する有機体）
既存SynthDefにLFNoise3階層を追加する。
- [ ] Drone SynthDefに A1（呼吸）を追加: feedback_amt・room を揺らす
- [ ] 動作確認: 何も操作しなくても音が微かに変化することを確認
- [ ] Granular SynthDefに A2（心拍）を追加: density・reverb_mix を揺らす
- [ ] 動作確認: 粒の密度が自律的に変化することを確認
- [ ] A3（神経）を全層に追加: pitch detune・pan を揺らす

### Phase 3: Layer B の実装（チューリング遺伝子）
独立したSynthとしてシフトレジスタを実装する。
- [ ] `turing_gene` SynthDef を実装
- [ ] シーンごとのDNA値をJSONファイルに定義
- [ ] Layer AのcenterValとLayer Bの出力を接続
- [ ] 動作確認: 同じシーンで数分待つと音が少しずつ変化することを確認

### Phase 4: 笛マッピングの実装
3本の笛と内部パラメーターのマッピングをPythonに実装する。
- [ ] Python側に `chaos_to_internal()` `density_to_internal()` `tension_to_internal()` 関数を実装
- [ ] OSCで3値だけ受け取り、内部計算で全パラメーターに展開する

### Phase 5: UI の再設計
フロントエンドを25パラメーターから8コントロールに整理する。
- [ ] 既存スライダーを削除
- [ ] SCENE / CHAOS / DENSITY / TENSION / BPM / DRIVE / FREEZE / MASTER を実装
- [ ] 「カオス表示パネル」は読み取り専用の可視化として残す（操作不可）

---

## 11. 設計決定済み事項

### SCENEのファイル構成（決定: 2026-03-30）

**採用: ハイブリッド案（1ファイル・シーンブロック方式）**

```
matoma.tidal（1ファイル）
  ├── グローバル設定（setcps、SynthDef定義）
  ├── -- SCENE: warm --
  │   d1 $ ...  ← ドラム（穏やか・低重心）
  │   d2 $ ...  ← コード
  │   d3 $ ...  ← ベース
  ├── -- SCENE: void --
  │   d1 $ ...  ← ドラム（疎・沈黙多め）
  │   d2 $ ...
  │   d3 $ ...
  ├── -- SCENE: vast --
  │   d1 $ ...  ← ドラム（広い空間、遅い動き）
  │   d2 $ ...
  │   d3 $ ...
  ├── -- SCENE: lost --
  │   d1 $ ...  ← ドラム（非グリッド、漂流）
  │   d2 $ ...
  │   d3 $ ...
  └── -- SCENE: peak --
      d1 $ ...  ← ドラム（高密度、変異的）
      d2 $ ...
      d3 $ ...
```

理由: BPM・グローバル設定を1か所で管理できる。ライブ中にエディタで全シーンを俯瞰できる。SCENEを切り替えるとき、Pythonが「どのブロックをevalするか」を選ぶ。

---

### BPMとDNAの連動（決定: 2026-03-30）

**採用: clockRateはBPMに連動する**

シーンDNAの `clockRate` は「何小節に1回変異するか」として定義し、BPMが変わっても小節単位のペース感が保たれるよう自動計算する。

```python
# Python側の計算式
# clockRate [Hz] = BPM / (60 * 4 * mutation_bars)
# mutation_bars: シーンDNAで定義する「何小節に1回変異するか」

def bpm_to_clock_rate(bpm: float, mutation_bars: int) -> float:
    beats_per_bar = 4          # 4/4拍子固定
    seconds_per_beat = 60 / bpm
    seconds_per_bar = seconds_per_beat * beats_per_bar
    return 1.0 / (seconds_per_bar * mutation_bars)

# 例: BPM=72、8小節に1回変異
# → clockRate = 1 / (3.33 * 8) = 0.0375 Hz
# BPM=144、同じく8小節に1回変異
# → clockRate = 1 / (1.67 * 8) = 0.075 Hz
```

シーンDNAの `clockRate` フィールドを `mutation_bars`（整数）に変更する：

```json
// 変更前
"clockRate": 0.07

// 変更後
"mutation_bars": 8   // 8小節に1回変異
```

BPMが変わるたびにPython側が `mutation_bars` から `clockRate` を再計算してSCに送る。

---

### FREEZEの挙動（決定: 2026-03-30）

**採用: シーン転換の橋渡し（C案）**

FREEZEは単独のエフェクトではなく、**シーン切り替えの「準備時間」を作る道具**として機能する。

```
操作シーケンス:
  1. FREEZE ON  → 出音が凍る。内部では次シーンへの準備が進む
  2. SCENE切替  → TidalとLayer B DNAが新シーンに移行し始める（出音は凍ったまま）
  3. FREEZE OFF → blurを一時上昇させて「霞になって溶ける」演出をしてから新シーンが現れる
```

**内部の動作:**

| タイミング | 出音 | Layer A/B | Tidal |
|-----------|------|----------|-------|
| FREEZE ON | 凍結（スナップショット保持） | 動き続ける（次シーンへ準備） | 停止 |
| SCENE切替中 | 凍結のまま | 新シーンDNAへ変異開始 | 新パターンへ移行開始 |
| FREEZE OFF | blur上昇→ゆっくり溶ける | 新シーンで稼働中 | 新パターンで再生 |

**Python側の実装責任:**
- FREEZE ON時: `PV_MagFreeze=1.0` をSCに送る
- SCENE切替検知: FREEZE中のSCENE変更を「予約」として保持する
- FREEZE OFF時: `blur`を一時的に上昇（0→4→0）させてから`PV_MagFreeze=0.0`に戻す

**音楽的な意味:**
DJがフェーダーを絞って次の曲を準備し、フェーダーを上げる操作に相当する。
凍らせている間が「準備時間」。観客には遷移の途中が聴こえない。

---

### シーン間の遷移（決定: 2026-03-30）

**採用: 8小節かけたゆっくり遷移（デフォルト）。16小節も選択可。**

理由: 即時切り替えではTidal・Layer B・Layer Aの3つが同時にジャンプし、クリックノイズや音の断絶が起きやすい。8〜16小節かけることで全レイヤーが滑らかに移行し安定する。

```haskell
-- Tidalでの実装: xfadeIn で8サイクルかけてフェードイン
d1 $ xfadeIn 1 8 $ s "matoma_kick ~ ~ ~  ~ ~ matoma_kick ~"
--                  ↑ 8サイクル（= 8小節）でクロスフェード
```

```python
# Python側: Layer B DNA・Layer A 代謝パラメーターの遷移時間
SCENE_TRANSITION_BARS = 8    # デフォルト（16に変更も可）

# .lag() でSC側もゆっくり移行
# SCへ送るOSC: /matoma/scene/transition_bars 8
```

| 遷移小節数 | 秒数（72BPM） | 秒数（110BPM） | 向いている状況 |
|-----------|-------------|--------------|--------------|
| 8小節 | 約26秒 | 約17秒 | 標準。変化を感じやすい |
| 16小節 | 約53秒 | 約35秒 | 気づかないうちに変わる。環境音的な使い方 |

---

### CHAOSの作用範囲（決定: 2026-03-30）

**採用: Tidal側・SC側の両方に作用。調整ノブを用意して後から絞れるようにする。**

```python
# Python側の設定値（初期値: 両方フル作用）
CHAOS_TIDAL_RATIO = 1.0   # Tidalへの影響度（0.0〜1.0）
CHAOS_SC_RATIO    = 1.0   # SC層への影響度（0.0〜1.0）
```

| 状況 | 対応 |
|------|------|
| 初期（両方フル） | `TIDAL_RATIO=1.0 / SC_RATIO=1.0` |
| Tidalが崩れすぎる | `TIDAL_RATIO=0.5` → 骨格を保ちSCだけ揺れる |
| SC音色が暴れすぎる | `SC_RATIO=0.5` → リズム崩しつつ音色は安定 |
| 完全に骨格を守る | `TIDAL_RATIO=0.0` → Tidalは固定、SCのみ変化 |

---

## 12. DROP軸設計（構造的位置）

SCENE軸が「感情的な世界観」を定義するのに対し、DROP軸は「曲の中のどこにいるか」= 構造的な位置を定義する。2つの軸は**直交**する。

```
warm + break    = 温かい世界観のブレイク（静かで穏やか）
void + build-up = 空虚な緊張感が蓄積していく
peak + drop     = 絶頂の解放（最もエネルギーが高い瞬間）
lost + anti-drop = 希望のように聴こえたのに沈んでいく（最もBurialらしい）
```

---

### DROP状態の定義

| 状態 | 意味 | 体験 |
|------|------|------|
| `break` | 休憩・抜き | ドラムが消え、空白が広がる。次への準備 |
| `build-up` | 蓄積・高揚 | 密度と緊張が徐々に上昇する。予感 |
| `drop` | 解放・爆発 | すべてが最大密度で解き放たれる |
| `anti-drop` | 裏切り・沈降 | 解放されると思ったのに沈む（Burial流） |

---

### 実装方針: シーンDNAへのオフセット

DROP状態は**SCENEのdefault値に対するオフセット**として機能する。

```python
effective_chaos   = clamp(scene_chaos   + drop_offset_chaos,   0.0, 1.0)
effective_density = clamp(scene_density + drop_offset_density, 0.0, 1.0)
effective_tension = clamp(scene_tension + drop_offset_tension, 0.0, 1.0)
```

SCENEの個性（warm は低重心、peak は高密度）を保ちながら、構造的な位置だけを変えられる。

---

### DROP状態ごとのオフセット

| DROP状態 | chaos offset | density offset | tension offset | 特記 |
|---------|-------------|----------------|---------------|------|
| `break` | −0.20 | −0.35 | −0.10 | 最小密度。空白を作る |
| `build-up` | 0 → +0.20 (ramp) | 0 → +0.30 (ramp) | 0 → +0.20 (ramp) | 唯一のランプ変化 |
| `drop` | +0.30 | +0.40 | 0（scene default維持） | テンションは解放感に変換 |
| `anti-drop` | −0.10 | −0.35 | +0.20 | 密度は落ちるが緊張は残る |

**build-up のランプ duration**: 4〜16小節（Python が毎小節オフセットを更新してOSCで送る）

---

### Tidal への影響

DROP状態は `drop_state` としてOSCで送られ、Pythonが評価するブロックを切り替える。

```
drop_state = "break"
  → d1 を silence に切り替え（ドラム停止）
  → d2/d3 は継続（コード・ベースは残す）

drop_state = "build-up"
  → every N で degradeBy 0.5 のNを毎小節 1ずつ減らす
  → パターンが徐々にフル密度に近づく

drop_state = "drop"
  → degradeBy 0（フルパターン。nothing が落ちない）

drop_state = "anti-drop"
  → d1 を silence（ドラムは落ちる）
  → d2/d3 は継続、ただし tension+0.2 でコードが不穏に
```

---

### 羊飼いモデルとの整合性

DROP軸は **「犬2頭目」** として機能する。

| 軸 | 道具 | 役割 |
|----|------|------|
| SCENE軸（犬1頭目） | シーンボタン | 群れがいる「場所」を変える |
| DROP軸（犬2頭目） | DROPボタン | 群れの「動きの形」を変える（散らばれ/集まれ） |

どちらも羊を直接動かすのではなく、**群れの方向と密度の形を変える**役割。
「break中に SCENE を warm → void に切り替える」= 羊飼いが2頭の犬を同時に使う演奏技法。

---

### UIへの追加

セクション9のUIイメージを更新する:

```
┌─────────────────────────────────────────────────┐
│  SCENE:  [warm] [void] [vast] [lost] [peak]      │  ← 犬①
│  DROP:   [break] [build-up] [drop] [anti-drop]  │  ← 犬②
├─────────────────────────────────────────────────┤
│  CHAOS    ──────●──────  0.4                    │
│  DENSITY  ────●────────  0.3                    │
│  TENSION  ─●──────────  0.2                    │
├─────────────────────────────────────────────────┤
│  BPM      ────────●────  80                     │
│  DRIVE    ──●──────────  0.2                    │
│  FREEZE   [  OFF  ]                             │
│  MASTER   ──────────●──  0.8                    │
└─────────────────────────────────────────────────┘
```

---

## 13. エネルギー軸設計（方向性・勾配）

SCENE軸（世界観）とDROP軸（構造位置）に続く3本目の軸。  
**今、音楽はどちらに向かって動いているか** — エネルギーの方向性を定義する。

---

### フィルター＋レゾナンスのアナロジー

```
フィルターを開いていく（cutoff 上昇）= 接近感・高揚・期待
フィルターを絞っていく（cutoff 下降）= 後退感・落下・解放
残響が長くなる              = 空間に溶けていく（低エネルギー）
残響が短くなる              = タイトに集中する（高エネルギー）
```

エネルギー軸はこの**フィルター操作の感覚**をシステム全体に広げたもの。

---

### ENERGY スライダー

```
ENERGY    0.0 ────────────── 0.5 ────────────── 1.0
          （下降・後退）     （中立・安定）     （上昇・接近）
```

**スライダー1本で「今どちら向きか」を設定する。**  
絶対的な音量ではなく、Layer A/Bのパラメーターが動く**方向と速さ**を制御する。

---

### 内部マッピング

| パラメーター | ENERGY=0.0（下降） | ENERGY=0.5（中立） | ENERGY=1.0（上昇） |
|------------|------------------|------------------|------------------|
| Layer A 呼吸速度全体 | × 0.6 倍（遅い） | × 1.0 | × 1.6 倍（速い） |
| フィルター cutoff ドリフト | 毎小節 −50Hz | ドリフトなし | 毎小節 +50Hz |
| Reverb decay | × 1.5（長い・溶ける） | × 1.0 | × 0.6（短い・タイト） |
| ピッチ中心ドリフト | −0.5 semitone / 8小節 | ドリフトなし | +0.5 semitone / 8小節 |
| Tidal velocity trend | 徐々に small 方向 | 固定 | 徐々に large 方向 |

**「ドリフト」とは**: 毎小節 Python が現在値を少し動かして OSC で送る。スライダーで上書きしない限り自動的に流れ続ける。

---

### DROP軸との連携（自動連動）

DROP状態が変わると ENERGY は**自動でその状態に馴染む値に引き寄せられる**。  
ただし羊飼いが ENERGY スライダーで上書きすれば優先される。

| DROP状態 | ENERGY の自動引き寄せ先 | 説明 |
|---------|----------------------|------|
| `break` | → 0.25（ゆるやかに） | 休憩なので下降方向に落ち着く |
| `build-up` | 現在値 → 0.85（ランプ） | build-up 期間中に徐々に上昇 |
| `drop` | → 1.0 → 0.5（即上昇、その後中立） | 解放の瞬間に最大、その後落ち着く |
| `anti-drop` | → 0.15（ゆるやかに） | 期待を裏切って沈む |

```python
# Pythonでの実装イメージ
class EnergyController:
    target: float   # DROP連動の引き寄せ先
    current: float  # 現在値
    manual: float   # 羊飼いによる上書き（Noneなら連動）

    def tick_per_bar(self) -> float:
        # manual があれば優先、なければ target に向かってゆっくり近づく
        if self.manual is not None:
            self.current = lerp(self.current, self.manual, 0.3)
        else:
            self.current = lerp(self.current, self.target, 0.2)
        return self.current
```

---

### 3軸の全体像

3軸が揃ったことで、ライブのどんな瞬間も座標として表現できる:

```
(SCENE=lost, DROP=build-up, ENERGY=0.7)
  = 孤独な世界観で、密度が蓄積されていく途中、エネルギーは上昇中
  = Burial的なグルーヴが凝縮されていく瞬間

(SCENE=void, DROP=anti-drop, ENERGY=0.1)
  = 空虚な世界で、解放されると思ったのに沈む、エネルギーは下降
  = 最もAlva Noto的な虚無の表現
```

---

### 羊飼いモデルとの整合性

| 軸 | 道具 | 役割 |
|----|------|------|
| SCENE軸（犬1頭目） | シーンボタン5択 | 群れがいる「場所」 |
| DROP軸（犬2頭目） | DROPボタン4択 | 群れの「動きの形」 |
| エネルギー軸（笛4本目） | ENERGYスライダー | 群れの「向かう方向」 |

ENERGYは**笛**（直接的すぎない操作）として位置づける。  
DROPが自動連動するため、意識的に上書きしなければ「自然な流れ」のまま進む。

---

### UIへの追加

```
┌─────────────────────────────────────────────────┐
│  SCENE:  [warm] [void] [vast] [lost] [peak]      │  ← 犬①
│  DROP:   [break] [build-up] [drop] [anti-drop]  │  ← 犬②
├─────────────────────────────────────────────────┤
│  CHAOS    ──────●──────  0.4                    │  ← 笛①
│  DENSITY  ────●────────  0.3                    │  ← 笛②
│  TENSION  ─●──────────  0.2                    │  ← 笛③
│  ENERGY   ──────────●──  0.7                    │  ← 笛④（上昇方向）
├─────────────────────────────────────────────────┤
│  BPM      ────────●────  80                     │
│  DRIVE    ──●──────────  0.2                    │
│  FREEZE   [  OFF  ]                             │
│  MASTER   ──────────●──  0.8                    │
└─────────────────────────────────────────────────┘
```

合計コントロール数: **10個**（8 → 9コントロールに増加。SCENEとDROPはボタン）

---

## 14. 未解決・要検討事項

- ~~**シーン間の遷移**~~ → **決定済み（セクション11参照）**
- ~~**FREEZE の挙動**~~ → **決定済み（セクション11参照）**
- ~~**BPMとDNAの連動**~~ → **決定済み（セクション11参照）**
- ~~**SCENE軸の名前**~~ → **決定済み: warm/void/vast/lost/peak（セクション7参照）**
- ~~**DROP軸の設計**~~ → **決定済み: break/build-up/drop/anti-drop（セクション12参照）**
- ~~**エネルギー軸の設計**~~ → **決定済み: ENERGYスライダー（下降0.0～中立0.5～上昇1.0）（セクション13参照）**
- **ライブ中のシーン追加**: 5シーン固定で良いか、実演中に増やしたくなるか
- **Chaos表示パネル**: 現在の読み取り専用パネルはこのまま残す。Layer A/Bの動きをビジュアル化する役割として有効
- **Tidal→SC接続方式**: SuperDirt経由 vs 直接OSC。Phase 3実装時に判断する（→ セクション3参照）
- **DROP軸の build-up duration**: デフォルト8小節だが、BPMや文脈によって4〜16小節の範囲で調整できると良い。UI側での設定方法を検討

---

_設計書バージョン: 1.6 / 2026-03-30 更新（3軸完成: SCENE軸・DROP軸・エネルギー軸）_
