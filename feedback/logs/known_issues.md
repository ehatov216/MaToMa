# MaToMa 既知の問題と解決策

> 更新日: 2026-03-29
> 再発防止・最速解決のためのトラブルシューティングログ

---

## 🔇 音が出ない問題

### 問題0: SCがZoom/rekordbox仮想デバイスに出力している【最頻出】

**症状:** ブリッジログに「テスト音再生」は出るが全く音が聞こえない
**原因:** ZoomAudioDevice または rekordbox Aggregate Device がSCのデフォルト出力になっている
**解決策:**
```bash
echo -n "MacBook Proのスピーカー" > backend/audio_device.txt
./start.sh
```
ログに `出力デバイス: MacBook Proのスピーカー` と出れば正しい
**ステータス:** 2026-03-29 audio_device.txt の仕組みで恒久対応済み

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
