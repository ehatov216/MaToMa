---
title: TidalCycles パターン操作関数リファレンス
category: tidal
tags: [tidal, pattern, time, randomness, alteration, transitions, every, perlin, degrade]
---

## TidalCycles パターン操作関数

---

### 1. 時間操作

```haskell
-- fast / slow: 速く・遅くする
d1 $ fast 2 $ s "bd sn"        -- 2倍速
d1 $ slow 4 $ s "bd sn hh cp"  -- 4倍遅く

-- fast にパターンを渡せる
d1 $ fast "2 4" $ s "bd sn kurt cp"  -- 前半2倍、後半4倍

-- fastGap: 速くして残りは無音
d1 $ fastGap 2 $ s "bd sn"  -- 半分の時間で1回再生して残りは無音

-- rev: 逆再生
d1 $ rev $ s "bd hh sn hh"

-- iter: サイクルごとにずらす
d1 $ iter 4 $ s "bd hh sn hh"

-- palindrome: 前進・後退を繰り返す
d1 $ palindrome $ s "bd hh sn"

-- rotL / rotR: 時間軸でシフト
d1 $ rotL 0.25 $ s "bd ~ sn ~"  -- 1/4サイクル左にずらす
```

---

### 2. ランダム性

```haskell
-- rand: 0.0〜1.0のランダム連続値
d1 $ s "bd*8" # pan rand
d1 $ s "arpy*4" # speed (rand + 0.5)  -- 0.5〜1.5の速度

-- irand n: 0〜n-1のランダム整数
d1 $ s "amencutup*8" # n (irand 8)

-- perlin: スムーズなランダム（パーリンノイズ）
d1 $ s "bd*32" # speed (perlin + 0.5)    -- 滑らかな速度変化
d1 $ s "arpy*8" # cutoff (perlinWith (saw * 4) * 2000)

-- choose: リストからランダム選択
d1 $ s "drum ~ drum drum" # n (choose [0,2,3])

-- wchoose: 重み付きランダム選択
d1 $ s "drum*4" # n (wchoose [(0,0.5),(2,0.3),(5,0.2)])

-- degrade: ランダムにイベントを消す（50%）
d1 $ degrade $ s "hh*8"

-- degradeBy: 消す割合を指定
d1 $ degradeBy 0.7 $ s "hh*8"  -- 70%消す

-- sometimes: 50%の確率で関数を適用
d1 $ sometimes (fast 2) $ s "bd sn"
d1 $ sometimes (# crush 2) $ s "arpy*4"

-- sometimes系バリアント
-- always(100%), almostAlways(90%), often(75%), sometimes(50%), rarely(25%), almostNever(10%), never(0%)
d1 $ rarely (fast 2) $ s "bd sn cp hh"

-- sometimesBy: 確率を指定
d1 $ sometimesBy 0.3 (# speed 2) $ s "arpy*4"

-- someCycles: サイクル単位でランダム適用
d1 $ someCycles (# crush 2) $ s "arpy*4"
```

---

### 3. パターンの変形・操作

```haskell
-- jux: 左右チャンネルで別々の処理
d1 $ jux rev $ s "bd sn hh cp"       -- 右チャンネルだけ逆再生
d1 $ jux (fast 2) $ s "arpy*4"       -- 右チャンネルだけ2倍速

-- striate: バッファをスライスして並べ替え
d1 $ striate 4 $ s "bev"

-- chop: バッファをN分割してランダム再生
d1 $ chop 16 $ s "breaks125"

-- ply: 各イベントをN回繰り返す
d1 $ ply 3 $ s "bd ~ sn cp"
d1 $ ply "2 3" $ s "bd ~ sn cp"   -- 前半2回、後半3回

-- stutter: イベントを時間ずらしながら繰り返す
d1 $ stutter 3 (1/8) $ s "bd sn"

-- range: 0〜1の値を別の範囲にスケール
d1 $ s "arpy*4" # speed (range 0.5 2 sine)

-- rangex: 指数スケール（周波数に向いてる）
d1 $ s "arpy*4" # cutoff (rangex 200 8000 sine)

-- quantise: 値を分数に丸める
d1 $ s "superchip*8" # n (quantise 1 $ range (-10) 10 $ slow 8 cosine)
```

---

### 4. 条件（every, when）

```haskell
-- every N: Nサイクルごとに関数を適用
d1 $ every 3 rev $ s "bd hh sn hh"
d1 $ every 4 (fast 2) $ s "bd sn"
d1 $ every 3 (# speed 2) $ s "arpy*4"

-- every' N offset: オフセット付きevery
d1 $ every' 3 1 (fast 2) $ s "bd sn"  -- 1,4,7...サイクル目に適用

-- foldEvery: 複数の周期でevery
d1 $ foldEvery [3,5] (|+ n 1) $ s "moog" # legato 1

-- when: 条件関数で適用
d1 $ when ((== 0) . (`mod` 3)) (fast 2) $ s "bd hh sn hh"

-- whenT: 時間条件
-- (高度な使い方)
```

---

### 5. トランジション（シーン切り替え）

```haskell
-- xfade: クロスフェードで切り替え
d1 $ s "bd(3,8) drum*4"
xfade 1 $ s "arpy*8" # n (run 8)

-- xfadeIn N cycles: N サイクルかけてクロスフェード
xfadeIn 1 8 $ s "arpy*8"

-- clutch: 現パターンをランダムに削りながら新パターンを追加
clutch 1 $ s "[hh*4, odx(3,8)]"

-- interpolate: コントロール値を線形補間
d1 $ s "arpy*16" # cutoff 100
interpolate 1 $ s "arpy*16" # cutoff 8000

-- jumpIn N cycles: Nサイクル後に即切り替え
jumpIn 1 2 $ s "hh*8"

-- anticipate: 8サイクル後に追加
anticipate 1 $ s "bd sn" # delay "0.5"
```

---

### 6. スタック・合成

```haskell
-- stack: 複数パターンを同時に走らせる
d1 $ stack [
  s "bd ~ ~ ~",
  s "~ ~ sn ~",
  s "hh*8" # gain 0.6
]

-- overlay: 2パターンを重ねる
d1 $ overlay (s "bd*4") (s "hh*8" # gain 0.6)

-- cat: パターンをサイクルごとに交互に再生
d1 $ cat [s "bd sn", s "hh*4", s "cp bd sn"]

-- fastcat: cat を1サイクルに収める
d1 $ fastcat [s "bd", s "sn", s "hh"]

-- append: 2パターンを順番に
d1 $ append (s "bd sn") (s "hh*4")
```

---

### 7. よく使う組み合わせパターン

```haskell
-- Autechre/Alva Noto スタイル：ランダム性 + 条件変形
d1 $ every 4 (fast 2)
   $ every 3 (jux rev)
   $ sometimesBy 0.3 (degradeBy 0.5)
   $ s "bd(3,8) ~ sn ~"
   # cutoff (range 400 4000 $ slow 8 perlin)
   # room 0.4

-- パーリンノイズでゆっくり変化するパラメーター
d1 $ s "arpy*8"
   # n (irand 12)
   # cutoff (rangex 200 8000 $ slow 16 perlin)
   # gain (range 0.6 1.0 $ slow 4 sine)
   # pan rand
```
