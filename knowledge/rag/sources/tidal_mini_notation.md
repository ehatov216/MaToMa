---
title: TidalCycles ミニ記法リファレンス
category: tidal
tags: [tidal, mini-notation, pattern, rhythm, sequence, euclidean]
---

## TidalCycles ミニ記法（Mini Notation）

ダブルクォートの中で使う専用記法。パターンの基本単位。

### 基本記号一覧

| 記号 | 効果 | 例 | 同等の書き方 |
|------|------|-----|------------|
| `~` | 休符 | `"~ hh"` | |
| `[ ]` | グループ化（1ステップを分割） | `"[bd sd] hh"` | `fastcat [s "bd sd", s "hh"]` |
| `.` | グループ化の省略形 | `"bd sd . hh hh hh"` | `"[bd sd] [hh hh hh]"` |
| `,` | 同時再生（ポリリズム） | `"[bd sd, hh hh hh]"` | `stack [...]` |
| `*` | 繰り返し | `"bd*2 sd"` | `"[bd bd] sd"` |
| `/` | 遅くする | `"bd/2"` | `slow 2 $ "bd"` |
| `\|` | ランダム選択 | `"[bd\|cp\|hh]"` | |
| `< >` | 交互に切り替え | `"bd <sd hh cp>"` | `slow 3 $ "bd sd bd hh bd cp"` |
| `!` | 複製 | `"bd!3 sd"` | `"bd bd bd sd"` |
| `_` | 音を延ばす | `"bd _ _ ~ sd _"` | |
| `@` | 延ばす（比率指定） | `"piano@3 piano"` | `"piano _ _ piano"` |
| `?` | ランダムに消す（50%） | `"bd? sd"` | `degradeBy 0.5 $ s "bd"` |
| `:` | サンプル番号指定 | `"bd:3"` | `s "bd" # n 3` |
| `( )` | ユークリッドリズム | `"bd(3,8)"` | `euclid 3 8 $ s "bd"` |
| `{ }` | ポリメトリック | `"{ bd bd bd, cp cp hh }"` | |
| `%` | 比率 | `"bd*4%2"` | `"bd*2"` |

---

### よく使うパターン

```haskell
-- 基本のビート
d1 $ s "bd ~ sn ~"

-- グループ化で細かいリズム
d1 $ s "[bd hh] [sn hh] [bd*2 hh] sn"

-- ユークリッドリズム（キック3発を8ステップに均等配置）
d1 $ s "bd(3,8)"

-- 複数層を同時に（コンマ区切り）
d1 $ s "[bd*4, hh*8, sn(3,8)]"

-- サイクルごとに交互に切り替え
d1 $ s "bd <sn cp>"

-- ランダムに音を消す
d1 $ s "hh*8" # gain "0.8?"

-- ポリメトリック（異なる長さのパターンを同時に走らせる）
d1 $ s "{bd cp hh}%8"
```

---

### ノート記法

```haskell
-- 音名でメロディ
d1 $ n "c4 d4 e4 g4" # s "superpiano"

-- MIDIノート番号
d1 $ n "60 62 64 67" # s "mysynth"

-- スケール（scale 関数）
d1 $ n (scale "minor" "0 2 4 5 7") # s "superpiano"

-- コード
d1 $ n "c'maj d'min g'maj" # s "superpiano"
```

---

### 数値パターン（コントロール値）

```haskell
-- 定数
d1 $ s "arpy*4" # cutoff 1000

-- パターン（サイクル内で変化）
d1 $ s "arpy*4" # cutoff "500 1000 2000 4000"

-- ランダム
d1 $ s "arpy*4" # cutoff (rand * 3000 + 500)

-- サイン波で滑らかに変化
d1 $ s "arpy*4" # cutoff (range 200 4000 sine)

-- 遅くした sin で大きくゆっくり変化
d1 $ s "arpy*4" # cutoff (range 200 4000 $ slow 8 sine)
```

---

### パターンの合成演算子

| 演算子 | 効果 |
|--------|------|
| `#` | 右辺のパラメーターを追加（左辺の構造を保持） |
| `\|+` | 数値を加算してマージ |
| `\|*` | 数値を乗算してマージ |
| `\|>` | 右辺の構造を保持してマージ |
| `<\|` | 左辺の構造を保持してマージ |

```haskell
-- # は最もよく使う（パラメーター追加）
d1 $ s "bd sn" # gain 0.8 # room 0.4

-- |+ で数値を足す
d1 $ n "0 2 4" |+ n "12"   -- オクターブ上げ

-- |* で掛け算
d1 $ s "bd*4" |* gain "1 0.8 0.6 0.4"
```
