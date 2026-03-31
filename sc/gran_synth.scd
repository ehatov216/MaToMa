// ══════════════════════════════════════════════════════════════════
//  MaToMa gran_synth.scd  — グラニュラーシンセ（バッファ不要・独立型）v1
//
//  【設計思想】
//    Droneに依存しない、自己完結したグラニュラー持続音源。
//    GrainSin（バッファ不要）を高密度で発火させることで
//    「途切れない・太い・滑らかな」アンビエントテクスチャを生成する。
//
//    OPN Tranquilizer 的「粒子の雲」:
//      density=35、grainDur=0.18s → 同時に ~6粒が重なる → 途切れない
//      ピッチ散乱（spread）で広がりを出しながら調和を保つ
//      bright パラメーターでオクターブ上層を追加して明るさを制御
//
//  【シグナルチェーン】
//    GrainSin（基音層）
//    + GrainSin（オクターブ上層 × bright）
//      → FreeVerb2（空間化）
//      → Env.adsr（attack:2s / release:5s でゆっくり立ち上がり・消える）
//      → Limiter（安全制御）
//      → ~effectBus
//
//  【Layer A: 3階層有機モジュレーション（drone.scd と同設計）】
//    A1（呼吸, ~0.04 Hz）: density を chaos に応じて揺らす
//    A2（心拍, ~0.15 Hz）: ピッチを spread に応じて揺らす
//    A3（神経, ~3 Hz）  : pan をゆっくり動かす
//
//  【パラメーター】
//    freq      : 基音（Hz）。デフォルト 110（A2）
//    density   : 1秒あたりのグレイン数（5〜60）。大きいほど密で途切れない
//    grainDur  : グレインの長さ（秒）。大きいほど滑らか・アンビエント的
//    spread    : ピッチの散乱量（0.0=純粋、1.0=広い）
//    panSpread : ステレオの広がり（0.0=中央、1.0=最大）
//    bright    : オクターブ上層の量（0.0=暗い、1.0=明るい）
//    chaos     : 有機モジュレーションの深さ（0.0=安定、1.0=揺らぐ）
//    room      : リバーブ量（0.0〜1.0）
//    amp       : 音量（0.0〜1.0）
//    gate      : エンベロープゲート（1=持続、0=フェードアウト）
//
//  【OSCアドレス（port 57200）】
//    /matoma/gran_synth/start
//    /matoma/gran_synth/stop
//    /matoma/gran_synth/param [名前] [値]
//      例: density 40 / grainDur 0.25 / bright 0.7 / chaos 0.5
// ══════════════════════════════════════════════════════════════════

