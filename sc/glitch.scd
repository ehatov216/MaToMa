// ══════════════════════════════════════════════════════════════════
//  MaToMa glitch.scd  — グリッチシンセ（独立音源）v1
//
//  【設計方針】
//    エフェクトではなくシンセ（ゼロから音を生成する音源）として実装。
//    Kim Casconeの「ポスト・デジタル」美学: エラーを音楽的素材として使う。
//
//  【3種類のグリッチシンセ】
//    1. \matoma_glitch_gendy  — Gendy確率合成（デジタルの叫び・不安定発振）
//    2. \matoma_glitch_chaos  — LFDNoise + Hasher カオステクスチャ
//    3. \matoma_glitch_burst  — Dust + Ringz バースト粒子
// ══════════════════════════════════════════════════════════════════

// ── 1. Gendy確率合成 ─────────────────────────────────────────────
SynthDef(\matoma_glitch_gendy, {
    arg out = 0,
        chaos   = 0.5,   // ランダムウォーク強度（0=安定、1=完全カオス）
        pitch   = 0.5,   // ピッチ中心（0=超低域20Hz、1=高域8000Hz）
        density = 0.5,   // 制御点数の逆数（0=多い=滑らか、1=少ない=カオス）
        amp     = 0.3;

    var numCPs  = density.linlin(0.0, 1.0, 12.0, 1.0).round.max(1).asInteger;
    var minFreq = pitch.linexp(0.0, 1.0, 20.0, 500.0);
    var maxFreq = pitch.linexp(0.0, 1.0, 200.0, 8000.0);
    var dist    = chaos.linlin(0.0, 1.0, 0.0, 5.0).round.asInteger;

    var sigL = Gendy1.ar(
        ampdist: dist, durdist: dist,
        adparam: chaos, ddparam: chaos,
        minfreq: minFreq, maxfreq: maxFreq,
        ampscale: chaos * 0.8 + 0.1,
        initCPs: numCPs, knum: numCPs
    );
    var sigR = Gendy3.ar(
        ampdist: dist, durdist: dist,
        adparam: chaos * 0.9, ddparam: chaos * 1.1,
        minfreq: minFreq * 1.01, maxfreq: maxFreq * 0.99,
        ampscale: chaos * 0.7 + 0.1,
        initCPs: numCPs, knum: numCPs
    );

    var sig = LeakDC.ar([sigL, sigR]);
    sig = Limiter.ar(sig, 0.9);
    Out.ar(~effectBus, sig * amp);
    Out.ar(out, sig * amp);
}).add;

s.sync;
"SynthDef定義完了: \\matoma_glitch_gendy".postln;


// ── 2. カオス/ノイズ生成 ──────────────────────────────────────────
SynthDef(\matoma_glitch_chaos, {
    arg out = 0,
        rate    = 0.5,   // カオスの速さ（0=遅いうねり、1=高速カオス）
        fmDepth = 0.5,   // FM変調の深さ
        amp     = 0.3;

    var noiseRate = rate.linexp(0.0, 1.0, 0.5, 5000.0);

    var freqMod = LFDNoise3.ar(noiseRate * 0.7) * fmDepth * 500 + 200;
    var sigL    = LFDNoise3.ar(freqMod);

    var phasor = Phasor.ar(0, noiseRate / SampleRate.ir, 0, 1);
    var hashed = Hasher.ar(phasor);

    var sigR = LFDNoise1.ar(noiseRate * (1 + (sigL * fmDepth)));

    var sig = [
        sigL * 0.5 + (hashed * fmDepth * 0.5),
        sigR * 0.5 + (hashed * fmDepth * 0.3)
    ];
    sig = RLPF.ar(sig, rate.linexp(0.0, 1.0, 400.0, 12000.0), 0.5);
    sig = LeakDC.ar(sig);
    sig = Limiter.ar(sig, 0.9);
    Out.ar(~effectBus, sig * amp);
    Out.ar(out, sig * amp);
}).add;

s.sync;
"SynthDef定義完了: \\matoma_glitch_chaos".postln;


// ── 3. バースト生成: Dust + Ringz ────────────────────────────────
SynthDef(\matoma_glitch_burst, {
    arg out = 0,
        density = 0.3,   // 射出頻度（0=稀、1=高密度）
        freq    = 0.5,   // 共振周波数（0=低域、1=高域）
        decay   = 0.3,   // 減衰時間（0=極短、1=長め）
        amp     = 0.4;

    var dustRate  = density.linexp(0.0, 1.0, 0.5, 200.0);
    var baseFreq  = freq.linexp(0.0, 1.0, 100.0, 8000.0);
    var decayTime = decay.linexp(0.0, 1.0, 0.003, 0.3);

    var dustL = Dust.ar(dustRate);
    var dustR = Dust.ar(dustRate * 0.97);

    var ringL = Ringz.ar(
        CoinGate.ar(0.7, dustL),
        Demand.ar(dustL, 0, Dwhite(baseFreq * 0.5, baseFreq * 2.0, inf)),
        decayTime
    );
    var ringR = Ringz.ar(
        CoinGate.ar(0.7, dustR),
        Demand.ar(dustR, 0, Dwhite(baseFreq * 0.5, baseFreq * 2.0, inf)),
        decayTime
    );

    var noiseL = BPF.ar(WhiteNoise.ar, baseFreq * 1.5, 0.2) *
                 EnvGen.ar(Env.perc(0.001, decayTime * 0.5), dustL);
    var noiseR = BPF.ar(WhiteNoise.ar, baseFreq * 1.3, 0.2) *
                 EnvGen.ar(Env.perc(0.001, decayTime * 0.5), dustR);

    var sig = Limiter.ar([ringL + noiseL, ringR + noiseR], 0.9);
    Out.ar(~effectBus, sig * amp);
    Out.ar(out, sig * amp);
}).add;

s.sync;
"SynthDef定義完了: \\matoma_glitch_burst".postln;
"グリッチシンセ 3種 ロード完了".postln;
