// ══════════════════════════════════════════════════════════════════
//  MaToMa ikeda_engine.scd  — 池田亮司的 test pattern エンジン
//
//  【設計コンセプト】
//    0/1 ビット列 × 複数グリッド分割で構成する「状態遷移のミニマルミュージック」。
//    毎周回（32ステップ = 2小節）ごとにビット列が微変化（状態遷移）する。
//    DAW的なグルーヴを一切持たず、「整然としているが決して繰り返さない」デジタルパターン。
//
//  【3層構造】
//    Layer 1: 音素材定義 — SynthDef（サイン波/クリック/ノイズのみ）
//    Layer 2: パターン/グリッド定義 — ビット列 × 複数分割 Routine
//    Layer 3: 空間配置 — 幾何学的パンニング（リバーブなし）
//
//  【レーン構成（6レーン）】
//    0: sub    (32分グリッド) — 超低域サイン波（20-80Hz）
//    1: click  (32分グリッド) — Impulse 単発クリック
//    2: sine   (16分グリッド) — 高域サイン波（2の冪乗倍音列）
//    3: noise  (32分グリッド) — ビットクラッシュノイズ
//    4: poly5  (5連符)        — サブバス 5連符（BPMと位相ずれ）
//    5: poly7  (7連符)        — クリック 7連符（BPMと位相ずれ）
//
//  【状態遷移ルール】
//    32ステップ完了ごとに ~ikedaMutate ビットをランダムにフリップ。
//    0 ↔ 1 の反転のみ → 急激に変わらず、ゆっくり姿を変えていく。
//
//  【OSCアドレス一覧】
//    /matoma/ikeda/start               — エンジン開始
//    /matoma/ikeda/stop                — エンジン停止
//    /matoma/ikeda/bpm [val]           — BPM（30-240）
//    /matoma/ikeda/mutate [val]        — 毎周回のフリップ数（0-8）
//    /matoma/ikeda/density [lane][val] — レーンのビット列密度を再生成（0.0-1.0）
//    /matoma/ikeda/layer [n][val]      — レーン ON/OFF（0-5, val=0|1）
//    /matoma/ikeda/amp [val]           — 全体音量（0-1）
//
//  【参照ナレッジ】
//    artist_ikeda_aesthetics.md    → サブバス/超高域/ビットクラッシュ/純音設計
//    design_probability_control.md → ポアソン過程・状態遷移設計
// ══════════════════════════════════════════════════════════════════

// ══════════════════════════════════════════════════════════════════
// ▌ Layer 1: 音素材定義（SynthDef）
//
//   使う波形はサイン波・クリック・ノイズのみ。
//   複雑な合成は一切行わない。
//   全 SynthDef は完全ドライ（リバーブなし）。
//   エンベロープは Attack ≈ 0、指数カーブで急速減衰。
// ══════════════════════════════════════════════════════════════════

// ──────────────────────────────────────────────────────────────────
// sub — 超低域サイン波パルス（20-80Hz）
//
//   「胸腔が瞬間的に動く」物理的サブバス。
//   周波数は発音ごとにランダム（Routine側で exprand で決定）。
//   dur: 10-60ms の短パルス。長すぎると「キック」になる。
// ──────────────────────────────────────────────────────────────────
SynthDef(\ikeda_sub, {
    arg freq = 40, dur = 0.025, amp = 0.9, pan = 0, out = 0;

    var sig, env;

    sig = SinOsc.ar(freq);
    env = EnvGen.ar(Env([1, 0.0001], [dur], \exp), doneAction: 2);

    Out.ar(out, Pan2.ar(sig * env * amp, pan));
}).add;

// ──────────────────────────────────────────────────────────────────
// click — Impulse 単発クリック
//
//   1サンプルのインパルス + 3ms の指数カーブで減衰。
//   「デジタルの最小単位」。周波数の概念を持たない純粋なクリック。
//   amp の二値性（鳴る/鳴らない）のみで表現。
// ──────────────────────────────────────────────────────────────────
SynthDef(\ikeda_click, {
    arg amp = 0.6, pan = 0, out = 0;

    var sig, env;

    sig = Impulse.ar(0);
    env = EnvGen.ar(Env([1, 0.0001], [0.003], \exp), doneAction: 2);

    Out.ar(out, Pan2.ar(sig * env * amp, pan));
}).add;

