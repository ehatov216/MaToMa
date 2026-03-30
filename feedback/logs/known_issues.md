# MaToMa 既知の問題と解決策

> 更新日: 2026-03-30
> 再発防止・最速解決のためのトラブルシューティングログ

---

## 🔇 音が出ない問題

### 問題Y: LocalIn/LocalOut フィードバックがSCサーバー全体をミュートする【2026-03-30 修正済み】

**症状:** MaToMa起動後にドローンも他アプリ（Spotify等）も一切音が出なくなる
**根本原因:** `matoma_drone` SynthDef内の `LocalIn/LocalOut` フィードバックループが
  起動直後に信号が発散し、SCサーバーの音量保護機能（Volume Protection）が
  全出力をミュートする。これがCoreAudio経由で他アプリの音も止める。
**修正（2026-03-30）:**
  - `LocalIn/LocalOut` を完全削除
  - `AllpassC` 連鎖 + `Limiter(0.9)` でフィードバック感を安全に代替
  - `feedback_amt` パラメーターは AllpassC のmix量として機能を維持
**診断手順:**
  1. シンプルな `{ SinOsc.ar(440) }.play` で音が出るか確認
  2. `SynthDef` に `LocalIn/LocalOut` を追加した瞬間に無音になるか確認
  3. 無音になれば本問題
**教訓:** LocalIn/LocalOut は高いフィードバック量（>0.5）+ Klankの長いdecayと
  組み合わせると起動直後に発散しやすい。必ずLimiterで保護するか、
  AllpassCで代替する。

---

### 問題X: MaToMa起動時に他アプリ（Spotify, Music.app等）の音が止まる【根本原因特定・完全修正済み】

**症状:** `./start.sh` を実行すると、他の音楽アプリの音が止まり、再生しても音が出なくなる
**根本原因（3軸すべて修正済み）:**

**原因A: サンプルレート強制 (最重要)**
  - 旧コード `s.options.sampleRate = 44100;` がZoom/外部IFの影響で48kHzになったシステムに対し
    44100Hzを強制 → CoreAudioがデバイスをリセット → 全アプリの音声ストリーム中断
  - **修正（2026-03-29）:** 削除。scsynth はシステムネイティブレートを使用

**原因B: inputStreamsEnabled="0" の誤解釈**
  - 旧コード `s.options.inputStreamsEnabled = "0"` は「ストリーム0のみ無効、それ以外は有効」の意味
  - **修正（2026-03-29）:** 削除（`numInputBusChannels = 0` のみで十分）

**原因C: Python の set_system_audio_output_device() 呼び出し（最終原因）**
  - bridge.py の `start_sc()` と GUI デバイス選択時に CoreAudio API
    `AudioObjectSetPropertyData(kAudioHardwarePropertyDefaultOutputDevice)` を呼んでいた
  - macOS がシステムデフォルト出力デバイスの変更を全アプリに通知
    → Spotify/Music.app 等の音声ストリームが一斉にリセット
  - **修正（2026-03-30）:**
    - Python 側の `set_system_audio_output_device()` 呼び出しを完全に削除
    - SC 側で `s.options.outDevice = "<デバイス名>"` を使用（他アプリに影響しない API）
    - run_headless.scd 起動時に audio_device.txt を読んで `s.options.outDevice` に設定

**確認方法:**
  1. Spotify で音楽を再生したまま `./start.sh` を実行する
  2. Spotify の再生が継続されれば修正成功
  3. `./start.sh` 後のログに `出力デバイス: 'XXX' (audio_device.txt より設定)` が出れば正常

---

### 問題0: SCがZoom/rekordbox仮想デバイスに出力している【最頻出】

**症状:** ブリッジログに「テスト音再生」は出るが全く音が聞こえない
**原因:** ZoomAudioDevice または rekordbox Aggregate Device がSCのデフォルト出力になっている
**解決策（UIから）:** GUIの「AUDIO DEVICE」セレクターで正しいデバイスを選択 → 次回以降は自動適用
**解決策（CLIから）:**
```bash
echo -n "MacBook Proのスピーカー" > backend/audio_device.txt
./start.sh
```
ログに `保存済みオーディオデバイスを適用: 'MacBook Proのスピーカー'` と出れば正しい
**ステータス:** 2026-03-29 bridge.py の起動時適用 + UIからの永続保存 で恒久対応済み
**注:** 旧「ステータス済み」はコードに反映されていなかったバグ（2026-03-29修正）

---

### 問題1: SCのオーディオデバイスが違うデバイスに出力されている

