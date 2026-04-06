// ══════════════════════════════════════════════════════════════════
//  MaToMa percussion.scd  — CHAOS ENGINE 専用 パーカッション音源
//
//  【設計コンセプト】
//    池田亮司的「デジタル・アルファベット（サイン波/クリック/ノイズ）」を
//    基本音素材とした電子パーカッション音源群。
//    ステップシーケンサーを廃止し、CHAOS ENGINE（ポアソン過程）のみで駆動。
//    不規則なタイミング × 帯域分担 × ビットクラッシュ = 池田亮司的なリズム感。
//
//  【4つの音源 — 帯域で役割分担】
//    0. matoma_perc_kick   — 「ブンブン」LPFノイズ×Impulseゲート刻み（低域）
//    1. matoma_perc_snare  — 「ピピピ」Impulse click train（60-150Hzバースト）
//    2. matoma_perc_hihat  — 「ギギギ」ビットクラッシュノイズ（round量子化）
//    3. matoma_perc_clap   — 純粋サイン波バースト（倍音列からランダム選択）
//
//  【CHAOS ENGINE（唯一のドライバ）】
//    ポアソン過程（指数分布の待機時間）で不規則なタイミングを生成。
//    density, amp, weights で密度・音量・帯域バランスを調整。
//
//  【OSC受信ポート】
//    57200（run_headless.scd と同一ポート）
//
//  【OSCアドレス一覧】
//    /matoma/perc/amp [val]              — 全体音量(0-1)更新
//    /matoma/perc/chaos/start            — CHAOS ENGINE 開始
//    /matoma/perc/chaos/stop             — CHAOS ENGINE 停止
//    /matoma/perc/chaos/density [val]    — 平均イベント数/秒（0.5〜20）
//    /matoma/perc/chaos/amp [val]        — 発音確率の強さ（0.0-1.0）
//    /matoma/perc/chaos/filter [val]     — カオスエンジン用カットオフHz（未使用だが互換維持）
//    /matoma/perc/chaos/weights [k][s][h][c] — kick/snare/hihat/clap の選択重み
//
//  【参照ナレッジ】
//    artist_ikeda_aesthetics.md    → サブバス/超高域/ビットクラッシュ/純音設計
//    design_probability_control.md → ポアソン過程・CHAOS ENGINE 設計
// ══════════════════════════════════════════════════════════════════

// ══════════════════════════════════════════════════════════════════
// ■ グローバル変数
// ══════════════════════════════════════════════════════════════════

// CHAOS ENGINE 用グローバル変数
~percAmp   = 0.7;   // 全体音量（0〜1）— CHAOS ENGINE の発音振幅基準
~percGroup = nil;   // パーカッション専用 ParGroup

// CHAOS ENGINE 状態
~percChaosRoutine = nil;
~percChaosDensity = 4.0;   // 平均イベント数/秒（0.5〜20）
~percChaosAmp     = 0.6;   // 発音確率の強さ（0.0-1.0）
~percChaosCutoff  = 4000.0;
~percChaosWeights = [0.4, 0.3, 0.2, 0.1];  // kick/snare/hihat/clap の選択重み

// ブラウザへの通知用NetAddr
~percNetAddr = NetAddr("127.0.0.1", 9000);

// ══════════════════════════════════════════════════════════════════
// ■ STEP 1: ParGroup 確保
//
//   全パーカッションシンセをこのグループに入れる。
//   doneAction:2 で発音後は自動解放される。
// ══════════════════════════════════════════════════════════════════
~percGroup = ParGroup.new;
"パーカッション ParGroup 確保完了".postln;

// ══════════════════════════════════════════════════════════════════
// ■ STEP 2: SynthDef 定義
//
//   synthesis_percussion.md のコード例を直接ベースに実装。
//   全SynthDefに共通パラメーター: cutoff, res, amp, pan, reverse, out, doneAction:2
//
//   reverse=0（通常）: 短いアタック → 長いディケイ
//   reverse=1（逆再生）: 長いフェードイン → 短いカット（リバースヒットの質感）
//   SelectX でエンベロープをモーフィングする。
// ══════════════════════════════════════════════════════════════════

