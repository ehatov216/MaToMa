/*
MaToMa: アンビエント・ドローンモジュール
==========================================
複数のオシレーターをゆっくり揺らし続けるドローン音源。
池田良治・Alva Noto 的な「持続する音の空間」を目指す。

音の仕組み:
  - 4本のサイン波を根音からわずかにずらして重ねる（デチューン）
  - LFO（ゆっくり揺れる波）がデチューンとフィルターを自律的に動かす
  - リバーブで空間の広がりをつける

使い方:
  1. このファイルを SuperCollider で開く
  2. Cmd+A → Cmd+Enter で全体を実行
  3. ブラウザのスライダー、または OSC メッセージで音を制御する

パラメーター:
  freq   : 根音（Hz）。低いほど重い。40=超低域、110=低域、220=中低域
  detune : 揺らぎの広がり（0.0〜1.0）。大きいほど音が太く・揺れる
  cutoff : 音の明るさ（Hz）。低い=こもった・暗い、高い=開いた・明るい
  drift  : 自律ゆらぎの速度（0.0〜1.0）。大きいほど変化が速い
  room   : 空間の広さ=リバーブ（0.0〜1.0）。大きいほど洞窟のような残響
  amp    : 音量（0.0〜1.0）

OSC アドレス（ブラウザ・Pythonから送る）:
  /matoma/drone/start  → ドローンを開始
  /matoma/drone/stop   → ドローンをフェードアウトして停止
  /matoma/drone/param  → パラメーター更新 [アドレス, 名前, 値]
                         例: ['/matoma/drone/param', 'detune', 0.5]
*/

(
s.waitForBoot({

    // ── ドローンのシンセ定義 ────────────────────────────────────────
    //
    // 「なぜサイン波4本か」:
    //   ノコギリ波（既存の matoma_basic）は倍音が多くザラザラした音。
    //   サイン波は倍音がない純粋な音で、重ねてゆっくり動かすと
    //   アンビエントに特有の「霞がかかったような」テクスチャになる。
    //
    SynthDef(\matoma_drone, {
        arg freq = 60,
            detune = 0.3,     // 揺らぎ幅（0=ユニゾン、1=最大に広がる）
            cutoff = 800,
            drift = 0.1,      // LFO速度の基準（0=ほぼ静止、1=速い）
            room = 0.6,
            amp = 0.4,
            gate = 1;

        // ── LFO: 音を自律的にゆっくり動かす「呼吸」 ──────────────
        // LFOSpeed: drift が 0.0〜1.0 の値を 0.01〜0.3 Hz に変換
        // （0.01 Hz ≈ 100秒周期のゆっくりした揺れ）
        var lfoSpeed   = drift.linexp(0, 1, 0.01, 0.3);
        var lfoDetune  = LFNoise2.kr(lfoSpeed).range(0.98, 1.02);   // デチューン揺れ
        var lfoCutoff  = LFNoise1.kr(lfoSpeed * 0.7).range(0.7, 1.4); // フィルター揺れ

        // ── 4本のオシレーター（それぞれわずかにずれた周波数）────────
        // detune=0.3 のとき ±15 Hz 程度ずれる → 音が太くなる
        var detuneHz = freq * detune * 0.05;  // detune を Hz オフセットに変換
        var sig1 = SinOsc.ar(freq                           * lfoDetune);
        var sig2 = SinOsc.ar((freq + detuneHz * 0.5)        * lfoDetune, 0.25pi);
        var sig3 = SinOsc.ar((freq - detuneHz * 0.3)        * lfoDetune, 0.5pi);
        var sig4 = SinOsc.ar((freq + detuneHz) * 2          * lfoDetune, 0.75pi);
        // sig4 は1オクターブ上のハーモニクスで「倍音の輪郭」を添える

        var sig = (sig1 + sig2 + sig3 + sig4) * 0.25; // 4本を混ぜて音量を正規化

        // ── ローパスフィルター: 高域を削って音を丸くする ───────────
        // cutoff に LFO を掛けて、フィルターがゆっくり動く
        sig = RLPF.ar(sig, (cutoff * lfoCutoff).clip(80, 16000), 0.4);

        // ── エンベロープ: 音の立ち上がり・フェードアウト ───────────
        // attack=5.0 秒でゆっくり立ち上がる（アンビエントらしい滑らかさ）
        sig = sig * Linen.kr(gate, 5.0, 1.0, 8.0, 2);

        // ── リバーブ: 空間の広がり ──────────────────────────────
        // FreeVerb: room が大きいほど長い残響（洞窟・大聖堂のイメージ）
        sig = FreeVerb.ar(sig, mix: room, room: room, damp: 0.4);

        sig = sig * amp;

        Out.ar(0, sig ! 2);  // ステレオ出力
    }).add;

    "シンセ定義完了: \\matoma_drone".postln;

    // ── OSC リスナーの設定 ──────────────────────────────────────────
    // ブラウザ → Python → OSC → ここで受け取る

    ~currentDrone = nil;  // 現在鳴っているドローンを記憶する変数

    // ドローンを開始する
    OSCdef(\matoma_drone_start, { |msg|
        {
            if (~currentDrone.notNil) {
                ~currentDrone.set(\gate, 0);  // 既存の音をフェードアウト
            };
            ~currentDrone = Synth(\matoma_drone);
            "ドローン開始".postln;
        }.defer;
    }, '/matoma/drone/start');

    // ドローンを停止する（ゆっくりフェードアウト）
    OSCdef(\matoma_drone_stop, { |msg|
        {
            if (~currentDrone.notNil) {
                ~currentDrone.set(\gate, 0);  // gate=0 → エンベロープがフェードアウト開始
                ~currentDrone = nil;
                "ドローン停止（フェードアウト中）".postln;
            };
        }.defer;
    }, '/matoma/drone/stop');

    // パラメーターをリアルタイム更新する
    // msg の形式: ['/matoma/drone/param', 'パラメーター名', 値]
    // 例: ['/matoma/drone/param', 'detune', 0.5]
    OSCdef(\matoma_drone_param, { |msg|
        var param = msg[1].asSymbol;
        var value = msg[2].asFloat;
        {
            if (~currentDrone.notNil) {
                ~currentDrone.set(param, value);
                "ドローン パラメーター更新: % = %".format(param, value.round(0.001)).postln;
            };
        }.defer;
    }, '/matoma/drone/param');

    "MaToMa ドローンモジュール起動完了。".postln;
    "コマンド例:".postln;
    "  ドローン開始 → NetAddr('127.0.0.1', 57120).sendMsg('/matoma/drone/start')".postln;
    "  周波数変更  → NetAddr('127.0.0.1', 57120).sendMsg('/matoma/drone/param', 'freq', 55)".postln;
    "  停止        → NetAddr('127.0.0.1', 57120).sendMsg('/matoma/drone/stop')".postln;
});
)
