// MaToMa専用ポート57200を使用（SC内部ポート57120/57121との衝突を回避）
thisProcess.openUDPPort(57200);

// GVerb等の大型UGen用にリアルタイムメモリを拡張（デフォルト8MB→128MB）
s.options.memSize = 131072;

s.waitForBoot({
    "SCサーバー起動完了".postln;
    "MaToMa OSC受信ポート: 57200".postln;

    ServerQuit.add({ "!!! scsynth が終了しました !!!".postln; });

    // 起動確認音（880Hz ビープ 0.5秒）
    { var sig = SinOsc.ar(880,0,0.2)*EnvGen.kr(Env.perc(0.01,0.4),doneAction:2); Out.ar(0,sig!2); }.play;
    "起動確認音を再生（聞こえれば音声出力OK）".postln;

    SynthDef(\matoma_basic, {
        arg freq = 220, cutoff = 1200, amp = 0.6, chaos = 0.4;
        // SCルール: var宣言はすべて先頭にまとめる
        var mod1Freq, mod1Sig, mod2Freq, mod2Sig, modIndex;
        var fbL, fbR;
        var noiseL, noiseR, cfNoise;
        var sigL, sigR, cf, out;

        // ── 2オペレーターFM ──────────────────────────────────────────────
        // モジュレーター1: 基本倍音を作る（整数比に近い周波数）
        mod1Freq = freq * LFNoise2.kr(0.06).range(1.98, 2.02);  // 2倍音付近でゆれる
        modIndex = chaos * 8 * (1 + LFNoise2.kr(0.04).range(-0.2, 0.3));
        mod1Sig  = SinOsc.ar(mod1Freq, 0, modIndex * freq);

        // モジュレーター2: 非整数比でザラつきと複雑さを加える
        mod2Freq = freq * LFNoise2.kr(0.05).range(1.3, 1.7);
        mod2Sig  = SinOsc.ar(mod2Freq, 0, modIndex * freq * 0.5);

        // ── SinOscFB（自己フィードバックFM）──────────────────────────────
        // 出力が自分に戻ることで、鐘・金属・倍音の嵐のような複雑な音色に
        // fbL/fbR はL/Rで異なるフィードバック量 → 非対称なステレオ感
        fbL = SinOscFB.ar(freq + mod1Sig + mod2Sig * 0.3 + LFNoise2.kr(0.05, freq * 0.003),
                          chaos * 0.7);
        fbL = fbL + SinOscFB.ar(freq * 1.5 + mod1Sig * 0.4, chaos * 0.4) * 0.3;

        fbR = SinOscFB.ar(freq + mod1Sig * 1.05 + mod2Sig * 0.4 + LFNoise2.kr(0.08, freq * 0.003),
                          chaos * 0.65);
        fbR = fbR + SinOscFB.ar(freq * 1.5 + mod1Sig * 0.45, chaos * 0.45) * 0.3;

        sigL = fbL;
        sigR = fbR;

        // ── ノイズテクスチャ（息・霧のような質感） ───────────────────────
        cfNoise = freq * LFNoise2.kr(0.08).range(2.0, 5.0);
        noiseL  = BPF.ar(WhiteNoise.ar, cfNoise,        0.3) * chaos * 0.12;
        noiseR  = BPF.ar(WhiteNoise.ar, cfNoise * 1.02, 0.3) * chaos * 0.12;

        sigL = sigL + noiseL;
        sigR = sigR + noiseR;

        // ── フィルター ───────────────────────────────────────────────────
        cf   = (cutoff * LFNoise2.kr(0.07).range(0.8, 1.2)).clip(80, 18000);
        sigL = RLPF.ar(sigL, cf,        0.5);
        sigR = RLPF.ar(sigR, cf * 0.97, 0.5);

        sigL = LeakDC.ar((sigL * 1.4).softclip);
        sigR = LeakDC.ar((sigR * 1.4).softclip);

        // ── 空間 ─────────────────────────────────────────────────────────
        out = FreeVerb2.ar(sigL, sigR, mix: 0.45, room: 0.8, damp: 0.35);
        Out.ar(0, out * amp);
    }).add;

    s.sync;
    "シンセ定義完了".postln;

    ~currentSynth = nil;

    OSCdef(\matoma_start, { |msg|
        { ~currentSynth = Synth(\matoma_basic); "音を開始".postln; }.defer;
    }, '/matoma/start', nil, 57200);

    OSCdef(\matoma_stop, { |msg|
        { if (~currentSynth.notNil) { ~currentSynth.free; ~currentSynth = nil; "音を停止".postln; }; }.defer;
    }, '/matoma/stop', nil, 57200);

    OSCdef(\matoma_param, { |msg|
        var param = msg[1].asSymbol;
        var value = msg[2].asFloat;
        if (~currentSynth.notNil) {
            ~currentSynth.set(param, value);
        };
    }, '/matoma/param', nil, 57200);

    // ── ドローンモジュール ───────────────────────────────────────────
    SynthDef(\matoma_drone, {
        arg freq    = 60,
            detune  = 0.25,   // アンサンブルの広がり
            cutoff  = 1800,   // 弦楽器の倍音が通る明るさ
            drift   = 0.1,
            room    = 0.85,
            revtime = 12.0,
            amp     = 1.8,    // ← 音量（Limiterで保護済みなのでクリッピングなし）
            breathe = 0.55,
            gate    = 1;

        var lfoRate, lfoSignal, cutoffMod, detuneHz;
        var vibrato, breatheAmp;
        var dryL, dryR;
        var wetL, wetR;
        var sigL, sigR, env;

        lfoRate   = drift.clip(0.001, 1).linexp(0.001, 1, 0.01, 0.25);
        lfoSignal = LFNoise1.kr(lfoRate);
        cutoffMod = (cutoff * (1 + lfoSignal * drift)).clip(300, 8000);
        detuneHz  = freq * detune * 0.05;

        // ── 弦楽器らしいビブラート（4.5Hz）──────────────────────────
        // バイオリン・チェロのビブラートは4〜6Hz。
        // これが「たおやか」な弦の生命感を作る。
        vibrato = SinOsc.kr(4.5) * freq * 0.005;

        // ── 呼吸する振幅（安らぎ）───────────────────────────────────
        breatheAmp = 1.0 + SinOsc.kr(0.083) * breathe * 0.2;

        // ── ストリングスアンサンブル：Saw波をデチューンして重ねる ────
        // 弦楽器 = 弓で弦を擦る → 倍音豊富なノコギリ波に近い波形。
        // ノイズなし：ノイズは不安感を生む。純粋な弦の音だけ。
        dryL = Mix([
            Saw.ar(freq + vibrato),
            Saw.ar(freq + vibrato + detuneHz * 0.7)  * 0.8,
            Saw.ar(freq + vibrato + detuneHz * 1.3)  * 0.6,
            Saw.ar(freq + vibrato - detuneHz * 0.4)  * 0.7,
            Saw.ar(freq * 0.5 + vibrato * 0.5)       * 0.35,
        ]) * 0.1;
        dryR = Mix([
            Saw.ar(freq + vibrato),
            Saw.ar(freq + vibrato - detuneHz * 0.7)  * 0.8,
            Saw.ar(freq + vibrato - detuneHz * 1.3)  * 0.6,
            Saw.ar(freq + vibrato + detuneHz * 0.4)  * 0.7,
            Saw.ar(freq * 0.5 + vibrato * 0.5)       * 0.35,
        ]) * 0.1;

        dryL = dryL * breatheAmp;
        dryR = dryR * breatheAmp;

        // ── 温かいローパスフィルター──────────────────────────────────
        // Saw波の高次倍音をカットして「たおやか」な弦の丸みを作る
        dryL = RLPF.ar(dryL, cutoffMod,        0.6);
        dryR = RLPF.ar(dryR, cutoffMod * 0.97, 0.6);

        // ── ソフトサチュレーション ────────────────────────────────────
        dryL = LeakDC.ar((dryL * 1.8).tanh) * 0.6;
        dryR = LeakDC.ar((dryR * 1.8).tanh) * 0.6;

        // ── エンベロープ（0.3秒の柔らかい立ち上がり）────────────────
        env  = Linen.kr(gate, 0.3, 1.0, 8.0, 2);
        dryL = dryL * env;
        dryR = dryR * env;

        // ── GVerb（安定版・長い残響）─────────────────────────────────
        wetL = GVerb.ar(dryL, 15, revtime, 0.4, 0.7, 15, 0, 0.4, 0.5, 30);
        wetR = GVerb.ar(dryR, 15, revtime, 0.4, 0.7, 15, 0, 0.4, 0.5, 30);

        sigL = dryL * (1 - room) + (wetL[0] * 0.6 + wetR[1] * 0.4) * room;
        sigR = dryR * (1 - room) + (wetL[1] * 0.4 + wetR[0] * 0.6) * room;

        // Limiter: ampを大きく設定してもクリッピングしないよう保護
        Out.ar(0, Limiter.ar([sigL, sigR] * amp, 0.95));
    }).add;

    s.sync;
    "シンセ定義完了: \\matoma_drone".postln;

    ~currentDrone = nil;

    OSCdef(\matoma_drone_start, { |msg|
        {
            if (~currentDrone.notNil) {
                ~currentDrone.set(\gate, 0);
            };
            ~currentDrone = Synth(\matoma_drone);
            "ドローン開始".postln;
        }.defer;
    }, '/matoma/drone/start', nil, 57200);

    OSCdef(\matoma_drone_stop, { |msg|
        {
            if (~currentDrone.notNil) {
                ~currentDrone.set(\gate, 0);
                ~currentDrone = nil;
                "ドローン停止（8秒でフェードアウト）".postln;
            };
        }.defer;
    }, '/matoma/drone/stop', nil, 57200);

    OSCdef(\matoma_drone_param, { |msg|
        var param = msg[1].asSymbol;
        var value = msg[2].asFloat;
        {
            if (~currentDrone.notNil) {
                ~currentDrone.set(param, value);
                "ドローン param: % = %".format(param, value.round(0.001)).postln;
            };
        }.defer;
    }, '/matoma/drone/param', nil, 57200);

    // ── グラニュラーサンプラーモジュール ────────────────────────────
    SynthDef(\matoma_granular, {
        arg buf = 0,
            rate = 1.0,
            pos = 0.0,
            posrand = 0.05,
            pitchrand = 0.01,
            size = 0.1,
            density = 20,
            trig_mode = 0,
            amp = 0.5,
            gate = 1;

        var trig_random  = Dust.kr(density);
        var trig_regular = Impulse.kr(density);
        var trigger = Select.kr(trig_mode, [trig_random, trig_regular]);

        var grainPos = (pos + TRand.kr(posrand.neg, posrand, trigger)).clip(0.0, 1.0);
        var grainRate = rate * (1.0 + TRand.kr(pitchrand.neg, pitchrand, trigger));
        var pan = TRand.kr(-0.8, 0.8, trigger);

        var sig = GrainBuf.ar(
            numChannels: 2,
            trigger: trigger,
            dur: size,
            sndbuf: buf,
            rate: grainRate,
            pos: grainPos,
            interp: 2,
            pan: pan,
            envbufnum: -1
        );

        sig = sig * Linen.kr(gate, 0.5, 1.0, 2.0, 2);
        sig = sig * amp;
        Out.ar(0, sig);
    }).add;

    s.sync;
    "シンセ定義完了: \\matoma_granular".postln;

    // デモ用バッファ（ファイル未選択時に使うサイン波）
    ~granularBuf = Buffer.alloc(s, (s.sampleRate * 2).round.asInteger, 1, { |buf|
        buf.sine1([1.0, 0.5, 0.25, 0.125], asWavetable: false, normalize: true);
        ~granularBufNum = buf.bufnum;
        "グラニュラー デモ用バッファ生成完了".postln;
    });

    ~currentGranular = nil;

    OSCdef(\matoma_granular_load, { |msg|
        var path = msg[1].asString;
        {
            if (~granularBuf.notNil) { ~granularBuf.free };
            ~granularBuf = Buffer.read(s, path, action: { |buf|
                ~granularBufNum = buf.bufnum;
                if (~currentGranular.notNil) {
                    ~currentGranular.set(\buf, ~granularBufNum);
                };
                "グラニュラー バッファロード完了: %".format(path).postln;
            });
        }.defer;
    }, '/matoma/granular/load', nil, 57200);

    OSCdef(\matoma_granular_start, { |msg|
        {
            if (~currentGranular.notNil) {
                ~currentGranular.set(\gate, 0);
            };
            ~currentGranular = Synth(\matoma_granular, [
                \buf, ~granularBufNum ?? { 0 }
            ]);
            "グラニュラー開始".postln;
        }.defer;
    }, '/matoma/granular/start', nil, 57200);

    OSCdef(\matoma_granular_stop, { |msg|
        {
            if (~currentGranular.notNil) {
                ~currentGranular.set(\gate, 0);
                ~currentGranular = nil;
                "グラニュラー停止".postln;
            };
        }.defer;
    }, '/matoma/granular/stop', nil, 57200);

    OSCdef(\matoma_granular_param, { |msg|
        var param = msg[1].asSymbol;
        var value = msg[2].asFloat;
        {
            if (~currentGranular.notNil) {
                ~currentGranular.set(param, value);
            };
        }.defer;
    }, '/matoma/granular/param', nil, 57200);

    "MaToMa 起動完了。ブラウザで操作してください。".postln;

    // Pythonブリッジへ起動完了を通知（ポート9000 = OSC_LISTEN_PORT）
    NetAddr("127.0.0.1", 9000).sendMsg('/matoma/ready');
    ">>> /matoma/ready 送信完了".postln;
});