// ──────────────────────────────────────────────────────────────────
// sine — 高域純粋サイン波（倍音列）
//
//   池田亮司的倍音列 [55, 110, 220, 440, 880, 1760, 3520, 8800] から選択。
//   freqIdx (0-7) で音程を指定。Routine 側で rrand(0, 7) でランダム選択。
//   dur: 10-50ms の短バースト。
// ──────────────────────────────────────────────────────────────────
SynthDef(\ikeda_sine, {
    arg freqIdx = 4, dur = 0.02, amp = 0.4, pan = 0, out = 0;

    var freqTable, freq, sig, env;

    // 2の冪乗倍音列（データソニフィケーション的な純音列）
    freqTable = [55, 110, 220, 440, 880, 1760, 3520, 8800];
    freq = Select.kr(freqIdx.clip(0, 7), freqTable);

    sig = SinOsc.ar(freq);
    env = EnvGen.ar(Env([1, 0.0001], [dur], \exp), doneAction: 2);

    Out.ar(out, Pan2.ar(sig * env * amp, pan));
}).add;

// ──────────────────────────────────────────────────────────────────
// noise — ビットクラッシュノイズバースト
//
//   WhiteNoise を round(2^-bits) で量子化（ビット削減）。
//   bits = 2 → 4段階、bits = 5 → 32段階。
//   bits が小さいほど粗く歪む（デジタルエラー感）。
//   HPF(3000Hz) で高域成分のみ残す。
// ──────────────────────────────────────────────────────────────────
SynthDef(\ikeda_noise, {
    arg bits = 3, dur = 0.008, amp = 0.35, pan = 0, out = 0;

    var step, noise, filtered, env;

    step     = 2 ** bits.neg;                // 量子化ステップ幅
    noise    = WhiteNoise.ar.round(step);    // ビットクラッシュ
    filtered = HPF.ar(noise, 3000);          // 高域成分のみ

    env = EnvGen.ar(Env([1, 0.0001], [dur], \exp), doneAction: 2);

    Out.ar(out, Pan2.ar(filtered * env * amp, pan));
}).add;

s.sync;
"IKEDA ENGINE SynthDef 登録完了 (sub / click / sine / noise)".postln;


// ══════════════════════════════════════════════════════════════════
// ▌ Layer 3: 空間配置（パンニングマップ）
//
//   各レーンに固定パン位置を割り当てる（幾何学的・デジタル的配置）。
//   自然な空間感ではなく、チャンネルの「位置決め」。
//   リバーブは一切使用しない。
// ══════════════════════════════════════════════════════════════════

//       lane:    sub    click  sine   noise  poly5  poly7
~ikedaPanMap = [ -1.0,   0.5,  -0.5,   0.0,   1.0,  -0.3 ];

"IKEDA ENGINE 空間配置マップ設定完了".postln;


// ══════════════════════════════════════════════════════════════════
// ▌ Layer 2: パターン/グリッド定義
//
//   ビット列（Array of 0|1）× 複数グリッド分割。
//   32ステップ完了ごとに ~ikedaMutate ビットをフリップ（状態遷移）。
// ══════════════════════════════════════════════════════════════════

// ── グローバル状態 ────────────────────────────────────────────────

~ikedaBpm      = 120.0;
~ikedaAmp      = 0.7;
~ikedaMutate   = 1;        // 毎周回フリップするビット数
~ikedaLayers   = Array.fill(6, { true });  // レーン ON/OFF フラグ

