# MaToMa ナレッジ強化 — スクレーピングターゲットURL

> 生成日: 2026-03-29
> 目的: 現在の知識ベース（実装レシピ集）に不足している
>       「設計判断の根拠」「心理音響」「システム設計哲学」を補充する
>
> 優先度: ★★★ = 最優先 / ★★ = 重要 / ★ = あると良い
> 保存先: knowledge/rag/sources/ 以下（カテゴリ別ファイル）

---

## カテゴリ1: 心理音響 / 音の知覚理論
> 「なぜその音が良く聞こえるのか」を説明する科学的基盤
> 保存先: `psychoacoustics_perception.md`

### ★★★ 最優先

| URL | 内容 | 取得したい情報 |
|-----|------|--------------|
| https://ccrma.stanford.edu/~jos/pasp/ | Stanford CCRMA — Physical Audio Signal Processing | マスキング効果、臨界帯域、スペクトル知覚の基礎理論 |
| https://ccrma.stanford.edu/~jos/filters/ | Introduction to Digital Filters (JOS) | フィルター設計の数学的基礎、音色への影響 |
| https://www.musicdsp.org/en/latest/ | MusicDSP.org | 実用的なDSPアルゴリズム集、フィルター実装例 |
| https://www.soundonsound.com/techniques/psychoacoustics | Sound On Sound — Psychoacoustics | 実践的な音楽制作における心理音響の活用 |
| https://msp.ucsd.edu/techniques/latest/book.pdf | Miller Puckette — The Theory and Technique of Electronic Music | MSP本人による電子音楽の理論・SC/Pd向け |

### ★★ 重要

| URL | 内容 | 取得したい情報 |
|-----|------|--------------|
| https://www.audiocheck.net/audiotests_harmanCurve.php | Harman Target Curve | リスニングの心理音響基準 |
| https://www.izotope.com/en/learn/audio-concepts.html | iZotope Audio Concepts | マスキング、周波数バランス、空間処理の実践知識 |
| https://www.soundonsound.com/techniques/fundamentals-audio-compression | Compression psychoacoustics | コンプレッションと知覚の関係 |

---

## カテゴリ2: 電子音楽システム設計哲学
> 「どうモジュールを組み合わせて思想を体現するか」
> 保存先: `system_design_philosophy.md`

### ★★★ 最優先

| URL | 内容 | 取得したい情報 |
|-----|------|--------------|
| https://www.buchla.com/historical/ | Buchla Historical | Don Buchlaの「West Coast合成」哲学、複雑性と制御のバランス |
| https://120years.net/wordpress/the-synthesizer/ | 120 Years of Electronic Music | 合成機器の歴史的文脈、各時代の設計思想 |
| https://learningsynths.ableton.com/ | Ableton Learning Synths | モジュラー思考の入門（視覚的・体系的） |
| https://www.moogmusic.com/news | Moog Music — Design Philosophy | アナログ合成の設計哲学 |
| https://noisegate.io/modular-synthesis-philosophy | Modular Synthesis Philosophy | Eurorack設計思想、信号フロー設計 |

### ★★ 重要

| URL | 内容 | 取得したい情報 |
|-----|------|--------------|
| https://www.modulargrid.net/e/racks/view/research | ModularGrid | システム設計の実例（人気ラック構成） |
| https://www.perfectcircuit.com/signal/learning-synthesis | Perfect Circuit Signal | West/East Coast合成の違いと設計思想 |
| https://cdm.link/category/modular/ | Create Digital Music — Modular | モジュラー設計の最新動向 |

---

## カテゴリ3: Autechre 技術的深掘り
> 現在の `artist_autechre_aesthetics.md` / `artist_autechre_production.md` の補強
> 保存先: `artist_autechre_deep.md`

### ★★★ 最優先

| URL | 内容 | 取得したい情報 |
|-----|------|--------------|
| https://www.factmag.com/2016/05/06/autechre-interview-elseq/ | Fact Mag — Autechre elseq interview | MaxMSPとSCの具体的な使い方、ランダム性の制御手法 |
| https://www.thewire.co.uk/in-writing/interviews/autechre | The Wire — Autechre interviews | 機材・ワークフロー・美学の詳細 |
| https://www.residentadvisor.net/features/1703 | RA — Autechre feature | ライブセットアップ、Eurorack使用法 |
| https://www.soundonsound.com/people/autechre | Sound On Sound — Autechre | 制作手法の技術的詳細 |
| https://www.youtube.com/watch?v=SZYpv0aph-g | Autechre — AE_LIVE技術解説 | リアルタイム生成アルゴリズムの動作原理（字幕あり） |

### ★★ 重要

