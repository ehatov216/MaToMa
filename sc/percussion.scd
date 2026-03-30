// ══════════════════════════════════════════════════════════════════
//  MaToMa percussion.scd  — 16ステップパーカッションシーケンサー
//
//  【設計コンセプト】
//    Alva Noto / 池田亮司スタイルの「電子音・合成音・マイクロサウンド」を
//    基本音源とした電子パーカッションシーケンサー。
//    「叩く」のではなく「パルス・クリック・瞬間的な波形」を鳴らす哲学。
//    「制御されたカオス」を実現するために、ステップごとの発火確率と
//    ユークリッドリズム生成を組み合わせる。
//
//  【4つの音源 — 池田亮司のデジタル・アルファベット（pulse/noise/silence）】
//    0. matoma_perc_kick   — 「ブンブン」LPFノイズ×Impulseゲート刻み（低域データ感）
//    1. matoma_perc_snare  — 「ピピピ」Impulse click train（60-150Hzバースト）
//    2. matoma_perc_hihat  — 「ギギギ」ビットクラッシュノイズ（round量子化）
//    3. matoma_perc_clap   — Klank電子共鳴（黄金比倍音、発音ごと基音変化）※良
//
//  【シーケンサー構成】
//    4トラック × 16ステップ
//    ステップごとに発火確率（0-100）を持つ
//    トラック別逆再生フラグで各音源のエンベロープ方向を切り替え可能
//    ParGroup に全シンセを収容（doneAction:2 で自動解放）
//
//  【CHAOS ENGINE】
//    ステップシーケンサーとは完全に独立した自律生成エンジン。
//    ポアソン過程（指数分布の待機時間）で不規則なタイミングを生成。
//
//  【OSC受信ポート】
//    57200（run_headless.scd と同一ポート）
//
//  【OSCアドレス一覧】
//    /matoma/perc/start                  — シーケンサー開始
//    /matoma/perc/stop                   — シーケンサー停止・ステップリセット
//    /matoma/perc/step [t][s][v]         — ステップ値設定（0|1）
//    /matoma/perc/bpm [val]              — BPM変更（30〜240）
//    /matoma/perc/filter [c][r]          — カットオフHz・レゾナンス(0-1)更新
//    /matoma/perc/amp [val]              — 全体音量(0-1)更新
//    /matoma/perc/clear [track]          — 指定トラックを全オフ
//    /matoma/perc/prob [t][s][prob]      — ステップごとの発火確率設定（0-100）
//    /matoma/perc/reverse [val]          — 後方互換: 全トラック逆再生トグル（0=forward, 1=reverse）
//    /matoma/perc/track/reverse [t][v]   — トラック別逆再生トグル（0=forward, 1=reverse）
//    /matoma/perc/euclid [t][hits]       — ユークリッドリズム生成
//    /matoma/perc/randomize [t][d]       — ランダムパターン生成（density 0.0-1.0）
//    /matoma/perc/scatter [track]        — 全ステップの確率をランダム設定（-1=全トラック）
//    /matoma/perc/chaos/start            — CHAOS ENGINE 開始
//    /matoma/perc/chaos/stop             — CHAOS ENGINE 停止
//    /matoma/perc/chaos/density [val]    — 平均イベント数/秒（0.5〜20）
//    /matoma/perc/chaos/amp [val]        — 発音確率の強さ（0.0-1.0）
//    /matoma/perc/chaos/filter [val]     — カオスエンジン用カットオフHz
//    /matoma/perc/chaos/weights [k][s][h][c] — kick/snare/hihat/clap の選択重み
//
//  【ブラウザ → tick通知】
//    SC → Python(9000): /matoma/perc/tick [step]  （現在ステップ位置）
//    SC → Python(9000): /matoma/perc/pattern [track] [s0..s15]  （パターン変更通知）
//
//  【参照ナレッジ】
//    artist_ikeda_aesthetics.md    → サブバス・超高域・周波数掃引・完全ドライ設計
//    artist_alvanoto_aesthetics.md → Klank非整数倍音（CLAP）・建築的倍音構造
//    design_probability_control.md → 確率トリガーパターン、Routineシーケンサー構成
// ══════════════════════════════════════════════════════════════════

