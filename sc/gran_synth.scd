// ══════════════════════════════════════════════════════════════════
//  MaToMa gran_synth.scd  — グラニュラーシンセ（バッファ不要・独立型）v2
//
//  【v2 改良点】
//    v1 問題: GrainSin単層 + 微弱モジュレーション → オシレータに近い質感
//    v2 解決:
//      1. 多層グレイン構造（sub / base×3 / harm×3 / FM層 / ノイズ層）
//      2. GrainFM: chaos高→FM合成グレイン（金属的・非調和的テクスチャ）
//      3. spread: 複数インスタンスのfreqを独立LFNoiseで散乱 → 「霧の和音」
//      4. harm:   倍音列（2x/3x/5x）の豊かさを独立制御
//      5. chaos:  0=滑らかなサイン雲 → 0.5=倍音+散乱 → 1.0=FM+ノイズ破壊
//
//  【シグナルチェーン】
//    Layer 1: GrainSin (sub, freq/2)     × bright逆依存（低音の土台）
//    Layer 2: GrainSin (base, freq) ×3   × spread散乱（霧の基音）
//    Layer 3: GrainSin (harm, 2x/3x/5x) × harm × bright（倍音の冠）
//    Layer 4: GrainFM  (FM grains)       × chaos（金属的カオス）
//    Layer 5: BPF WhiteNoise/GrayNoise   × chaos（砂嵐テクスチャ）
//      → FreeVerb2 → Env.adsr → Limiter → Out
//
//  【パラメーター】
//    freq      : 基音（Hz）。デフォルト 110（A2）
//    density   : グレイン密度（/秒）。大きいほど密で途切れない（5〜60）
//    grainDur  : 基準グレイン長（秒）。大きいほど滑らか・アンビエント的
//    spread    : 周波数散乱（0=純粋コヒーレント、1=広く霧状に散乱）
//    panSpread : ステレオ広がり（0=中央、1=最大）
//    bright    : 上倍音量（0=暗くサブ重視、1=明るく上倍音重視）
//    harm      : 倍音構造（0=基音サイン波のみ、1=倍音列が鳴り響く）
//    chaos     : カオス強度（0=滑らか純粋、1=FM+ノイズ・不規則・破壊的）
//    room      : リバーブ量（0〜1）
//    amp       : 音量（0〜1）
//    gate      : エンベロープゲート（1=持続、0=フェードアウト）
//
//  【OSCアドレス（port 57200）】
//    /matoma/gran_synth/start
//    /matoma/gran_synth/stop
//    /matoma/gran_synth/param [名前] [値]
//      例: spread 0.7 / harm 0.6 / chaos 0.8 / freq_norm 0.4
// ══════════════════════════════════════════════════════════════════

