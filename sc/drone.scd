/*
MaToMa: アンビエント・ドローンモジュール
==========================================
複数のサイン波をゆっくり揺らし続ける、持続する音の空間。
LFOがcutoff（音の明るさ）を自律的にゆっくり動かし続ける。

【音の仕組みのイメージ】
  ・ドローン = 低音を長く伸ばし、少しずつ変化させる「地面のような音」
  ・4本の音をわずかにずらして重ねる（デチューン）→ 揺れる・太い音に
  ・LFO = 「ゆっくり揺れる波」。呼吸するように cutoff を上下させる
  ・drift を上げるほど、誰も触らなくても音が変化し続ける（自律モード）

【パラメーター】
  freq   : 根音の高さ（Hz）。40=超低域、60=低域、110=中低域
  detune : 音の揺らぎ・厚み（0.0〜1.0）。大きいほど太くゆったりした音
  cutoff : 音の明るさの基準値（Hz）。低い=暗い・こもった、高い=明るい・開いた
  drift  : LFOの速度と深度（0.0〜1.0）。0=ほぼ静止、1=大きく・速く揺れる
  room   : 空間の広さ・残響（0.0〜1.0）。大きいほど洞窟のような広がり
  amp    : 音量（0.0〜1.0）

【OSCアドレス】
  /matoma/drone/start         → ドローン開始
  /matoma/drone/stop          → ドローンをフェードアウトして停止
  /matoma/drone/param [名前] [値] → パラメーター更新
    例: /matoma/drone/param detune 0.6

【単独での使い方】
  1. SuperCollider でこのファイルを開く
  2. Cmd+A → Cmd+Enter で全体を実行
  3. ブラウザのスライダーか、下記の「動作確認」ブロックで操作する

────────────────────────────────────────────────────────────────────
【run_headless.scd への組み込み方】

  run_headless.scd の s.waitForBoot({ ... }) の中、
  既存の OSCdef の定義の後ろ（"MaToMa 起動完了" の前）に
  ▼▼▼ ここから ▼▼▼ と ▲▲▲ ここまで ▲▲▲ の間をコピーする。

  コピー後の run_headless.scd のイメージ:

    s.waitForBoot({
        // ... 既存の matoma_basic SynthDef ...
        // ... 既存の OSCdef(\matoma_start) など ...

        // ▼▼▼ ここから（drone.scd より）▼▼▼
        SynthDef(\matoma_drone, { ... }).add;
        s.sync;
        ~currentDrone = nil;
        OSCdef(\matoma_drone_start, ...);
        OSCdef(\matoma_drone_stop,  ...);
        OSCdef(\matoma_drone_param, ...);
        // ▲▲▲ ここまで ▲▲▲

        "MaToMa 起動完了".postln;
    });
────────────────────────────────────────────────────────────────────
*/