| URL | 内容 | 取得したい情報 |
|-----|------|--------------|
| https://www.reddit.com/r/autechre/ | Reddit r/autechre | ファン分析、技術的考察まとめ |
| https://wiki.freesoftware.gr/index.php/Autechre_Production_Techniques | Production Techniques Wiki | 機材リスト、信号フロー推測 |

---

## カテゴリ4: Tim Hecker / Burial 技術的深掘り
> 保存先: `artist_hecker_burial_deep.md`

### ★★★ 最優先

| URL | 内容 | 取得したい情報 |
|-----|------|--------------|
| https://www.thewire.co.uk/in-writing/interviews/tim-hecker | The Wire — Tim Hecker | グラニュラー処理、空間設計の具体的手法 |
| https://www.factmag.com/2013/11/04/tim-hecker-interview/ | Fact Mag — Tim Hecker | Ableton + ハードエフェクトの組み合わせ方 |
| https://www.soundonsound.com/people/burial | Sound On Sound — Burial | 非グリッドリズム、Foleyサンプリング手法 |
| https://www.theguardian.com/music/2007/dec/14/electronicmusic.burial | Guardian — Burial interview | 制作哲学、ツール選択の理由 |
| https://pitchfork.com/features/interview/6396-burial/ | Pitchfork — Burial | サンプリング手法、音響設計の意図 |

---

## カテゴリ5: 生成音楽 / アルゴリズム作曲理論
> 「どうルールを設計して音楽的な自律性を生むか」
> 保存先: `generative_music_theory.md`

### ★★★ 最優先

| URL | 内容 | 取得したい情報 |
|-----|------|--------------|
| https://www.brian-eno.net/articles/generative-music/ | Brian Eno — Generative Music essay | 生成音楽の哲学的定義、複雑性と制御のバランス |
| https://cycling74.com/articles/generative-music-in-max | Cycling '74 — Generative Music | MaxMSP/SCでの生成音楽実装パターン |
| https://toplap.org/wiki/Main_Page | TOPLAP Wiki | ライブコーディング実践、生成音楽の共同体知識 |
| https://tidalcycles.org/docs/ | TidalCycles Documentation | ミニ記法、パターン変換、確率制御の完全リファレンス |
| https://supercollider.github.io/tutorials/ | SuperCollider Tutorials | SC公式チュートリアル（JITLib、ProxySpace） |

### ★★ 重要

| URL | 内容 | 取得したい情報 |
|-----|------|--------------|
| https://www.algorave.com/ | Algorave | ライブコーディングの実践例・哲学 |
| https://music.arts.uci.edu/dobrian/cm/index.html | Computer Music at UC Irvine | アルゴリズム作曲の学術的体系 |
| https://mitpress.mit.edu/9780262539036/the-algorithmic-composer/ | The Algorithmic Composer | アルゴリズム作曲の設計原則（目次/概要） |

---

## カテゴリ6: SuperCollider 高度な使い方
> 現在のSC知識をより深くする
> 保存先: `sc_advanced_techniques.md`

### ★★★ 最優先

| URL | 内容 | 取得したい情報 |
|-----|------|--------------|
| https://doc.sccode.org/Reference/JITLib/ | SC JITLib Reference | Ndef/ProxySpace — ライブコーディング用の動的再定義 |
| https://doc.sccode.org/Classes/Ndef.html | Ndef Documentation | Ndefの設計パターン、MaToMaへの適用可能性 |
| https://doc.sccode.org/Tutorials/Getting-Started/14-Scheduling-Events.html | SC Scheduling | スケジューリング設計、TempoClock、Routine vs Task |
| https://scsynth.org/t/techniques-for-building-adaptive-music-systems/7337 | scsynth.org — Adaptive Music | アダプティブ音楽システムの設計パターン |
| https://composerprogrammer.com/teaching/supercollider/sctutorial/tutorial.html | SC Tutorial (Nick Collins) | SC設計の上級者向け解説 |

### ★★ 重要

| URL | 内容 | 取得したい情報 |
|-----|------|--------------|
| https://github.com/supercollider/supercollider/wiki | SC GitHub Wiki | バグ回避、最適化パターン |
| https://scsynth.org/ | scsynth.org フォーラム | 実践的な問題解決、設計相談事例 |
| https://doc.sccode.org/Classes/Server.html | Server class docs | scsynth設定、パフォーマンス最適化 |

---

## カテゴリ7: FluCoMa（音響ML・特徴量解析）
> 現在の `plugins_flucoma.md` の補強
> 保存先: `flucoma_advanced.md`

### ★★★ 最優先

