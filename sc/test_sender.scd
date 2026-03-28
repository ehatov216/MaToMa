/*
MaToMa: SC テスト送信スクリプト
================================
Python ブリッジ（bridge.py）が起動していることを確認してから
このスクリプトを実行してください。

使い方:
1. ターミナルで: cd MaToMa && python3 backend/bridge.py
2. ブラウザで: frontend/index.html を開く
3. このファイルを SuperCollider で開き、Cmd+A → Cmd+Enter で実行
*/

(
// Python ブリッジが待ち受けるアドレス（ポート9000）
~bridge = NetAddr("127.0.0.1", 9000);

"MaToMa: Pythonブリッジへの接続準備完了".postln;
"以下のコードブロックで個別にテスト送信できます".postln;
)

// ── テスト送信1: 単純な値 ──
(
~bridge.sendMsg("/matoma/test", "hello", 42, 0.75);
"送信: /matoma/test".postln;
)

// ── テスト送信2: パラメーター更新 ──
(
~bridge.sendMsg("/matoma/param/cutoff", 0.5);
"送信: /matoma/param/cutoff = 0.5".postln;
)

// ── テスト送信3: 1秒ごとに値が変わる繰り返し送信 ──
(
Routine({
    10.do { |i|
        var val = i / 9.0;  // 0.0 〜 1.0
        ~bridge.sendMsg("/matoma/param/cutoff", val);
        "送信 [%/9]: /matoma/param/cutoff = %".format(i, val.round(0.01)).postln;
        1.wait;
    };
    "繰り返し送信完了".postln;
}).play;
)

// ── 停止 ──
(
~bridge.sendMsg("/matoma/stop", 0);
"送信: /matoma/stop".postln;
)