// 6レーンのビット列（初期密度 0.5 のランダム）
// sizes: sub=32, click=32, sine=16, noise=32, poly5=5, poly7=7
~ikedaBits = [
    Array.fill(32, { 0.5.coin.asInteger }),  // 0: sub
    Array.fill(32, { 0.5.coin.asInteger }),  // 1: click
    Array.fill(16, { 0.5.coin.asInteger }),  // 2: sine（16分 = 32分の半分）
    Array.fill(32, { 0.5.coin.asInteger }),  // 3: noise
    Array.fill(5,  { 0.5.coin.asInteger }),  // 4: poly5
    Array.fill(7,  { 0.5.coin.asInteger }),  // 5: poly7
];

// ── ビット列操作関数 ────────────────────────────────────────────────

// 指定レーンの n ビットをランダムにフリップ（0↔1）
~ikedaMutateLane = { |laneIdx, n=1|
    var arr, indices;
    arr     = ~ikedaBits[laneIdx];
    indices = (0..(arr.size - 1)).scramble.keep(n);
    indices.do { |i| arr[i] = 1 - arr[i]; };
};

// 指定レーンのビット列を密度 density で再生成
~ikedaRegenLane = { |laneIdx, density=0.5|
    var sizes;
    sizes = [32, 32, 16, 32, 5, 7];
    ~ikedaBits[laneIdx] = Array.fill(sizes[laneIdx], { density.coin.asInteger });
    "ikeda/density: lane=% density=%".format(laneIdx, density.round(0.01)).postln;
};

// ── Routine 参照変数 ──────────────────────────────────────────────

~ikedaRoutine32   = nil;  // メイングリッド（sub/click/sine/noise）
~ikedaRoutinePoly5 = nil;  // 5連符
~ikedaRoutinePoly7 = nil;  // 7連符

// ── エンジン起動関数 ──────────────────────────────────────────────