// ──────────────────────────────────────────────────────────────────
// 0. matoma_perc_kick — 「ブンブン」低域ノイズ×Impulseゲート刻み
//
//    池田亮司的「低域のデータ処理感」。
//    BrownNoise → LPF（カットオフが LFNoise1 で動的に揺れる）で低域のみ抽出。
//    さらに Impulse.ar(10-50Hz) でゲーティング → 「ぶつ切りの低音塊」が規則的に出る。
//    これが「ブンブン」の正体: 単なる低音ではなく、低音が高速に刻まれた感触。
// ──────────────────────────────────────────────────────────────────
SynthDef(\matoma_perc_kick, {
    arg freq      = 40,
        decay     = 0.08,
        pitch_env = 0.04,   // 後方互換（未使用）
        cutoff    = 4000,   // 後方互換（未使用）
        res       = 0.3,    // 後方互換（未使用）
        amp       = 0.85,
        pan       = 0,
        reverse   = 0,
        out       = 0;

    var gateFreq, cutoffHz, noise, gate, gateEnv, sig, actualDur, env_fwd, env_rev, env;

    // ゲート周波数（10-50Hz = 1秒10-50回の刻み）
    gateFreq = ExpRand(10, 50);

    // LPFカットオフが揺れる（40-200Hz でランダム動作）→ 低域の「ぼこぼこ」感
    cutoffHz = LFNoise1.kr(ExpRand(2, 8)).exprange(40, 200);
    noise    = LPF.ar(BrownNoise.ar, cutoffHz);

    // Impulseゲートで刻む（超短エンベロープ: 1-30ms）
    gate    = Impulse.ar(gateFreq);
    gateEnv = EnvGen.ar(Env.perc(0.001, ExpRand(0.001, 0.03)), gate);

    sig = noise * gateEnv;

    // 全体の発音時間（50-200ms）
    actualDur = decay * ExpRand(0.6, 2.5);
    env_fwd   = EnvGen.ar(Env.perc(0.001, actualDur), doneAction: 2);
    env_rev   = EnvGen.ar(Env([0, 1, 0], [actualDur * 0.8, actualDur * 0.15]), doneAction: 2);
    env       = SelectX.ar(reverse.clip(0, 1), [env_fwd, env_rev]);

    sig = sig * env * amp;
    Out.ar(out, Limiter.ar(Pan2.ar(sig, pan), 0.9));
}).add;

// ──────────────────────────────────────────────────────────────────
// 1. matoma_perc_snare — 「ピピピ」Impulse click train
//
//    池田亮司「テストパターン」の高音ピピピの正体。
//    Impulse.ar(60-150Hz) = 1秒60-150発のクリック列を短時間バーストさせる。
//    LFNoise1 で周波数を ±5Hz 揺らす → 「ギリギリ整然としながら揺れる」感。
//    全体エンベロープ（30-200ms）で切り取るので、N個のクリックの塊が1発になる。
//    例: 100Hz × 0.08秒 = 約8クリックのバースト → これが1ステップの音。
// ──────────────────────────────────────────────────────────────────
SynthDef(\matoma_perc_snare, {
    arg tone    = 100,    // 後方互換: click train 周波数の参考値（実際は ExpRand）
        decay   = 0.08,
        snap    = 0.5,    // 後方互換（未使用）
        cutoff  = 5000,   // 後方互換（未使用）
        res     = 0.3,    // 後方互換（未使用）
        amp     = 0.35,
        pan     = 0,
        reverse = 0,
        out     = 0;

    var clickFreq, clickMod, pulse, actualDur, env_fwd, env_rev, env, sig;

    // クリック周波数（60-150Hz = 1秒60-150クリック）
    clickFreq = ExpRand(60, 150);
    // LFNoise1 で ±5Hz 揺らす → 「ギリギリ整然」感
    clickMod  = clickFreq + LFNoise1.kr(10).range(-5, 5);

    // click train: Impulse列（1サンプルのインパルスが高速連続）
    pulse = Impulse.ar(clickMod);

    // 全体の持続時間（30-200ms）→ その間に N 個のクリックバースト
    actualDur = decay * ExpRand(0.4, 2.5);
    env_fwd   = EnvGen.ar(Env.perc(0.001, actualDur), doneAction: 2);
    env_rev   = EnvGen.ar(Env([0, 1, 0], [actualDur * 0.8, actualDur * 0.15]), doneAction: 2);
    env       = SelectX.ar(reverse.clip(0, 1), [env_fwd, env_rev]);

    sig = pulse * env * amp;
    Out.ar(out, Limiter.ar(Pan2.ar(sig, pan), 0.9));
}).add;