// ══════════════════════════════════════════════════════════════════
// ■ グローバル変数
// ══════════════════════════════════════════════════════════════════

// 4トラック × 16ステップ（0=off, 1=on）
~percSteps   = Array.fill(4, { Array.fill(16, { 0 }) });

// 4トラック × 16ステップの発火確率（0-100）
// 100=必ず鳴る、50=半分の確率、0=絶対鳴らない
~percProbs   = Array.fill(4, { Array.fill(16, { 100 }) });

// トラック別逆再生フラグ（各トラックのエンベロープ方向を個別制御）
// true=リバースヒット（フェードイン→短カット）、false=通常（アタック→ディケイ）
~percTrackReverse = Array.fill(4, { false });

// シーケンサー状態
~percBpm     = 120.0;   // BPM（30〜240の範囲を想定）
~percCutoff  = 4000.0;  // フィルターカットオフHz
~percRes     = 0.3;     // レゾナンス（0〜1）
~percAmp     = 0.7;     // 全体音量（0〜1）
~percStep    = 0;       // 現在のステップ位置（0〜15）
~percRoutine = nil;     // 動作中のRoutine
~percGroup   = nil;     // パーカッション専用 ParGroup

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
// 3. matoma_perc_clap — Klank電子共鳴パルス（Alva Noto的建築的倍音）
//
//    美学参照: artist_alvanoto_aesthetics.md → 建築的・幾何学的構造
//    Impulse励振 + Klank（黄金比に近い非整数倍音比）。
//    freqscale = ExpRand(500, 2500) → 発音ごとに基音が変化。
//    → コンピューターのビープ音の上位版: 電子的なベル・シンバル余韻。
// ──────────────────────────────────────────────────────────────────
SynthDef(\matoma_perc_clap, {
    arg cutoff  = 4000,
        res     = 0.3,
        amp     = 0.45,
        pan     = 0,
        reverse = 0,
        out     = 0;

    var exc, sig, env_fwd, env_rev, env, filtered;

    exc = Impulse.ar(0);

    // 非整数倍音（黄金比的な周波数比 → 数学的・建築的）
    // freqscale: ExpRand で発音ごとに基音が 500-2500Hz で変化
    sig = Klank.ar(`[
        [1.0, 1.73, 2.93, 4.17, 6.31],
        [1.0, 0.7,  0.5,  0.3,  0.15],
        [0.08, 0.06, 0.04, 0.03, 0.02]
    ], exc,
        freqscale: ExpRand(500, 2500));

    env_fwd = EnvGen.ar(Env.perc(0.001, 0.12), doneAction: 2);
    env_rev = EnvGen.ar(Env([0, 0.4, 1, 0], [0.09, 0.025, 0.001]), doneAction: 2);
    env     = SelectX.ar(reverse.clip(0, 1), [env_fwd, env_rev]);

    sig      = sig * env * amp;
    filtered = RLPF.ar(sig, cutoff.clip(80, 18000), res.linlin(0, 1, 0.05, 1.0));

    Out.ar(out, Limiter.ar(Pan2.ar(filtered, pan), 0.9));
}).add;

s.sync;
"SynthDef定義完了 (Klank共鳴・FM合成・マイクロサウンド): \\matoma_perc_kick, \\matoma_perc_snare, \\matoma_perc_hihat, \\matoma_perc_clap".postln;

// ══════════════════════════════════════════════════════════════════
// ■ STEP 3: ユークリッドリズム生成関数
//
//   k個のヒットをn=16ステップに均等配置（Bresenhamライン法）。
//   Arca / Autechre 的な非グリッドリズムを生成するのに使う。
// ══════════════════════════════════════════════════════════════════
~generateEuclid = { |hits, steps=16|
    // var 宣言はすべて関数先頭にまとめる
    var pattern, bucket;

    pattern = Array.fill(steps, { 0 });
    bucket  = 0.0;

    // hits 個のヒットを等間隔で配置（Bresenham的なバケツアルゴリズム）
    hits.do {
        pattern[bucket.asInteger] = 1;
        bucket = bucket + (steps / hits.max(1));
    };

    pattern
};

"ユークリッドリズム生成関数 ~generateEuclid 登録完了".postln;

// ══════════════════════════════════════════════════════════════════
// ■ STEP 4: 各トラックの対応SynthDef名
// ══════════════════════════════════════════════════════════════════

// トラック0=kick, 1=snare, 2=hihat, 3=clap
~percSynths = [
    \matoma_perc_kick,
    \matoma_perc_snare,
    \matoma_perc_hihat,
    \matoma_perc_clap
];

// ══════════════════════════════════════════════════════════════════
// ■ STEP 5: シーケンサーRoutine起動関数
//
//   design_probability_control.md の確率トリガーパターンを参照。
//   CoinGate の代わりにRoutine内で確率チェックを行う（OSC制御との相性のため）。
//   ~percTrackReverse[track] でトラック別リバースエンベロープを制御。
// ══════════════════════════════════════════════════════════════════
~startPercRoutine = {
    // var 宣言はすべて関数先頭にまとめる
    var stepDur, playStep;

    // 既存Routineを停止してから再起動
    if (~percRoutine.notNil) { ~percRoutine.stop; ~percRoutine = nil; };

    // ParGroupを毎回再作成（s.freeAll後も確実に有効な状態にする）
    ~percGroup = ParGroup.new;

    ~percRoutine = Routine({
        loop {
            // 16分音符の長さを毎ループ参照（BPM変更をリアルタイムに反映）
            stepDur = 60.0 / ~percBpm / 4;

            // ステップ位置はシーケンス方向（全体）は常に前進
            playStep = ~percStep;

            // 4トラックをスキャン
            4.do { |track|
                if (
                    (~percSteps[track][playStep] == 1) &&
                    (1.0.rand * 100 < ~percProbs[track][playStep])
                ) {
                    // targetを指定せずデフォルトグループに追加（グループ無効化を回避）
                    Synth(~percSynths[track], [
                        \cutoff,  ~percCutoff,
                        \res,     ~percRes,
                        \amp,     ~percAmp * rrand(0.88, 1.0),
                        \pan,     rrand(-0.25, 0.25),
                        \reverse, if (~percTrackReverse[track]) { 1 } { 0 },
                        \out,     0
                    ]);
                };
            };

            // ブラウザに現在ステップを通知
            ~percNetAddr.sendMsg('/matoma/perc/tick', ~percStep);

            // ステップを進める
            ~percStep = (~percStep + 1) % 16;

            stepDur.wait;
        }
    }).play(TempoClock.default);  // クロックを明示

    "パーカッションシーケンサー開始 (BPM: %)".format(~percBpm.round(0.1)).postln;
};

// ══════════════════════════════════════════════════════════════════
// ■ STEP 6: CHAOS ENGINE 起動関数
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
// ■ STEP 7: OSCdef 登録
// ══════════════════════════════════════════════════════════════════

// ── /matoma/perc/start — シーケンサー開始 ──────────────────────────
OSCdef(\matoma_perc_start, { |msg|
    { ~startPercRoutine.(); }.defer;
}, '/matoma/perc/start', nil, 57200);

// ── /matoma/perc/stop — シーケンサー停止・ステップリセット ──────────
OSCdef(\matoma_perc_stop, { |msg|
    {
        if (~percRoutine.notNil) {
            ~percRoutine.stop;
            ~percRoutine = nil;
        };
        ~percStep = 0;
        "パーカッションシーケンサー停止".postln;
    }.defer;
}, '/matoma/perc/stop', nil, 57200);

// ── /matoma/perc/step [track] [step] [val] — ステップ値設定 ─────────
// track: 0〜3, step: 0〜15, val: 0（off）または 1（on）
OSCdef(\matoma_perc_step, { |msg|
    var track = msg[1].asInteger;
    var step  = msg[2].asInteger;
    var val   = msg[3].asInteger;
    {
        if (track.inclusivelyBetween(0, 3) and: { step.inclusivelyBetween(0, 15) }) {
            ~percSteps[track][step] = val.clip(0, 1);
            "perc/step: track=% step=% val=%".format(track, step, val).postln;
        };
    }.defer;
}, '/matoma/perc/step', nil, 57200);

// ── /matoma/perc/bpm [val] — BPM変更 ────────────────────────────────
// Routine内で毎ループ参照するのでリアルタイムに反映される
OSCdef(\matoma_perc_bpm, { |msg|
    var val = msg[1].asFloat;
    {
        ~percBpm = val.clip(30, 240);
        "perc/bpm: %".format(~percBpm.round(0.1)).postln;
    }.defer;
}, '/matoma/perc/bpm', nil, 57200);

// ── /matoma/perc/filter [cutoff] [res] — フィルター更新 ────────────
// 次の発音から反映（スポーン時に参照）
OSCdef(\matoma_perc_filter, { |msg|
    var cutoff = msg[1].asFloat;
    var res    = msg[2].asFloat;
    {
        ~percCutoff = cutoff.clip(80, 18000);
        ~percRes    = res.clip(0, 1);
        "perc/filter: cutoff=% res=%".format(
            ~percCutoff.round(1), ~percRes.round(0.01)).postln;
    }.defer;
}, '/matoma/perc/filter', nil, 57200);

// ── /matoma/perc/amp [val] — 全体音量 ───────────────────────────────
OSCdef(\matoma_perc_amp, { |msg|
    var val = msg[1].asFloat;
    {
        ~percAmp = val.clip(0, 1);
        "perc/amp: %".format(~percAmp.round(0.01)).postln;
    }.defer;
}, '/matoma/perc/amp', nil, 57200);

// ── /matoma/perc/clear [track] — 指定トラックをすべてオフ ──────────
OSCdef(\matoma_perc_clear, { |msg|
    var track = msg[1].asInteger;
    {
        if (track.inclusivelyBetween(0, 3)) {
            ~percSteps[track] = Array.fill(16, { 0 });
            "perc/clear: track=% 全ステップクリア".format(track).postln;
        };
    }.defer;
}, '/matoma/perc/clear', nil, 57200);

// ── /matoma/perc/prob [track] [step] [prob] — ステップごとの発火確率設定 ──
// track: 0〜3, step: 0〜15, prob: 0-100（100=必ず鳴る）
OSCdef(\matoma_perc_prob, { |msg|
    var track = msg[1].asInteger;
    var step  = msg[2].asInteger;
    var prob  = msg[3].asFloat;
    {
        if (track.inclusivelyBetween(0, 3) and: { step.inclusivelyBetween(0, 15) }) {
            ~percProbs[track][step] = prob.clip(0, 100);
            "perc/prob: track=% step=% prob=%".format(
                track, step, ~percProbs[track][step].round(1)).postln;
        };
    }.defer;
}, '/matoma/perc/prob', nil, 57200);

// ── /matoma/perc/reverse [val] — 後方互換: 全トラック逆再生トグル ───
// val: 0=forward, 1=reverse
// 後方互換のため残す。~percTrackReverse 全要素を一括更新する。
OSCdef(\matoma_perc_reverse, { |msg|
    var val = msg[1].asInteger;
    {
        4.do { |track|
            ~percTrackReverse[track] = (val == 1);
        };
        "perc/reverse: % (全トラック一括)".format(
            if (val == 1) {"reverse"} {"forward"}).postln;
    }.defer;
}, '/matoma/perc/reverse', nil, 57200);

// ── /matoma/perc/track/reverse [track] [val] — トラック別逆再生トグル ──
// track: 0〜3, val: 0=forward, 1=reverse
// 各トラックのエンベロープ方向を個別に制御する
OSCdef(\matoma_perc_track_reverse, { |msg|
    var track = msg[1].asInteger;
    var val   = msg[2].asInteger;  // 0=forward, 1=reverse
    {
        if (track.inclusivelyBetween(0, 3)) {
            ~percTrackReverse[track] = (val == 1);
            "perc/track/reverse: track=% %".format(
                track, if (val == 1) {"reverse"} {"forward"}).postln;
        };
    }.defer;
}, '/matoma/perc/track/reverse', nil, 57200);

// ── /matoma/perc/euclid [track] [hits] — ユークリッドリズム生成 ──────
// track: 0〜3, hits: 1-16
// 生成したパターンをブラウザに通知する
OSCdef(\matoma_perc_euclid, { |msg|
    var track = msg[1].asInteger;
    var hits  = msg[2].asInteger;
    {
        if (track.inclusivelyBetween(0, 3) and: { hits.inclusivelyBetween(1, 16) }) {
            ~percSteps[track] = ~generateEuclid.(hits, 16);
            // 生成したパターンをブラウザに通知（*展開で16個の値をフラット送信）
            ~percNetAddr.sendMsg('/matoma/perc/pattern', track, *~percSteps[track]);
            "perc/euclid: track=% hits=% pattern=%".format(
                track, hits, ~percSteps[track]).postln;
        };
    }.defer;
}, '/matoma/perc/euclid', nil, 57200);

// ── /matoma/perc/randomize [track] [density] — ランダムパターン生成 ──
// track: 0〜3, density: 0.0-1.0（1.0=全ステップon）
// density の確率で各ステップをon/offにする
OSCdef(\matoma_perc_randomize, { |msg|
    var track   = msg[1].asInteger;
    var density = msg[2].asFloat;
    {
        if (track.inclusivelyBetween(0, 3)) {
            ~percSteps[track] = Array.fill(16, {
                (1.0.rand < density.clip(0.0, 1.0)).asInteger
            });
            // 生成したパターンをブラウザに通知
            ~percNetAddr.sendMsg('/matoma/perc/pattern', track, *~percSteps[track]);
            "perc/randomize: track=% density=% pattern=%".format(
                track, density.round(0.01), ~percSteps[track]).postln;
        };
    }.defer;
}, '/matoma/perc/randomize', nil, 57200);

// ── /matoma/perc/scatter [track] — スキャッターモード ──────────────
// track: 0〜3 または -1（全トラック）
// 全ステップの確率をランダムに設定する（制御されたカオスの極端な適用）
OSCdef(\matoma_perc_scatter, { |msg|
    var track = msg[1].asInteger;
    {
        if (track == -1) {
            // 全トラックの全ステップ: 確率をランダム設定 + 確率>30なら自動ON
            4.do { |t|
                16.do { |s|
                    var prob = (1.0.rand * 100).round;
                    ~percProbs[t][s] = prob;
                    ~percSteps[t][s] = if (prob > 30) { 1 } { 0 };  // 30%超はON
                };
                // ブラウザにステップパターンを通知
                ~percNetAddr.sendMsg('/matoma/perc/pattern', t, *~percSteps[t]);
            };
            "perc/scatter: 全トラック確率＋ステップランダム設定".postln;
        } {
            if (track.inclusivelyBetween(0, 3)) {
                // 指定トラックのみ全ステップ確率をランダム設定
                16.do { |s|
                    var prob = (1.0.rand * 100).round;
                    ~percProbs[track][s] = prob;
                    ~percSteps[track][s] = if (prob > 30) { 1 } { 0 };
                };
                ~percNetAddr.sendMsg('/matoma/perc/pattern', track, *~percSteps[track]);
                "perc/scatter: track=% 確率＋ステップランダム設定".format(track).postln;
            };
        };
    }.defer;
}, '/matoma/perc/scatter', nil, 57200);

// ══════════════════════════════════════════════════════════════════
// ■ STEP 8: CHAOS ENGINE OSCdef 登録
// ══════════════════════════════════════════════════════════════════

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
