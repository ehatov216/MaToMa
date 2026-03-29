<!-- Generated: 2026-03-29 | Files scanned: scenes.json, knowledge_base.json | Token estimate: ~400 -->
# Data Structures

## scenes.json — プリセットシーン

4シーン固定。`backend/scenes.py` で読み込み。

```json
{
  "name": "暗い",
  "freq": 110,          // FM合成 基本周波数 (Hz)
  "cutoff": 400,        // FM合成 フィルターカットオフ (Hz)
  "amp": 0.4,           // FM合成 ゲイン
  "drone": {
    "freq": 40,         // ドローン 基本周波数 (Hz)
    "detune": 0.4,      // デチューン量 (0-1)
    "cutoff": 500,      // ドローン フィルター (Hz)
    "drift": 0.6,       // LFO速度 (0-1)
    "room": 0.9,        // リバーブ量 (0-1)
    "revtime": 20.0,    // 残響時間 (秒)
    "amp": 0.8,
    "breathe": 0.7      // 振幅変調 (0-1)
  }
}
```

| シーン名 | freq | drone.freq | 特性 |
|---------|------|------------|------|
| 暗い | 110 | 40 | 最も低く重い |
| 標準 | 220 | 55 | バランス型 |
| 明るい | 440 | 80 | 高く明るい |
| 高音・静か | 660 | 110 | 最も高く静か |

## OSC Address Space

```
/matoma/param          [key: str, value: float]  — FMシンセ制御
/matoma/drone/param    [key: str, value: float]  — ドローン制御
/matoma/granular/param [key: str, value: float]  — グラニュラー制御
/matoma/granular/load  [path: str]               — サンプルファイルロード
/matoma/spectral/param [key: str, value: float]  — スペクトル制御
/matoma/scene          [name: str]               — シーン一括切替
/matoma/ready          []                         — SC起動完了 (SC→Python)
/matoma/seq/tick       [step: int, active: bool] — ステップ通知 (SC→Python)
/matoma/granular/density [n: int]                — グレイン密度 (SC→Python)
```

## Parameter Ranges

```
FM Synth:
  freq    55-880 Hz
  cutoff  200-8000 Hz
  amp     0-1
  chaos   0-1

Drone:
  freq    40-220 Hz
  detune  0-1
  cutoff  80-3000 Hz
  drift   0-1
  room    0-1
  revtime 1-30 s
  amp     0-1
  breathe 0-1

Granular:
  pos     0-1    (再生位置)
  density 1-50   (グレイン/秒)
  spread  0-1    (ピッチばらつき)
  amp     0-1

Spectral:
  smear   0.1-0.9
  chaos   0.1-0.8

Sequencer:
  bpm          20-300
  trig_prob    0-1
  mutation_prob 0-1
  steps        16固定
```

## feedback/knowledge.md 構造

```
## 言葉とパラメーターの対応
| ユーザーの言葉 | 変更するパラメーター | 方向 | 値の範囲 |

## 効いた操作
## 効かなかった操作
## 警告（悪化パターン）
```

## feedback/logs/YYYY-MM-DD.json 構造

```json
[
  {
    "timestamp": "...",
    "hypothesis": "drift を上げると揺らぎが増える",
    "change": {"param": "drift", "from": 0.2, "to": 0.5},
    "evaluation": "良くなった",
    "note": "..."
  }
]
```