(
s.waitForBoot({

    // ▼▼▼ ここから run_headless.scd にコピー ▼▼▼

    // ── SynthDef: アンビエント・ドローン ──────────────────────────────
    SynthDef(\matoma_drone, {
        arg freq   = 60,
            detune = 0.3,
            cutoff = 800,
            drift  = 0.1,
            room   = 0.6,
            amp    = 0.4,
            gate   = 1;

        // SCルール: var宣言はすべて先頭にまとめる
        var lfoRate, lfoSignal, cutoffMod, detuneHz;
        var sigL, sigR, env, sig;

        // ── LFO: drift が速度と深度を同時に制御 ─────────────────────
        //
        // drift = 0.0 → lfoRate ≈ 0.01 Hz（約100秒周期）、変化量ほぼゼロ
        // drift = 0.5 → lfoRate ≈ 0.06 Hz（約17秒周期）、cutoff が±75%揺れる
        // drift = 1.0 → lfoRate ≈ 0.35 Hz（約3秒周期）、cutoff が±150%揺れる
        lfoRate   = drift.clip(0.001, 1).linexp(0.001, 1, 0.01, 0.35);
        lfoSignal = LFNoise1.kr(lfoRate);
        cutoffMod = (cutoff * (1 + lfoSignal * drift * 1.5)).clip(80, 16000);

        // ── オシレーター: L/R で逆方向にデチューン → 真のステレオ ───
        //
        // Lは+方向、Rは-方向にずらすことで、音が左右に広がって聞こえる。
        // サブバス（freq*0.5）で低域の厚みを出し、
        // 三角波（LFTri）は倍音が少なく丸いので温かみを加える。
        detuneHz = freq * detune * 0.08;
        sigL = Mix([
            SinOsc.ar(freq,                      0),
            SinOsc.ar(freq + detuneHz * 0.9,     0.25pi),
            SinOsc.ar(freq + detuneHz * 0.4,     0.6pi),
            SinOsc.ar(freq * 2 + detuneHz * 0.2, 0.1pi)  * 0.4,  // 1オクターブ上
            SinOsc.ar(freq * 0.5,                0.8pi)  * 0.5,  // サブバス
            LFTri.ar(freq - detuneHz * 0.15)            * 0.15,  // 温かみ
        ]) * 0.2;
        sigR = Mix([
            SinOsc.ar(freq,                      0.5pi),
            SinOsc.ar(freq - detuneHz * 0.9,     0.75pi),
            SinOsc.ar(freq - detuneHz * 0.4,     0.3pi),
            SinOsc.ar(freq * 2 - detuneHz * 0.2, 0.9pi)  * 0.4,
            SinOsc.ar(freq * 0.5,                0.2pi)  * 0.5,
            LFTri.ar(freq + detuneHz * 0.15)            * 0.15,
        ]) * 0.2;

        // ── ローパスフィルター（rq=0.7: 緩やか・温かいロールオフ） ──
        sigL = RLPF.ar(sigL, cutoffMod,        0.7);
        sigR = RLPF.ar(sigR, cutoffMod * 0.96, 0.7);

        // ── ソフトサチュレーション → 倍音付加・温かみ ───────────────
        sigL = LeakDC.ar((sigL * 2.5).tanh) * 0.5;
        sigR = LeakDC.ar((sigR * 2.5).tanh) * 0.5;

        // ── エンベロープ ─────────────────────────────────────────────
        env  = Linen.kr(gate, 1.0, 1.0, 8.0, 2);
        sigL = sigL * env;
        sigR = sigR * env;

        // ── ステレオリバーブ（FreeVerb2 = 真のステレオ空間） ─────────
        sig = FreeVerb2.ar(sigL, sigR, mix: room, room: room, damp: 0.5);
        Out.ar(0, sig * amp);
    }).add;

    s.sync;  // SynthDef がサーバーに届くまで待つ

    "シンセ定義完了: \\matoma_drone".postln;

    // ── グローバル変数: 現在鳴っているドローンを記憶 ─────────────────
    ~currentDrone = nil;

    // ── OSCdef: ドローンを開始する ──────────────────────────────────
    OSCdef(\matoma_drone_start, { |msg|
        {
            if (~currentDrone.notNil) {
                ~currentDrone.set(\gate, 0);  // 既存をフェードアウト
            };
            ~currentDrone = Synth(\matoma_drone);
            "ドローン開始".postln;
        }.defer;
    }, '/matoma/drone/start');

    // ── OSCdef: ドローンを停止する ──────────────────────────────────
    // gate=0 を渡すと Linen エンベロープが release（8秒かけてフェードアウト）
    OSCdef(\matoma_drone_stop, { |msg|
        {
            if (~currentDrone.notNil) {
                ~currentDrone.set(\gate, 0);
                ~currentDrone = nil;
                "ドローン停止（8秒でフェードアウト）".postln;
            };
        }.defer;
    }, '/matoma/drone/stop');

    // ── OSCdef: パラメーターをリアルタイム更新 ──────────────────────
    // 受信形式: ['/matoma/drone/param', 'パラメーター名', 値]
    // 例: ['/matoma/drone/param', 'drift', 0.7]
    OSCdef(\matoma_drone_param, { |msg|
        var param = msg[1].asSymbol;
        var value = msg[2].asFloat;
        {
            if (~currentDrone.notNil) {
                ~currentDrone.set(param, value);
                "ドローン param: % = %".format(param, value.round(0.001)).postln;
            };
        }.defer;
    }, '/matoma/drone/param');

    // ▲▲▲ ここまで run_headless.scd にコピー ▲▲▲

    "MaToMa ドローンモジュール起動完了。".postln;
    "".postln;
    "── 動作確認コマンド ──────────────────────────────".postln;
    "ドローン開始: NetAddr('127.0.0.1', 57120).sendMsg('/matoma/drone/start')".postln;
    "根音変更:     NetAddr('127.0.0.1', 57120).sendMsg('/matoma/drone/param', 'freq', 55)".postln;
    "自律ゆらぎ:   NetAddr('127.0.0.1', 57120).sendMsg('/matoma/drone/param', 'drift', 0.8)".postln;
    "停止:         NetAddr('127.0.0.1', 57120).sendMsg('/matoma/drone/stop')".postln;
});
)

// ────────────────────────────────────────────────────────────────────
// 動作確認（このファイルを単独実行中のみ使用）
// 各ブロックを選択して Cmd+Enter で個別に実行できる
// ────────────────────────────────────────────────────────────────────

// ドローンを開始する
// NetAddr("127.0.0.1", 57120).sendMsg('/matoma/drone/start');

// drift を上げて自律ゆらぎを強くする
// NetAddr("127.0.0.1", 57120).sendMsg('/matoma/drone/param', 'drift', 0.8);

// 根音を低くする（重いドローン）
// NetAddr("127.0.0.1", 57120).sendMsg('/matoma/drone/param', 'freq', 40);

// 停止する（8秒でフェードアウト）
// NetAddr("127.0.0.1", 57120).sendMsg('/matoma/drone/stop');