// ── SynthDef: バッファ不要グラニュラーシンセ ────────────────────────
// synthesis_granular.md § GrainSin / norns_sc_patterns.md を参照して実装
// OPN Tranquilizer 的「粒子の雲」設計（artist_opn_aesthetics.md 参照）
SynthDef(\matoma_gran_synth, {
    arg freq      = 110,   // 基音（Hz）: A2
        density   = 35,    // グレイン/秒: 35 × 0.18s ≈ 6粒同時 = 途切れない
        grainDur  = 0.18,  // グレインの長さ（秒）
        spread    = 0.2,   // ピッチ散乱（0=純粋、1=広い）
        panSpread = 0.7,   // ステレオ広がり
        bright    = 0.4,   // オクターブ上層の量（0=暗い、1=明るい）
        chaos     = 0.3,   // 有機モジュレーション深さ
        room      = 0.6,   // リバーブ量
        amp       = 0.4,   // 音量
        gate      = 1,     // エンベロープゲート
        outBus    = 0;     // 出力バス

    // SCルール: var宣言はすべて先頭にまとめる
    var trig_base, trig_upper;
    var sig_base, sig_upper, sig, wet, env;
    // Layer A: 3階層有機モジュレーション
    var a1_density_mod;   // A1: 呼吸（~0.04 Hz）— density
    var a2_pitch_mod;     // A2: 心拍（~0.15 Hz）— pitch
    var a3_pan;           // A3: 神経（~3 Hz）  — pan
    var density_live, freq_base, freq_upper, pan_base, pan_upper;

    // ── Layer A1: 呼吸（~0.04 Hz）— density を揺らす ─────────────────
    // chaos が深さを制御: chaos=0 → 変調なし、chaos=1 → ±30% 変動
    // drone.scd の a1 と同設計（呼吸するような密度感）
    a1_density_mod = LFNoise2.kr(0.04).range(
        1.0 - (0.3 * chaos),
        1.0 + (0.3 * chaos)
    );

    // ── Layer A2: 心拍（~0.15 Hz）— ピッチを揺らす ───────────────────
    // spread が散乱幅を制御。chaos が揺れをさらに深める。
    // デフォルト spread=0.2, chaos=0.3 → ±1.625% = ±28 cents（微妙な揺らぎ）
    a2_pitch_mod = LFNoise2.kr(0.15).range(
        1.0 - (spread * 0.025 * (1.0 + chaos)),
        1.0 + (spread * 0.025 * (1.0 + chaos))
    );

    // ── Layer A3: 神経（~3 Hz）— pan をゆっくり動かす ─────────────────
    // drone.scd の a3 と同設計（ステレオが「息をする」感覚）
    a3_pan = LFNoise1.kr(3.0).range(panSpread.neg, panSpread);

    // ── 有機値を計算 ──────────────────────────────────────────────────
    density_live = (density * a1_density_mod).clip(5, 80);
    freq_base    = freq * a2_pitch_mod;

    // ── トリガー: Impulse + 少量の Dust（有機的ゆらぎ）──────────────
    // Impulse が主体（安定した密度）+ Dust 20% で機械的すぎない発火感
    // 参照: synthesis_granular.md § Dust.ar(density)
    trig_base  = Impulse.ar(density_live) + Dust.ar(density_live * 0.2);
    // 上層は疎な Dust 発火（ふわっとした偶発的な倍音が出る感覚）
    trig_upper = Dust.ar(density_live * 0.55);

    // ── 基音層: freq の GrainSin 雲 ──────────────────────────────────
    // grainDur を小さくゆらして「完全に均一でない」有機感を加える
    // 参照: synthesis_granular.md § GrainSin.ar(...) Synthesis-only Drone
    // GrainSin に amp 引数はないため、出力に乗算する
    sig_base = GrainSin.ar(
        numChannels: 2,
        trigger:     trig_base,
        dur:         grainDur + LFNoise1.kr(0.5).range(0.0, grainDur * 0.2),
        freq:        freq_base,
        pan:         a3_pan
    ) * amp;

    // ── 上方倍音層: オクターブ上（freq * 2）の疎なグレイン雲 ──────────
    // bright パラメーターで量を制御。0 なら完全に暗い、1 なら明るい質感。
    // 上層は少し揺れて「倍音が漂う」感覚を作る（単純な×2 にしない）
    freq_upper = freq * 2.0 * LFNoise1.kr(0.3).range(0.99, 1.01);
    pan_upper  = LFNoise1.kr(2.0).range(panSpread.neg * 0.8, panSpread * 0.8);

    sig_upper = GrainSin.ar(
        numChannels: 2,
        trigger:     trig_upper,
        dur:         grainDur * 0.7,
        freq:        freq_upper,
        pan:         pan_upper
    ) * (amp * bright * 0.45);

    // ── ミックス ─────────────────────────────────────────────────────
    sig = sig_base + sig_upper;

    // ── FreeVerb2: 空間化 ─────────────────────────────────────────────
    // room が大きいほど広く溶けていく。
    // damp は room と逆相関（広い空間は高域が残る）
    wet = FreeVerb2.ar(
        sig[0], sig[1],
        mix:  room.linlin(0.0, 1.0, 0.3, 0.8),
        room: room.linlin(0.0, 1.0, 0.5, 0.9),
        damp: room.linlin(0.0, 1.0, 0.6, 0.1)
    );

    // ── エンベロープ ─────────────────────────────────────────────────
    // attack 2秒（ゆっくり立ち上がる）/ release 5秒（ゆっくり消える）
    // drone.scd の 4秒/8秒 より短め: 演奏中の即応性を確保
    // attack 0.5秒（ON後すぐ聞こえる）/ release 3秒（ゆっくり消える）
    env = EnvGen.ar(Env.adsr(0.5, 0.1, 0.9, 3.0), gate, doneAction: 2);

    // ── 安全制御: Limiter ─────────────────────────────────────────────
    // 高密度グレインの重なりでピークが出やすいため 0.85 で頭打ち
    Out.ar(outBus, Limiter.ar(wet * env, 0.85));
}).add;

s.sync;
"SynthDef定義完了: \\matoma_gran_synth (バッファ不要グラニュラーシンセ v1)".postln;

// ── グローバル変数 ─────────────────────────────────────────────────
~currentGranSynth = nil;

// ── OSCdef: グラニュラーシンセ 開始 ──────────────────────────────────
// 既に鳴っていれば gate=0 でフェードアウトしてから新しく起動する
OSCdef(\matoma_gran_synth_start, { |msg|
    {
        if (~currentGranSynth.notNil) {
            ~currentGranSynth.set(\gate, 0);
        };
        ~currentGranSynth = Synth(\matoma_gran_synth, [
            \outBus, ~effectBus.index
        ], addAction: \addToTail);
        "グラニュラーシンセ開始 (freq:110 density:35 grainDur:0.18)".postln;
    }.defer;
}, '/matoma/gran_synth/start', nil, 57200);

// ── OSCdef: グラニュラーシンセ 停止 ──────────────────────────────────
// gate=0 → Env.adsr の release（5秒フェードアウト）が走る
OSCdef(\matoma_gran_synth_stop, { |msg|
    {
        if (~currentGranSynth.notNil) {
            ~currentGranSynth.set(\gate, 0);
            ~currentGranSynth = nil;
            "グラニュラーシンセ停止（5秒フェードアウト）".postln;
        };
    }.defer;
}, '/matoma/gran_synth/stop', nil, 57200);

// ── OSCdef: グラニュラーシンせ パラメーター ──────────────────────────
// 許可リストで想定外パラメーターを弾く（セキュリティ）
OSCdef(\matoma_gran_synth_param, { |msg|
    var param = msg[1].asSymbol;
    var value = msg[2].asFloat;
    var allowed = #[\freq, \density, \grainDur, \spread, \panSpread,
                    \bright, \chaos, \room, \amp, \gate];
    {
        if (allowed.includes(param).not) {
            "gran_synth/param: 許可されていないパラメーター '%' を無視".format(param).postln;
        } {
            if (~currentGranSynth.notNil) {
                ~currentGranSynth.set(param, value);
                "グラニュラーシンセ param: % = %".format(param, value.round(0.001)).postln;
            };
        };
    }.defer;
}, '/matoma/gran_synth/param', nil, 57200);

"グラニュラーシンセモジュール ロード完了 (v1 バッファ不要・独立型)".postln;