SynthDef(\matoma_gran_synth, {
    arg freq      = 110,   // 基音（Hz）: A2
        density   = 35,    // グレイン密度（/秒）
        grainDur  = 0.18,  // 基準グレイン長（秒）
        spread    = 0.2,   // 周波数散乱（0=純粋、1=霧状）
        panSpread = 0.7,   // ステレオ広がり
        bright    = 0.4,   // 上倍音量（0=暗い、1=明るい）
        harm      = 0.3,   // 倍音構造（0=サイン波、1=複雑な倍音列）
        chaos     = 0.3,   // カオス強度（0=滑らか、1=FM+ノイズ）
        room      = 0.6,   // リバーブ量
        amp       = 0.4,   // 音量
        gate      = 1,     // ゲート
        outBus    = 0;     // 出力バス

    // SCルール: var宣言はすべて先頭にまとめる
    var a1_density_mod, a2_pitch_mod, a3_pan;
    var density_live, freq_live;

    // Layer 1: Sub（低音の土台）
    var sub_trig, sub_freq, sig_sub;

    // Layer 2: Base × 3（spread散乱）
    var base_trig1, base_trig2, base_trig3;
    var freq1, freq2, freq3;
    var sig_base1, sig_base2, sig_base3;

    // Layer 3: Harmonics（倍音列）
    var harm_trig2, harm_trig3, harm_trig5;
    var sig_harm2, sig_harm3, sig_harm5;

    // Layer 4: FM Grains（GrainFM）
    var fm_density, fm_trig, fm_dur, fm_modfreq, fm_index, sig_fm;

    // Layer 5: Noise Texture
    var noise_cf, sig_noise, sig_noise2;

    // Mix + FX
    var sig, wet, env;

    // ── Layer A1: 呼吸（0.04 Hz）— density を揺らす ─────────────────
    a1_density_mod = LFNoise2.kr(0.04).range(
        1.0 - (0.3 * chaos),
        1.0 + (0.3 * chaos)
    );

    // ── Layer A2: 心拍（0.15 Hz）— ピッチを微妙に揺らす ─────────────
    // v1より幅を狭める（ピッチが崩れすぎないように）
    a2_pitch_mod = LFNoise2.kr(0.15).range(
        1.0 - (0.012 * (1.0 + chaos)),
        1.0 + (0.012 * (1.0 + chaos))
    );

    // ── Layer A3: 神経（3 Hz）— pan をゆっくり動かす ─────────────────
    a3_pan = LFNoise1.kr(3.0).range(panSpread.neg, panSpread);

    density_live = (density * a1_density_mod).clip(5, 80);
    freq_live    = freq * a2_pitch_mod;

    // ═══════════════════════════════════════════════════════════════
    // LAYER 1: SUB — 重低音の土台（freq/2）
    // ═══════════════════════════════════════════════════════════════
    // 粗な密度・長いgrain → 持続する低音ベース
    // bright=1（高域重視）の時は引っ込む、bright=0（低域重視）の時に前面に出る
    sub_trig = Dust.ar(density_live * 0.12);
    sub_freq = freq_live * 0.5 * LFNoise1.kr(0.09).range(0.995, 1.005);
    sig_sub  = GrainSin.ar(
        numChannels: 2,
        trigger:     sub_trig,
        dur:         grainDur * 3.0 + LFNoise1.kr(0.15).range(0, grainDur),
        freq:        sub_freq,
        pan:         LFNoise1.kr(0.4).range(-0.25, 0.25)
    ) * (amp * (0.55 - bright * 0.45).max(0.04));

    // ═══════════════════════════════════════════════════════════════
    // LAYER 2: BASE × 3 — 基音グレイン雲（spread散乱）
    // ═══════════════════════════════════════════════════════════════
    // 3インスタンスの freq を独立 LFNoise で散乱させる。
    // spread=0 → ほぼ同一周波数（コヒーレントなサイン波の雲）
    // spread=1 → ±12%散乱（霧状の和音テクスチャ）
    base_trig1 = Impulse.ar(density_live) + Dust.ar(density_live * 0.2);
    base_trig2 = Dust.ar(density_live * 0.6);
    base_trig3 = Dust.ar(density_live * 0.4);

    freq1 = freq_live * LFNoise1.kr(0.7).range(
        1.0 - (spread * 0.08), 1.0 + (spread * 0.08));
    freq2 = freq_live * LFNoise1.kr(0.5).range(
        1.0 - (spread * 0.12), 1.0 + (spread * 0.12));
    freq3 = freq_live * LFNoise1.kr(0.9).range(
        1.0 - (spread * 0.10), 1.0 + (spread * 0.10));

    sig_base1 = GrainSin.ar(2, base_trig1,
        grainDur + LFNoise1.kr(0.5).range(0.0, grainDur * 0.2),
        freq1, a3_pan
    ) * amp;

    sig_base2 = GrainSin.ar(2, base_trig2, grainDur * 1.3,
        freq2,
        LFNoise1.kr(2.0).range(panSpread.neg * 0.7, panSpread * 0.7)
    ) * amp * (spread * 0.5 + 0.1);

    sig_base3 = GrainSin.ar(2, base_trig3, grainDur * 0.8,
        freq3,
        LFNoise1.kr(1.5).range(panSpread.neg * 0.5, panSpread * 0.5)
    ) * amp * (spread * 0.4 + 0.08);

    // ═══════════════════════════════════════════════════════════════
    // LAYER 3: HARMONICS — 倍音層（harm + bright 制御）
    // ═══════════════════════════════════════════════════════════════
    // 2倍音（オクターブ上）: bright が強い時に出る
    harm_trig2 = Dust.ar(density_live * 0.4);
    sig_harm2  = GrainSin.ar(2, harm_trig2, grainDur * 0.7,
        freq_live * 2.0 * LFNoise1.kr(0.3).range(0.99, 1.01),
        LFNoise1.kr(2.0).range(panSpread.neg * 0.6, panSpread * 0.6)
    ) * amp * bright * 0.45;

    // 3倍音（明るい中域）: harm が強い時に出る
    harm_trig3 = Dust.ar(density_live * 0.22);
    sig_harm3  = GrainSin.ar(2, harm_trig3, grainDur * 0.55,
        freq_live * 3.0 * LFNoise1.kr(0.4).range(0.99, 1.01),
        LFNoise1.kr(2.5).range(panSpread.neg * 0.9, panSpread * 0.9)
    ) * amp * harm * bright * 0.35;

    // 5倍音（鋭い高域）: harm + bright が最大の時に出る
    harm_trig5 = Dust.ar(density_live * 0.12);
    sig_harm5  = GrainSin.ar(2, harm_trig5, grainDur * 0.35,
        freq_live * 5.0 * LFNoise1.kr(0.35).range(0.98, 1.02),
        LFNoise1.kr(3.0).range(panSpread.neg, panSpread)
    ) * amp * harm * bright * 0.22;

    // ═══════════════════════════════════════════════════════════════
    // LAYER 4: FM GRAINS — GrainFM による金属的カオステクスチャ
    // ═══════════════════════════════════════════════════════════════
    // chaos=0   → FM grains ほぼ無音（index≈0 → サイン波に近い）
    // chaos=0.5 → 金属的・鐘状のFMテクスチャが現れる
    // chaos=1.0 → 高密度・高インデックスFMグレイン → 破壊的ノイズ質感
    fm_density = density_live * chaos.linlin(0, 1, 0.04, 0.85);
    fm_trig    = Dust.ar(fm_density);
    fm_dur     = (grainDur * chaos.linlin(0, 1, 0.9, 0.04)).max(0.008);
    fm_modfreq = freq_live * LFNoise1.kr(1.5).range(0.5, 4.0);
    fm_index   = chaos.linlin(0, 1, 0.1, 14.0)
                 + LFNoise0.kr(8).range(0, chaos * 5);

    sig_fm = GrainFM.ar(
        numChannels: 2,
        trigger:     fm_trig,
        dur:         fm_dur + LFNoise1.kr(2.0).range(0, fm_dur * 0.6),
        carfreq:     freq_live * LFNoise0.kr(12).range(0.7, 2.8),
        modfreq:     fm_modfreq,
        index:       fm_index,
        pan:         LFNoise1.kr(4.0).range(panSpread.neg, panSpread)
    ) * amp * chaos * 0.55;

    // ═══════════════════════════════════════════════════════════════
    // LAYER 5: NOISE TEXTURE — chaos制御のバンドパスノイズ
    // ═══════════════════════════════════════════════════════════════
    // 連続的なノイズ層: chaos=0で完全無音、chaos=1で「砂嵐」的テクスチャ
    noise_cf   = freq_live * LFNoise1.kr(0.3).range(1.5, 6.0);
    sig_noise  = BPF.ar(WhiteNoise.ar, noise_cf, 0.15)
                 * chaos * amp * 0.22;
    sig_noise2 = BPF.ar(GrayNoise.ar,
        freq_live * LFNoise1.kr(0.5).range(2.0, 8.0), 0.18)
                 * chaos * amp * 0.14;

    // ═══════════════════════════════════════════════════════════════
    // MIX
    // ═══════════════════════════════════════════════════════════════
    sig = sig_sub
        + sig_base1 + sig_base2 + sig_base3
        + sig_harm2 + sig_harm3 + sig_harm5
        + sig_fm
        + sig_noise + sig_noise2;

    // ── FreeVerb2: 空間化 ──────────────────────────────────────────
    wet = FreeVerb2.ar(
        sig[0], sig[1],
        mix:  room.linlin(0.0, 1.0, 0.3, 0.8),
        room: room.linlin(0.0, 1.0, 0.5, 0.9),
        damp: room.linlin(0.0, 1.0, 0.6, 0.1)
    );

    // ── エンベロープ: attack 0.5秒 / release 3秒 ──────────────────
    env = EnvGen.ar(Env.adsr(0.5, 0.1, 0.9, 3.0), gate, doneAction: 2);

    Out.ar(outBus, Limiter.ar(wet * env, 0.85));
}).add;