~startIkedaEngine = {
    var step32, step5, step7;

    // 既存 Routine を停止
    if (~ikedaRoutine32.notNil)    { ~ikedaRoutine32.stop;    ~ikedaRoutine32 = nil; };
    if (~ikedaRoutinePoly5.notNil) { ~ikedaRoutinePoly5.stop; ~ikedaRoutinePoly5 = nil; };
    if (~ikedaRoutinePoly7.notNil) { ~ikedaRoutinePoly7.stop; ~ikedaRoutinePoly7 = nil; };

    // ParGroup 確保
    ~ikedaGroup = ParGroup.new;

    // ── Routine 1: メイングリッド（32分ベース）────────────────────
    step32 = 0;
    ~ikedaRoutine32 = Routine({
        loop {
            var stepDur32, sineStep;

            // 32分音符の長さ（毎ループで BPM 変更を即時反映）
            stepDur32 = 60.0 / ~ikedaBpm / 8;

            // ── lane 0: sub（超低域サイン波）──────────────────────
            if (~ikedaLayers[0] && { ~ikedaBits[0][step32] == 1 }) {
                Synth(\ikeda_sub, [
                    \freq,  exprand(20, 80),
                    \dur,   rrand(0.012, 0.05),
                    \amp,   ~ikedaAmp * rrand(0.75, 1.0),
                    \pan,   ~ikedaPanMap[0],
                    \out,   0
                ]);
            };

            // ── lane 1: click（Impulse クリック）─────────────────
            if (~ikedaLayers[1] && { ~ikedaBits[1][step32] == 1 }) {
                Synth(\ikeda_click, [
                    \amp,   ~ikedaAmp * rrand(0.5, 0.9),
                    \pan,   ~ikedaPanMap[1],
                    \out,   0
                ]);
            };

            // ── lane 3: noise（ビットクラッシュ）─────────────────
            if (~ikedaLayers[3] && { ~ikedaBits[3][step32] == 1 }) {
                Synth(\ikeda_noise, [
                    \bits,  rrand(2, 5),
                    \dur,   rrand(0.004, 0.018),
                    \amp,   ~ikedaAmp * rrand(0.4, 0.75),
                    \pan,   ~ikedaPanMap[3],
                    \out,   0
                ]);
            };

            // ── lane 2: sine（16分 = 2ステップに1回）────────────
            sineStep = step32.div(2);
            if ((step32 % 2 == 0) && ~ikedaLayers[2] && { ~ikedaBits[2][sineStep] == 1 }) {
                Synth(\ikeda_sine, [
                    \freqIdx, rrand(0, 7),
                    \dur,     rrand(0.01, 0.04),
                    \amp,     ~ikedaAmp * rrand(0.35, 0.65),
                    \pan,     ~ikedaPanMap[2],
                    \out,     0
                ]);
            };

            // ── 32ステップ完了 → 状態遷移（ビットフリップ）────────
            step32 = (step32 + 1) % 32;
            if (step32 == 0) {
                [0, 1, 2, 3].do { |lane|
                    ~ikedaMutate.do { ~ikedaMutateLane.(lane, 1); };
                };
            };

            stepDur32.wait;
        }
    }).play(TempoClock.default);

    // ── Routine 2: poly5（5連符、2小節を5分割）──────────────────
    step5 = 0;
    ~ikedaRoutinePoly5 = Routine({
        loop {
            var stepDur5;
            // 2小節分を5分割
            stepDur5 = (60.0 / ~ikedaBpm * 2) / 5;

            if (~ikedaLayers[4] && { ~ikedaBits[4][step5] == 1 }) {
                Synth(\ikeda_sub, [
                    \freq,  exprand(20, 55),
                    \dur,   rrand(0.02, 0.06),
                    \amp,   ~ikedaAmp * 0.65,
                    \pan,   ~ikedaPanMap[4],
                    \out,   0
                ]);
            };

            // 5連符レーンも状態遷移（5ステップ完了ごと）
            step5 = (step5 + 1) % 5;
            if (step5 == 0) {
                ~ikedaMutate.do { ~ikedaMutateLane.(4, 1); };
            };

            stepDur5.wait;
        }
    }).play(TempoClock.default);

    // ── Routine 3: poly7（7連符、2小節を7分割）──────────────────
    step7 = 0;
    ~ikedaRoutinePoly7 = Routine({
        loop {
            var stepDur7;
            // 2小節分を7分割
            stepDur7 = (60.0 / ~ikedaBpm * 2) / 7;

            if (~ikedaLayers[5] && { ~ikedaBits[5][step7] == 1 }) {
                Synth(\ikeda_click, [
                    \amp,   ~ikedaAmp * 0.5,
                    \pan,   ~ikedaPanMap[5],
                    \out,   0
                ]);
            };

            // 7連符レーンも状態遷移（7ステップ完了ごと）
            step7 = (step7 + 1) % 7;
            if (step7 == 0) {
                ~ikedaMutate.do { ~ikedaMutateLane.(5, 1); };
            };

            stepDur7.wait;
        }
    }).play(TempoClock.default);

    "IKEDA ENGINE 開始 (BPM: %, mutate: %/周回)".format(
        ~ikedaBpm.round(0.1), ~ikedaMutate).postln;
};

// ── エンジン停止関数 ──────────────────────────────────────────────

~stopIkedaEngine = {
    if (~ikedaRoutine32.notNil)    { ~ikedaRoutine32.stop;    ~ikedaRoutine32 = nil; };
    if (~ikedaRoutinePoly5.notNil) { ~ikedaRoutinePoly5.stop; ~ikedaRoutinePoly5 = nil; };
    if (~ikedaRoutinePoly7.notNil) { ~ikedaRoutinePoly7.stop; ~ikedaRoutinePoly7 = nil; };
    "IKEDA ENGINE 停止".postln;
};

"IKEDA ENGINE パターンシステム設定完了".postln;


// ══════════════════════════════════════════════════════════════════
// ▌ OSCdef 登録
// ══════════════════════════════════════════════════════════════════

// ── /matoma/ikeda/start ──────────────────────────────────────────
OSCdef(\matoma_ikeda_start, { |msg|
    { ~startIkedaEngine.(); }.defer;
}, '/matoma/ikeda/start', nil, 57200);

// ── /matoma/ikeda/stop ───────────────────────────────────────────
OSCdef(\matoma_ikeda_stop, { |msg|
    { ~stopIkedaEngine.(); }.defer;
}, '/matoma/ikeda/stop', nil, 57200);