**症状:** ブリッジログに「テスト音再生 (880Hz)」は出るが音が聞こえない
**原因:** macOSに複数のオーディオデバイスがある場合（rekordbox Aggregate Device等）、SCが意図しないデバイスに出力する
**解決策:**
1. macOS「システム設定 → サウンド → 出力」で正しいデバイスを選択
2. `run_headless.scd` の `s.options.outDevice_` で明示的にデバイスを指定
3. SC再起動（`./start.sh`）

**確認方法:** ブリッジログに `[SC] outDevice: MacBook Proのスピーカー` が出ていれば正しいデバイス

---

### 問題2: 再セットアップ後に音が出ない

**症状:** ↺ 再セットアップを押した後ドローンが聞こえない
**原因(1):** `Synth(\matoma_effect_out)` に `inBus` 引数を渡さなかった → バス0フィードバックループ
**解決策(1):** 再セットアップハンドラーで必ず `[\inBus, ~effectBus, \out, 0]` を渡す
**原因(2):** Droneのアタックタイム4秒 → 起動直後は音量ゼロ
**解決策(2):** 再セットアップ時は `[\atk, 0.5]` で即座にフェードイン
**ステータス:** 2026-03-29 修正済み

---

### 問題3: FreqShift.ar を使うと音が出ない

**症状:** SynthDef定義完了ログは出るが音が出ない
**原因:** `FreqShift.ar` は sc3-plugins が必要。未インストール時はサーバー側でサイレントに失敗
**解決策:** `FreqShift.ar` の代わりに `AllpassC.ar + DelayC.ar`（ビルトインのみ）を使う
**ステータス:** 2026-03-29 修正済み（FreqShift削除）
**チェックリスト:** SynthDef内で以下を使う前にsc3-pluginsの有無を確認
- `FreqShift.ar` ← 要sc3-plugins
- `MoogFF.ar` ← 要sc3-plugins
- `SVF.ar` ← 要sc3-plugins

---

### 問題4: ステップシーケンサーのSTARTを押しても音が出ない

**症状:** パッドをONにしてSTARTを押しても何も聞こえない
**原因:** `~percSteps` が全部0（OFF）のままだった。SCATTERは確率だけ設定してステップをONにしていなかった
**解決策:** SCATTER実行時に確率>30%のステップを自動でONにする
**ステータス:** 2026-03-29 修正済み

---

### 問題5: CHAOS ENGINE の START CHAOS が反応しない

**症状:** START CHAOSを押しても音が出ない
**原因:** SC側の `~startChaosEngine` 内Routineで `var` 宣言がloop内にあった（SyntaxError）。`doUntil`も標準SCに存在しない
**解決策:** `var` 宣言をRoutine関数の先頭に移動。`doUntil`を`wchoose`に置換
**ステータス:** 2026-03-29 修正済み

---

## 🔌 接続問題

### 問題6: ブラウザに「WebSocket not found」エラー

**症状:** ブラウザでlocalhost:8765を直接開くとエラー
**原因:** ブラウザはWebSocketサーバーに直接接続不可
**解決策:** `open /path/to/frontend/index.html` でHTMLファイルを直接開く

---

### 問題7: SC起動タイムアウト

**症状:** bridge.pyが「SC起動タイムアウト（60秒）」を報告
**原因:** 既存のsclang/scsynthプロセスがポート競合
**解決策:** `pkill -f sclang && pkill -f scsynth` してから `./start.sh`

---

## 🔧 デバッグ手順（音が出ない場合）

```
Step 1: ♪ テストボタンを押す
  → ブリッジログに「テスト音再生 (880Hz)」が出るか確認
  → 出る: SC動作OK → オーディオデバイス設定を確認（問題1）
  → 出ない: SCへのメッセージが届いていない → WebSocket確認

Step 2: ブリッジログを確認
  tail -f /path/to/tasks/[task_id].output
  → 「SCへ転送: /matoma/test_tone」が出るか確認

Step 3: SCプロセス確認
  ps aux | grep sclang
  → プロセスがなければ ./start.sh で再起動

Step 4: それでも出ない → ↺ 再セットアップ → Step 1 へ
```

---

## 📋 定期チェックリスト（コード更新後）

- [ ] `./start.sh` で起動
- [ ] ♪ テストボタン → ビープ音が1.5秒聞こえる
- [ ] ↺ 再セットアップ → 0.5秒後にドローンが聞こえる
- [ ] SynthDef内でsc3-plugins依存UGenを使っていないか確認