// ──────────────────────────────────────────────────────────────────
// 2. matoma_perc_hihat — 「ギギギ」ビットクラッシュノイズ
//
//    池田亮司「0と1」感。WhiteNoise を round(2^-bits) で量子化（ビット削減）。
//    bits = IRand(2, 5) → 4〜32段階に音を量子化 → デジタルエラー音。
//    HPFで高域成分のみ残す → 高音域のギザギザしたデジタルノイズ。
//    これが「ギギギ」「ジジジ」的な、「データが壊れた」感触の源。
// ──────────────────────────────────────────────────────────────────
SynthDef(\matoma_perc_hihat, {
    arg decay   = 0.025,
        cutoff  = 6000,   // 後方互換（未使用）
        res     = 0.3,    // 後方互換（未使用）
        amp     = 0.32,
        pan     = 0,
        reverse = 0,
        out     = 0;

    var bits, step, noise, crushed, filtered, actualDur, env_fwd, env_rev, env, sig;

    // ビット削減（IRand(2,5) → 2-5ビット相当 = 4〜32段階に量子化）
    bits     = IRand(2, 5);
    step     = 2 ** bits.neg;           // 量子化ステップ幅（小さいほど粗い）
    noise    = WhiteNoise.ar;
    crushed  = noise.round(step);       // 量子化 = ビットクラッシュ

    // HPF で高域絞り（2kHz-8kHz でランダム）
    filtered = HPF.ar(crushed, ExpRand(2000, 8000));

    // 超短バースト（10-60ms）
    actualDur = decay * ExpRand(0.4, 2.5);
    env_fwd   = EnvGen.ar(Env.perc(0.001, actualDur), doneAction: 2);
    env_rev   = EnvGen.ar(Env([0, 1, 0], [actualDur * 0.7, actualDur * 0.25]), doneAction: 2);
    env       = SelectX.ar(reverse.clip(0, 1), [env_fwd, env_rev]);

    sig = filtered * env * amp;
    Out.ar(out, Limiter.ar(Pan2.ar(sig, pan), 0.9));
}).add;

