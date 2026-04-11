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
        pitch   = 0.5,   // 周波数帯域の中心（0=超低域50Hz、1=超高域4kHz）
        filterQ = 0.5,   // フィルター共振（0=なだらか、1=鋭い共振）
        amp     = 0.3;

    var noiseRate = rate.linexp(0.0, 1.0, 0.5, 5000.0);
    var pitchBase = pitch.linexp(0.0, 1.0, 50.0, 4000.0);

    // L: pitchBaseを中心にFM揺れ（音域が pitch で大きく変わる）
    var freqModL = LFDNoise3.ar(noiseRate * 0.7) * fmDepth * pitchBase + pitchBase;
    var sigL     = LFDNoise3.ar(freqModL);

    // 位相リセット + Hasherでデジタルクランチテクスチャ
    var phasor = Phasor.ar(0, noiseRate / SampleRate.ir, 0, 1);
    var hashed = Hasher.ar(phasor);

    // R: 微妙にデチューンしたFM + 自己変調（L と明確に異なる音）
    var freqModR = LFDNoise3.ar(noiseRate * 0.73) * fmDepth * pitchBase * 0.97 + (pitchBase * 1.03);
    var sigR     = LFDNoise1.ar(freqModR * (1 + (sigL * fmDepth)));

    var sig = [
        sigL * 0.5 + (hashed * fmDepth * 0.5),
        sigR * 0.5 + (hashed * fmDepth * 0.3)
    ];

    // フィルター: pitchBase × rate 倍でカットオフ、filterQで共振量を制御
    var filterCutoff = (pitchBase * rate.linexp(0.0, 1.0, 2.0, 20.0)).clip(80.0, 18000.0);
    var rq = filterQ.linlin(0.0, 1.0, 0.8, 0.05);
    sig = RLPF.ar(sig, filterCutoff, rq);
    sig = LeakDC.ar(sig);
    sig = Limiter.ar(sig, 0.9);
    Out.ar(~effectBus, sig * amp);
    Out.ar(out, sig * amp);
}).add;

s.sync;
"SynthDef定義完了: \\matoma_glitch_chaos".postln;


// ── 3. バースト生成: Dust + Ringz（共通スケール制約版）────────────
// サンプルから変えた点: Dwhite(任意周波数) → BufRd(~scaleBuf からスケール音程を選択)
// spread はバッファ内の選択範囲幅に変換（0=中域集中、1=全オクターブ分散）
SynthDef(\matoma_glitch_burst, {
    arg out           = 0,
        density       = 0.3,   // 射出頻度（0=稀、1=高密度）
        freq          = 0.5,   // 参照周波数 (BPFノイズのみ使用)
        decay         = 0.3,   // 減衰時間（0=極短、1=長め）
        spread        = 0.5,   // 音程分散（0=中域集中、1=全オクターブ）
        amp           = 0.4,
        scaleBuf      = 0,     // ~scaleBuf.bufnum
        numScaleFreqs = 15;    // ~scaleBuf.numFrames（3オクターブ×5音程など）

    var dustRate  = density.linexp(0.0, 1.0, 0.5, 200.0);
    var baseFreq  = freq.linexp(0.0, 1.0, 100.0, 8000.0);
    var decayTime = decay.linexp(0.0, 1.0, 0.003, 0.3);

    var dustL  = Dust.ar(dustRate);
    var dustR  = Dust.ar(dustRate * 0.97);
    // 第2レイヤー: 低密度・倍音帯域のバースト
    var dustL2 = Dust.ar(dustRate * 0.35);
    var dustR2 = Dust.ar(dustRate * 0.33);

    // spread → バッファ選択範囲（低spread=下位オクターブ集中、高spread=全域分散）
    var maxIdx    = numScaleFreqs - 1;
    var rangeMid  = maxIdx * 0.5;
    var halfRange = (maxIdx * spread.linlin(0.0, 1.0, 0.15, 0.5)).round.max(1);
    var loIdx     = (rangeMid - halfRange).max(0);
    var hiIdx     = (rangeMid + halfRange).min(maxIdx);

    // メインRingz: BufRd でスケール音程から周波数を選択（interp=1 = 最近傍、補間なし）
    var freqL = BufRd.ar(1, scaleBuf, Demand.ar(dustL,  0, Dwhite(loIdx, hiIdx, inf)), 1, 1);
    var freqR = BufRd.ar(1, scaleBuf, Demand.ar(dustR,  0, Dwhite(loIdx, hiIdx, inf)), 1, 1);
    var ringL = Ringz.ar(CoinGate.ar(0.7, dustL), freqL, decayTime);
    var ringR = Ringz.ar(CoinGate.ar(0.7, dustR), freqR, decayTime);

    // 第2レイヤーRingz: 高オクターブ側（2倍音）でテクスチャに奥行き
    var freqL2 = BufRd.ar(1, scaleBuf, Demand.ar(dustL2, 0, Dwhite(loIdx, maxIdx, inf)), 1, 1) * 2.0;
    var freqR2 = BufRd.ar(1, scaleBuf, Demand.ar(dustR2, 0, Dwhite(loIdx, maxIdx, inf)), 1, 1) * 2.0;
    var ringL2 = Ringz.ar(CoinGate.ar(0.5, dustL2), freqL2, decayTime * 2.0) * 0.4;
    var ringR2 = Ringz.ar(CoinGate.ar(0.5, dustR2), freqR2, decayTime * 2.0) * 0.4;

    var noiseL = BPF.ar(WhiteNoise.ar, baseFreq * 1.5, 0.2) *
                 EnvGen.ar(Env.perc(0.001, decayTime * 0.5), dustL);
    var noiseR = BPF.ar(WhiteNoise.ar, baseFreq * 1.3, 0.2) *
                 EnvGen.ar(Env.perc(0.001, decayTime * 0.5), dustR);

    var sig = Limiter.ar([
        ringL + ringL2 + noiseL,
        ringR + ringR2 + noiseR
    ], 0.9);
    Out.ar(~effectBus, sig * amp);
    Out.ar(out, sig * amp);
}).add;

s.sync;
"SynthDef定義完了: \\matoma_glitch_burst".postln;
"グリッチシンセ 3種 ロード完了".postln;