| URL | 内容 | 取得したい情報 |
|-----|------|--------------|
| https://learn.flucoma.org/ | FluCoMa Learning | 音響MLのチュートリアル、実用的な特徴量抽出 |
| https://www.flucoma.org/make/ | FluCoMa Make | 実際の作品例・制作ワークフロー |
| https://github.com/flucoma/flucoma-sc | FluCoMa SC GitHub | SC向け実装例、最新API |
| https://learn.flucoma.org/reference/mfcc/ | MFCC Reference | 音色特徴量の技術的説明 |
| https://learn.flucoma.org/reference/noveltyslice/ | NoveltySlice | 自動セグメンテーション手法 |

---

## カテゴリ8: 音楽制作ワークステーション設計
> 「どうシステムを設計するか」の上位概念
> 保存先: `workstation_system_design.md`

### ★★★ 最優先

| URL | 内容 | 取得したい情報 |
|-----|------|--------------|
| https://www.ableton.com/en/articles/what-makes-a-great-live-set/ | Ableton — Great Live Set | ライブセットの設計原則、人間-機械インタラクション |
| https://www.soundonsound.com/techniques/live-electronic-music-setup | Sound On Sound — Live Setup | ライブ電子音楽のシステム設計実践 |
| https://cdm.link/2018/09/whats-system-live-performance/ | CDM — Performance System | パフォーマンスシステムの設計思想 |
| https://monome.org/docs/norns/studies/ | Norns Studies | Nornsの音楽システム設計（MaToMaのアーキテクチャ参照元） |
| https://llllllll.co/t/norns-study-group/14773 | Lines Forum — Norns Study | Norns設計のコミュニティ議論 |

### ★★ 重要

| URL | 内容 | 取得したい情報 |
|-----|------|--------------|
| https://www.native-instruments.com/en/specials/reaktor-6/blocks/ | NI Reaktor Blocks | モジュラー設計のGUI実装例 |
| https://vcvrack.com/manual/ | VCV Rack Manual | ソフトウェアEurorackの設計哲学 |
| https://www.sweetwater.com/insync/what-is-modular-synthesis/ | Sweetwater — Modular Synthesis | モジュラー合成の概念的説明 |

---

## カテゴリ9: 音楽理論 × 電子音楽
> 「音楽的に正しい構造」を電子音楽で実装する方法
> 保存先: `music_theory_electronic.md`

### ★★★ 最優先

| URL | 内容 | 取得したい情報 |
|-----|------|--------------|
| https://www.musictheory.net/ | musictheory.net | 基礎理論（スケール、和声）の体系的整理 |
| https://www.soundonsound.com/techniques/harmony-theory-electronic-music | SOS — Harmony in Electronic Music | 電子音楽でのハーモニー・調性設計 |
| https://www.youtube.com/watch?v=rHqkeLxAsTc | Adam Neely — Groove Analysis | グルーヴの科学的分析（リズム揺らぎ） |
| https://www.reddit.com/r/musictheory/wiki/resources | r/musictheory Resources | 音楽理論の学習リソース体系 |
| https://www.ethanhein.com/wp/2014/groove/ | Ethan Hein — Groove | グルーヴとリズム知覚の理論 |

---

## 優先スクレーピング順序（推奨）

```
Round 1（最重要・すぐ効果あり）:
1. https://ccrma.stanford.edu/~jos/pasp/         ← 心理音響基礎
2. https://www.musicdsp.org/en/latest/            ← DSPレシピ集
3. https://learn.flucoma.org/                     ← FluCoMa学習
4. https://tidalcycles.org/docs/                  ← Tidal完全リファレンス
5. https://monome.org/docs/norns/studies/         ← Nornsシステム設計

Round 2（設計哲学）:
6. https://www.brian-eno.net/articles/generative-music/
7. https://www.factmag.com/2016/05/06/autechre-interview-elseq/
8. https://toplap.org/wiki/Main_Page
9. https://msp.ucsd.edu/techniques/latest/book.pdf （PDF）
10. https://doc.sccode.org/Reference/JITLib/

Round 3（アーティスト深掘り）:
11. Autechre インタビュー群
12. Tim Hecker インタビュー群
13. Burial インタビュー群

Round 4（システム設計）:
14. Ableton/VCV/Reaktor設計資料
15. モジュラー設計哲学資料
```

---

## スクレーピング後の保存ルール

スクレーピングしたコンテンツは以下の形式で保存すること:

```markdown
# [カテゴリ名] — [ファイル名].md

> ソース: [URL]
> 取得日: YYYY-MM-DD
> 関連ナレッジ: [既存ファイル名との関係]

## [セクション名]

[コンテンツ]

## Claude向け使用ガイド

このファイルは以下の状況で参照する:
- [状況1]
- [状況2]

キーワード: [日本語タグ]
```