// ──────────────────────────────────────────────────────────────────
// 3. matoma_perc_clap — Klank非整数倍音クラップ（Alva Noto × 池田亮治）
//
//    美学参照: artist_alvanoto_aesthetics.md / artist_ikeda_aesthetics.md
//    → Klank（非整数倍音比 1.0/1.73/2.93/4.17/6.31）+ Impulse励振
//    → freqscale: ExpRand(500, 2500) で発音ごとに基音がランダム変化
//    → 非整数倍音 = 整数倍音（倍音列）を外れた「金属的・電子的共鳴感」
//    → クリックが共鳴構造に当たって短く消える = "digital materiality"
//    サンプルから変えた点: sa_clap（WhiteNoiseバースト式）→ Klank非整数倍音＋Impulse励振
// ──────────────────────────────────────────────────────────────────
SynthDef(\matoma_perc_clap, {
    arg cutoff  = 4000,   // 後方互換（未使用）
        res     = 0.3,    // 後方互換（未使用）
        amp     = 0.45,
        pan     = 0,
        reverse = 0,
        out     = 0;

    var exciter, sig, actualDur, env_fwd, env_rev, env;

    // Impulse励振 → Klank非整数倍音共鳴（発音ごとに基音が変化）
    exciter = Impulse.ar(0);
    sig = Klank.ar(
        `[[1.0, 1.73, 2.93, 4.17, 6.31],     // 非整数倍音比（金属的・電子的共鳴）
          [1.0,  0.8,  0.6,  0.4,  0.25],    // 各倍音の振幅
          [0.08, 0.05, 0.03, 0.02, 0.01]],   // 各倍音の減衰時間（秒）
        exciter,
        freqscale: ExpRand(500, 2500)         // 発音ごとにランダムな基音
    );

    // 持続時間（30-100ms でランダム）
    actualDur = ExpRand(0.03, 0.10);

    env_fwd = EnvGen.ar(Env([1, 0.0001], [actualDur], \exp), doneAction: 2);
    env_rev = EnvGen.ar(Env([0.0001, 1, 0.0001], [actualDur * 0.8, 0.001], [\lin, \exp]), doneAction: 2);
    env     = SelectX.ar(reverse.clip(0, 1), [env_fwd, env_rev]);

    sig = sig * env * amp;
    Out.ar(out, Limiter.ar(Pan2.ar(sig, pan), 0.9));
}).add;

s.sync;
"SynthDef定義完了 (Klank共鳴・FM合成・マイクロサウンド): \\matoma_perc_kick, \\matoma_perc_snare, \\matoma_perc_hihat, \\matoma_perc_clap".postln;

// ══════════════════════════════════════════════════════════════════
// ■ STEP 3: 各トラックの対応SynthDef名
// ══════════════════════════════════════════════════════════════════

// トラック0=kick, 1=snare, 2=hihat, 3=clap
~percSynths = [
    \matoma_perc_kick,
    \matoma_perc_snare,
    \matoma_perc_hihat,
    \matoma_perc_clap
];

// ══════════════════════════════════════════════════════════════════
// ■ STEP 4: CHAOS ENGINE 起動関数
//
//   ステップシーケンサーとは完全に独立した自律生成エンジン。
//   ポアソン過程（指数分布の待機時間）で不規則なタイミングを生成。
//   exprand(min, max) でポアソン過程の待機時間を生成。
// ══════════════════════════════════════════════════════════════════
~startChaosEngine = {
    // var はfunction先頭に（SCルール）
    var waitTime, track, weights;

    if (~percChaosRoutine.notNil) { ~percChaosRoutine.stop; ~percChaosRoutine = nil; };
    ~percGroup = ParGroup.new;

    ~percChaosRoutine = Routine({
        loop {
            // ポアソン過程: 指数分布で待機時間を決定
            // density/s から平均間隔を計算（densityが高いほど短い間隔）
            waitTime = exprand(0.02, 2.0 / ~percChaosDensity.max(0.1));

            // 発音確率チェック（ampが高いほど鳴りやすい）
            if (1.0.rand < ~percChaosAmp) {
                // 重み付きランダムで楽器選択（wchooseを使う）
                weights = ~percChaosWeights.normalizeSum;
                track = [0, 1, 2, 3].wchoose(weights);

                // パラメーターをランダムに変化させながら発音
                Synth(~percSynths[track], [
                    \cutoff,  (~percChaosCutoff * rrand(0.5, 2.0)).clip(200, 8000),
                    \res,     rrand(0.1, 0.7),
                    \amp,     rrand(0.3, 1.0) * ~percAmp,
                    \pan,     rrand(-0.8, 0.8),
                    \reverse, [0, 0, 0, 1].wchoose([0.7, 0.1, 0.1, 0.1]),
                    \out,     0
                ]);
            };

            waitTime.wait;
        }
    }).play(TempoClock.default);

    "CHAOS ENGINE 開始 (density: %/s, amp: %)".format(
        ~percChaosDensity.round(0.1), ~percChaosAmp.round(0.01)).postln;
};

// ══════════════════════════════════════════════════════════════════
// ■ STEP 5: CHAOS ENGINE OSCdef 登録
// ══════════════════════════════════════════════════════════════════

// ── /matoma/perc/amp [val] — 全体音量 ───────────────────────────────
OSCdef(\matoma_perc_amp, { |msg|
    var val = msg[1].asFloat;
    {
        ~percAmp = val.clip(0, 1);
        "perc/amp: %".format(~percAmp.round(0.01)).postln;
    }.defer;
}, '/matoma/perc/amp', nil, 57200);

// ── /matoma/perc/chaos/start — CHAOS ENGINE 開始 ──────────────────
OSCdef(\matoma_perc_chaos_start, { |msg|
    { ~startChaosEngine.(); }.defer;
}, '/matoma/perc/chaos/start', nil, 57200);

// ── /matoma/perc/chaos/stop — CHAOS ENGINE 停止 ───────────────────
OSCdef(\matoma_perc_chaos_stop, { |msg|
    {
        if (~percChaosRoutine.notNil) {
            ~percChaosRoutine.stop;
            ~percChaosRoutine = nil;
            "CHAOS ENGINE 停止".postln;
        };
    }.defer;
}, '/matoma/perc/chaos/stop', nil, 57200);

// ── /matoma/perc/chaos/density [val] — 平均イベント数/秒 ───────────
// val: 0.5〜20（値が大きいほど密な発音）
OSCdef(\matoma_perc_chaos_density, { |msg|
    ~percChaosDensity = msg[1].asFloat.clip(0.5, 20.0);
    "perc/chaos/density: %/s".format(~percChaosDensity.round(0.1)).postln;
}, '/matoma/perc/chaos/density', nil, 57200);

// ── /matoma/perc/chaos/amp [val] — 発音確率の強さ ──────────────────
// val: 0.0〜1.0（1.0=常に鳴る、0.0=絶対鳴らない）
OSCdef(\matoma_perc_chaos_amp, { |msg|
    ~percChaosAmp = msg[1].asFloat.clip(0.0, 1.0);
    "perc/chaos/amp: %".format(~percChaosAmp.round(0.01)).postln;
}, '/matoma/perc/chaos/amp', nil, 57200);

// ── /matoma/perc/chaos/filter [val] — カオスエンジン用カットオフ ────
// val: 200〜8000 Hz
OSCdef(\matoma_perc_chaos_filter, { |msg|
    ~percChaosCutoff = msg[1].asFloat.clip(200, 8000);
    "perc/chaos/filter: % Hz".format(~percChaosCutoff.round(1)).postln;
}, '/matoma/perc/chaos/filter', nil, 57200);

// ── /matoma/perc/chaos/weights [k] [s] [h] [c] — 楽器選択重み ─────
// k=kick, s=snare, h=hihat, c=clap (0〜1 の非負値、normalizeSum で正規化)
OSCdef(\matoma_perc_chaos_weights, { |msg|
    ~percChaosWeights = [
        msg[1].asFloat.clip(0, 1),
        msg[2].asFloat.clip(0, 1),
        msg[3].asFloat.clip(0, 1),
        msg[4].asFloat.clip(0, 1)
    ];
    "perc/chaos/weights: kick=% snare=% hihat=% clap=%".format(
        ~percChaosWeights[0].round(0.01),
        ~percChaosWeights[1].round(0.01),
        ~percChaosWeights[2].round(0.01),
        ~percChaosWeights[3].round(0.01)
    ).postln;
}, '/matoma/perc/chaos/weights', nil, 57200);

"パーカッションシーケンサー OSCdef 登録完了".postln;
"  既存: /matoma/perc/start|stop|step|bpm|filter|amp|clear".postln;
"  既存: /matoma/perc/prob|reverse|euclid|randomize|scatter".postln;
"  新規: /matoma/perc/track/reverse".postln;
"  新規: /matoma/perc/chaos/start|stop|density|amp|filter|weights".postln;

// ══════════════════════════════════════════════════════════════════
// ■ 動作確認用コマンド（コメントアウト済み、テスト時に使用）
// ══════════════════════════════════════════════════════════════════

/*
// 1. 単音テスト（各音源が鳴るか確認）
Synth(\matoma_perc_kick,  [\amp, 0.85, \reverse, 0]);  // 「ブンブン」低域ノイズ刻み
Synth(\matoma_perc_snare, [\amp, 0.35, \reverse, 0]);  // 「ピピピ」click train
Synth(\matoma_perc_hihat, [\amp, 0.32, \reverse, 0]);  // 「ギギギ」ビットクラッシュ
Synth(\matoma_perc_clap,  [\amp, 0.45, \reverse, 0]);  // Klank電子共鳴

// 1b. リバーステスト（エンベロープ方向反転）
Synth(\matoma_perc_kick,  [\amp, 0.85, \reverse, 1]);
Synth(\matoma_perc_snare, [\amp, 0.35, \reverse, 1]);
Synth(\matoma_perc_hihat, [\amp, 0.32, \reverse, 1]);
Synth(\matoma_perc_clap,  [\amp, 0.45, \reverse, 1]);

// 2. ステップパターンを設定してシーケンサーを動かす
~percSteps[0] = [1,0,0,0, 1,0,0,0, 1,0,0,0, 1,0,0,0];
~percSteps[1] = [0,0,0,0, 1,0,0,0, 0,0,0,0, 1,0,0,0];
~percSteps[2] = [1,0,1,0, 1,0,1,0, 1,0,1,0, 1,0,1,1];
~percSteps[3] = [0,0,0,0, 0,0,0,1, 0,0,0,0, 0,0,1,0];

// 3. トラック別逆再生（kick=reverse, snare=forward）
~percTrackReverse[0] = true;
~percTrackReverse[1] = false;

// 4. ユークリッドリズムのテスト（kick に3/16 を設定）
~percSteps[0] = ~generateEuclid.(3, 16);

// 5. シーケンサー開始
~startPercRoutine.();

// 6. CHAOS ENGINE 開始
~startChaosEngine.();

// 7. 停止
~percRoutine.stop; ~percStep = 0;
if (~percChaosRoutine.notNil) { ~percChaosRoutine.stop; ~percChaosRoutine = nil; };

// 8. OSC経由でのテスト（Python側と同じ操作）
NetAddr("127.0.0.1", 57200).sendMsg('/matoma/perc/bpm', 140);
NetAddr("127.0.0.1", 57200).sendMsg('/matoma/perc/step', 0, 0, 1);
NetAddr("127.0.0.1", 57200).sendMsg('/matoma/perc/euclid', 0, 5);
NetAddr("127.0.0.1", 57200).sendMsg('/matoma/perc/randomize', 2, 0.5);
NetAddr("127.0.0.1", 57200).sendMsg('/matoma/perc/scatter', -1);
// トラック0をリバースに
NetAddr("127.0.0.1", 57200).sendMsg('/matoma/perc/track/reverse', 0, 1);
// 後方互換: 全トラック一括リバース
NetAddr("127.0.0.1", 57200).sendMsg('/matoma/perc/reverse', 1);
NetAddr("127.0.0.1", 57200).sendMsg('/matoma/perc/start');
NetAddr("127.0.0.1", 57200).sendMsg('/matoma/perc/stop');
// CHAOS ENGINE 操作
NetAddr("127.0.0.1", 57200).sendMsg('/matoma/perc/chaos/start');
NetAddr("127.0.0.1", 57200).sendMsg('/matoma/perc/chaos/density', 8.0);
NetAddr("127.0.0.1", 57200).sendMsg('/matoma/perc/chaos/amp', 0.8);
NetAddr("127.0.0.1", 57200).sendMsg('/matoma/perc/chaos/filter', 3000);
NetAddr("127.0.0.1", 57200).sendMsg('/matoma/perc/chaos/weights', 0.5, 0.2, 0.2, 0.1);
NetAddr("127.0.0.1", 57200).sendMsg('/matoma/perc/chaos/stop');
*/