s.sync;
"SynthDef定義完了: \\matoma_gran_synth (v2 多層グレイン+GrainFM)".postln;

// ── グローバル変数 ─────────────────────────────────────────────────
~currentGranSynth = nil;

// ── OSCdef: グラニュラーシンセ 開始 ──────────────────────────────────
OSCdef(\matoma_gran_synth_start, { |msg|
    {
        if (~currentGranSynth.notNil) {
            ~currentGranSynth.set(\gate, 0);
        };
        ~currentGranSynth = Synth(\matoma_gran_synth, [
            \outBus, 0
        ], addAction: \addToTail);
        "グラニュラーシンセ開始 v2 (freq:110 density:35 spread:0.2 harm:0.3 chaos:0.3)".postln;
    }.defer;
}, '/matoma/gran_synth/start', nil, 57200);

// ── OSCdef: グラニュラーシンセ 停止 ──────────────────────────────────
OSCdef(\matoma_gran_synth_stop, { |msg|
    {
        if (~currentGranSynth.notNil) {
            ~currentGranSynth.set(\gate, 0);
            ~currentGranSynth = nil;
            "グラニュラーシンセ停止（3秒フェードアウト）".postln;
        };
    }.defer;
}, '/matoma/gran_synth/stop', nil, 57200);

// ── OSCdef: グラニュラーシンセ パラメーター ──────────────────────────
// freq_norm (0〜1) → 55〜880 Hz（A1〜A5）の対数スケールでマップ
// harm, spread が新規パラメーター（v2追加）
OSCdef(\matoma_gran_synth_param, { |msg|
    var param = msg[1].asSymbol;
    var value = msg[2].asFloat;
    var allowed = #[\freq, \freq_norm, \density, \grainDur, \spread, \panSpread,
                    \bright, \harm, \chaos, \room, \amp, \gate];
    {
        if (allowed.includes(param).not) {
            "gran_synth/param: 許可されていないパラメーター '%' を無視".format(param).postln;
        } {
            if (~currentGranSynth.notNil) {
                if (param == \freq_norm) {
                    // 0.0〜1.0 → 55〜880 Hz（A1〜A5）に対数マップ
                    ~currentGranSynth.set(\freq, value.linexp(0.0, 1.0, 55.0, 880.0));
                } {
                    ~currentGranSynth.set(param, value);
                };
                "グラニュラーシンセ param: % = %".format(param, value.round(0.001)).postln;
            };
        };
    }.defer;
}, '/matoma/gran_synth/param', nil, 57200);

"グラニュラーシンセモジュール ロード完了 (v2 多層グレイン+GrainFM)".postln;