// ── /matoma/ikeda/bpm [val] ──────────────────────────────────────
// Routine内で毎ループ参照するのでリアルタイムに反映される
OSCdef(\matoma_ikeda_bpm, { |msg|
    var val = msg[1].asFloat;
    {
        ~ikedaBpm = val.clip(30, 240);
        "ikeda/bpm: %".format(~ikedaBpm.round(0.1)).postln;
    }.defer;
}, '/matoma/ikeda/bpm', nil, 57200);

// ── /matoma/ikeda/mutate [val] ───────────────────────────────────
// val: 0-8（毎周回フリップするビット数。0=固定, 8=高速変化）
OSCdef(\matoma_ikeda_mutate, { |msg|
    var val = msg[1].asInteger;
    {
        ~ikedaMutate = val.clip(0, 8);
        "ikeda/mutate: %/周回".format(~ikedaMutate).postln;
    }.defer;
}, '/matoma/ikeda/mutate', nil, 57200);

// ── /matoma/ikeda/density [lane] [val] ───────────────────────────
// lane: 0-5, val: 0.0-1.0（1.0=全ステップON）
// ビット列を指定密度で再生成する
OSCdef(\matoma_ikeda_density, { |msg|
    var lane    = msg[1].asInteger;
    var density = msg[2].asFloat;
    {
        if (lane.inclusivelyBetween(0, 5)) {
            ~ikedaRegenLane.(lane, density.clip(0.0, 1.0));
        };
    }.defer;
}, '/matoma/ikeda/density', nil, 57200);

// ── /matoma/ikeda/layer [n] [val] ────────────────────────────────
// n: 0-5, val: 0=OFF, 1=ON
OSCdef(\matoma_ikeda_layer, { |msg|
    var lane = msg[1].asInteger;
    var val  = msg[2].asInteger;
    {
        if (lane.inclusivelyBetween(0, 5)) {
            ~ikedaLayers[lane] = (val == 1);
            "ikeda/layer: lane=% %".format(
                lane, if (val == 1) {"ON"} {"OFF"}).postln;
        };
    }.defer;
}, '/matoma/ikeda/layer', nil, 57200);

// ── /matoma/ikeda/amp [val] ──────────────────────────────────────
OSCdef(\matoma_ikeda_amp, { |msg|
    var val = msg[1].asFloat;
    {
        ~ikedaAmp = val.clip(0, 1);
        "ikeda/amp: %".format(~ikedaAmp.round(0.01)).postln;
    }.defer;
}, '/matoma/ikeda/amp', nil, 57200);

"IKEDA ENGINE OSCdef 登録完了".postln;
"  /matoma/ikeda/start|stop|bpm|mutate|density|layer|amp".postln;


// ══════════════════════════════════════════════════════════════════
// ▌ 動作確認用コマンド（コメントアウト済み）
// ══════════════════════════════════════════════════════════════════

/*
// 1. エンジン起動（デフォルトBPM=120、全レーンON）
~startIkedaEngine.();

// 2. BPM変更
~ikedaBpm = 140;
NetAddr("127.0.0.1", 57200).sendMsg('/matoma/ikeda/bpm', 140);

// 3. mutate速度を上げる（より速く変化）
~ikedaMutate = 3;
NetAddr("127.0.0.1", 57200).sendMsg('/matoma/ikeda/mutate', 3);

// 4. レーンのON/OFF（例: poly5をOFF）
NetAddr("127.0.0.1", 57200).sendMsg('/matoma/ikeda/layer', 4, 0);

// 5. ビット列密度を変える（例: clickレーンを疎に）
NetAddr("127.0.0.1", 57200).sendMsg('/matoma/ikeda/density', 1, 0.25);

// 6. 全体音量を下げる
NetAddr("127.0.0.1", 57200).sendMsg('/matoma/ikeda/amp', 0.5);

// 7. エンジン停止
~stopIkedaEngine.();

// 8. ビット列の現在状態を確認
~ikedaBits.do { |arr, i|
    ["sub","click","sine","noise","poly5","poly7"][i].post;
    " → ".post;
    arr.postln;
};
*/
