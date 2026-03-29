// ══════════════════════════════════════════════════════════════════
//  MaToMa run_headless.scd  — ヘッドレス SC 起動スクリプト v4
//
//  【起動順序】
//    1. バス確保: ~droneBus / ~effectBus
//    2. SynthDef 定義（Drone v3 自己組織化FB / Granular / Effects / Rhythmic）
//    3. OSCdef 登録
//    4. 常駐シンセ起動:
//       - Effect パススルー Out（~effectBus → Out 0）
//       - Granular Recorder（~droneBus → リングバッファ）
//    5. Turing Machine 自動スタート（prob=0.2、控えめ）
//    6. Drone 自動スタート（起動直後から音が出る）
//    7. /matoma/ready を Python へ送信
//
//  【ポート】
//    Python → SC : 57200（MaToMa専用、scsynth内部 57120/57121 と衝突しない）
//    SC → Python : 9000
//
//  【Drone 設計変更】
//    旧: Ndef(\drone) + Saw波  → Ndef.stop() が効かない問題あり
//    v2: SynthDef(\matoma_drone) + ~currentDrone Synth管理
//        停止は ~currentDrone.set(\gate, 0) → Env.adsr release で 8秒フェード
//        drone.scd v2 Klankベース「共鳴育成型」を採用
//    v3: 自己組織化フィードバックネットワーク型（2026-03-29）
//        FreqShift(-1Hz) + DelayC + AllpassC (rumush パターン)
//        Resonz 温かみ追加 (a_loss_of_self パターン)
//        Klank 倍音 6本拡張、feedback_amt=0.4、shimmer=0.5
//
//  【パラメーター範囲】
//    freq         : 20Hz〜300Hz（超低域〜中低域）
//    feedback_amt : 0.0〜0.75（破壊的フィードバック対応）
//    shimmer      : 0.0〜1.0（浮遊感の強さ）
//    room         : 0.0〜1.0（空間の広さ）
// ══════════════════════════════════════════════════════════════════

// SCディレクトリを起動時に取得（waitForBoot内では nil になる場合があるため）
~matomaScDir = thisProcess.nowExecutingPath.dirname;
"SC dir: %".format(~matomaScDir).postln;

// MaToMa専用ポート（scsynth内部 57120/57121 と衝突しない）
thisProcess.openUDPPort(57200);

// GVerb 等の大型UGen に必要な RTメモリ（デフォルト 8MB → 128MB）
s.options.memSize = 131072;

// 出力デバイスを設定（backend/audio_device.txt から読み込む、なければデフォルト）
~matomaDeviceConfig = ~matomaScDir.dirname +/+ "backend" +/+ "audio_device.txt";
s.options.outDevice = if (File.exists(~matomaDeviceConfig)) {
    var f = File(~matomaDeviceConfig, "r");
    var d = f.readAllString;
    f.close;
    d.asString
} { "" };
s.options.inDevice  = "";
"出力デバイス: %".format(
    if (s.options.outDevice.isEmpty) { "(システムデフォルト)" } { s.options.outDevice }
).postln;

s.waitForBoot({
    "SCサーバー起動完了".postln;
    "MaToMa OSC受信ポート: 57200".postln;

    // scsynth が落ちたら自動再起動
    ServerQuit.add({
        "!!! scsynth が終了 — 3秒後に再起動 !!!".postln;
        3.wait;
        s.boot;
    });

    // 起動確認音（880Hz 0.4秒）
    { SinOsc.ar(880, 0, 0.2) * EnvGen.kr(Env.perc(0.01, 0.4), doneAction: 2) }.play;

    // ══════════════════════════════════════════════════════════════
    // ■ STEP 1: 共有バスの確保
    //
    //   すべての SynthDef 定義より前に確保する。
    //   ~droneBus  : Drone → Granular の素材ルート
    //   ~effectBus : 全音源 → グローバルエフェクト層ルート
    // ══════════════════════════════════════════════════════════════
    ~droneBus  = Bus.audio(s, 2);
    ~effectBus = Bus.audio(s, 2);

    "共有バス確保完了: ~droneBus=%, ~effectBus=%".format(
        ~droneBus, ~effectBus).postln;

    // ══════════════════════════════════════════════════════════════
    // ■ STEP 2: DRONE v3 — 自己組織化フィードバックネットワーク型
    //
    //   設計:
    //     PinkNoise + LocalIn feedback
    //     → Klank (6倍音バンク × L/R)
    //     → FreqShift.ar(-1Hz) — 微小ピッチシフトで有機的変化
    //     → DelayC × 2 + AllpassC — 自己組織化フィードバック (rumush パターン)
    //     → HPF.ar(40) — DCオフセット除去
    //     → LocalOut.ar(* feedback_amt * 1.8) — 増幅フィードバック
    //     [klanked から分岐]
    //     → Resonz.ar — 体鳴り・温かみ追加 (a_loss_of_self パターン)
    //     → LeakDC + tanh — サチュレーション
    //     → PitchShift Shimmer — 浮遊感
    //     → Out.ar(~droneBus) + FreeVerb2 → Out.ar(0)
    //
    //   停止は gate=0 で Env.adsr release（8秒フェード）が走る。
    //
    //   パラメーター範囲:
    //     freq         : 20〜300 Hz（超低域〜中低域、OSC側で制御）
    //     feedback_amt : 0.0〜0.75（0.5超から破壊的な倍音自己増幅）
    //     shimmer      : 0.0〜1.0（浮遊感の強さ）
    //     room         : 0.0〜1.0（FreeVerb2 の room size）
    //     amp          : 0.0〜1.0
    //     gate         : 1=持続、0=フェードアウト開始
    // ══════════════════════════════════════════════════════════════
    SynthDef(\matoma_drone, {
        arg freq         = 60,
            feedback_amt = 0.4,
            shimmer      = 0.5,
            room         = 0.75,
            amp          = 0.35,
            atk          = 4.0,   // アタック時間（再セットアップ時は短くできる）
            gate         = 1;

        // var 宣言はすべて先頭にまとめる（SC のルール）
        var noise, fb, klankedL, klankedR, klanked;
        var delayed, warmth, saturated;
        var pitchShifted, shimmered;
        var env, sig;

        // ── PinkNoise: 共鳴の「種」 ──────────────────────────────────
        // 自然界に近いスペクトル分布 → Klank が「自然に育つ音」に変換する
        noise = PinkNoise.ar(0.12);

        // ── LocalIn: 自己組織化フィードバックの入口 ──────────────────
        // rumush パターン: 前サンプルの信号を取り込んで自己組織化する
        fb = LocalIn.ar(2);

        // ── Klank: 倍音フィルターバンク 6本（胴鳴り） ───────────────
        // 非整数倍音 6本 = 「空気の塊」的な質感。旧5本から拡張。
        // L チャンネル: 基音重視の配置
        klankedL = Klank.ar(`[
            [freq,        freq * 1.501, freq * 2.756, freq * 3.999, freq * 5.404, freq * 7.102],
            [1.0,         0.7,          0.5,          0.3,          0.15,         0.08],
            [4.0,         3.0,          2.0,          1.5,          1.0,          0.7]
        ], noise + (fb[0] * feedback_amt.clip(0, 0.75)));

        // R チャンネル: わずかに異なる比率でステレオ感
        klankedR = Klank.ar(`[
            [freq * 1.003, freq * 1.504, freq * 2.759, freq * 4.003, freq * 5.408, freq * 7.106],
            [0.9,          0.65,         0.45,         0.27,         0.13,         0.07],
            [4.1,          3.1,          2.1,          1.55,         1.05,         0.75]
        ], noise + (fb[1] * feedback_amt.clip(0, 0.75)));

        klanked = [klankedL, klankedR];

        // ── AllpassC: ランダムなオールパスで有機的変化（ビルトインのみ）──
        // FreqShift(sc3-plugins依存)の代わりに AllpassC で変化を生成
        // LFNoise1 で遅延時間をゆっくり変化させることで音が生き物のように動く
        delayed = klanked + AllpassC.ar(
            klanked, 0.15,
            LFNoise1.kr([0.07, 0.09]).range(0.02, 0.12),
            3.0
        );
        delayed = delayed + DelayC.ar(
            klanked, 0.25,
            LFNoise2.kr([0.03, 0.05]).range(0.01, 0.08)
        );
        // HPF: DCオフセット除去
        delayed = HPF.ar(delayed, 40);

        // ── LocalOut: フィードバックの出口 ───────────────────────────
        LocalOut.ar(delayed * feedback_amt * 1.5);

        // ── Resonz + tanh: 体鳴り・温かみ追加 ───────────────────────
        // a_loss_of_self パターン準拠:
        //   (sig * 0.75) + (Resonz.ar(sig, freq, 0.15) * 1.125)
        // klanked 信号に Resonz を混ぜて「胴鳴り」感を追加
        warmth    = Resonz.ar(klanked, freq * 1.001, 0.18) * 0.9;
        saturated = LeakDC.ar(((klanked + warmth) * 2.2).tanh) * 0.5;

        // ── Shimmer Reverb ────────────────────────────────────────────
        // リバーブ尾部をオクターブ上にピッチシフト → 浮遊感・広がり
        pitchShifted = PitchShift.ar(saturated, 0.1, 2.0, 0.01, 0.005);
        shimmered = [
            saturated[0] + (pitchShifted[0] * shimmer.clip(0, 1.0)),
            saturated[1] + (pitchShifted[1] * shimmer.clip(0, 1.0))
        ];

        // ── エンベロープ: attack 4秒 / release 8秒 ──────────────────
        env       = EnvGen.ar(Env.adsr(atk, 0.3, 0.88, 8.0), gate, doneAction: 2);
        shimmered = shimmered * env;

        // ── ~droneBus: Granular 用ウェット素材として書き出す ─────────
        Out.ar(~droneBus, shimmered);

        // ── FreeVerb2: 最終空間演出 ──────────────────────────────────
        // room 0.0→0.45, room 1.0→0.92 にマップ（広いレンジで効果が出る）
        sig = FreeVerb2.ar(
            shimmered[0], shimmered[1],
            mix:  room.linlin(0.0, 1.0, 0.45, 0.92),
            room: room.linlin(0.0, 1.0, 0.60, 0.95),
            damp: room.linlin(0.0, 1.0, 0.55, 0.12)
        );

        // ~effectBus にも送って Granular と合流させる
        Out.ar(~effectBus, sig * 0.8);

        Out.ar(0, sig * amp);
    }).add;

    s.sync;
    "SynthDef定義完了: \\matoma_drone (v3 自己組織化フィードバックネットワーク型)".postln;

    // ── Drone グローバル変数 ─────────────────────────────────────────
    ~currentDrone = nil;

    // OSCdef: Drone 開始
    OSCdef(\matoma_drone_start, { |msg|
        {
            if (~currentDrone.notNil) {
                ~currentDrone.set(\gate, 0);  // 既存をフェードアウト
            };
            ~currentDrone = Synth(\matoma_drone, addAction: \addToHead);
            "ドローン開始 (v2 Klank)".postln;
        }.defer;
    }, '/matoma/drone/start', nil, 57200);

    // OSCdef: Drone 停止
    // gate=0 → Env.adsr release（8秒フェードアウト）が起動する
    // Ndef.stop() は使わない（機能しない問題の回避）
    OSCdef(\matoma_drone_stop, { |msg|
        {
            if (~currentDrone.notNil) {
                ~currentDrone.set(\gate, 0);
                ~currentDrone = nil;
                "ドローン停止（8秒フェードアウト）".postln;
            };
        }.defer;
    }, '/matoma/drone/stop', nil, 57200);

    // OSCdef: Drone パラメーター更新
    // Python からの範囲は 0.0〜1.0 を前提として SC 側でスケールする
    // 例: freq は 0〜1 → 20〜300 Hz にマップ
    OSCdef(\matoma_drone_param, { |msg|
        var param = msg[1].asSymbol;
        var value = msg[2].asFloat;
        {
            if (~currentDrone.notNil) {
                switch(param)
                { \freq_norm } {
                    // 0〜1 → 20〜300Hz（超低域〜中低域）
                    var hz = value.linexp(0.0, 1.0, 20.0, 300.0);
                    ~currentDrone.set(\freq, hz);
                    "ドローン freq: % → % Hz".format(value.round(0.01), hz.round(0.1)).postln;
                }
                {
                    // その他（feedback_amt, shimmer, room, amp 等）はそのまま渡す
                    ~currentDrone.set(param, value);
                    "ドローン param: % = %".format(param, value.round(0.001)).postln;
                };
            };
        }.defer;
    }, '/matoma/drone/param', nil, 57200);

    // ══════════════════════════════════════════════════════════════
    // ■ STEP 3: SYNTH FM — 2オペレーター + 自己フィードバック FM
    //
    //   chaos パラメーターが高いほど倍音が豊かで荒々しい音に。
    // ══════════════════════════════════════════════════════════════
    SynthDef(\matoma_basic, {
        arg freq = 220, cutoff = 1200, amp = 0.6, chaos = 0.4;

        var modIndex, mod1Freq, mod2Freq, mod1Sig, mod2Sig;
        var fbL, fbR, noiseL, noiseR, cfNoise;
        var sigL, sigR, cf;

        modIndex = chaos * 8 * (1 + LFNoise2.kr(0.04).range(-0.2, 0.3));

        mod1Freq = freq * LFNoise2.kr(0.06).range(1.98, 2.02);
        mod1Sig  = SinOsc.ar(mod1Freq, 0, modIndex * freq);

        mod2Freq = freq * LFNoise2.kr(0.05).range(1.3, 1.7);
        mod2Sig  = SinOsc.ar(mod2Freq, 0, modIndex * freq * 0.5);

        fbL = SinOscFB.ar(
            freq + mod1Sig + mod2Sig * 0.3 + LFNoise2.kr(0.05, freq * 0.003),
            chaos * 0.7);
        fbL = fbL + SinOscFB.ar(freq * 1.5 + mod1Sig * 0.4, chaos * 0.4) * 0.3;

        fbR = SinOscFB.ar(
            freq + mod1Sig * 1.05 + mod2Sig * 0.4 + LFNoise2.kr(0.08, freq * 0.003),
            chaos * 0.65);
        fbR = fbR + SinOscFB.ar(freq * 1.5 + mod1Sig * 0.45, chaos * 0.45) * 0.3;

        cfNoise = freq * LFNoise2.kr(0.08).range(2.0, 5.0);
        noiseL  = BPF.ar(WhiteNoise.ar, cfNoise,        0.3) * chaos * 0.12;
        noiseR  = BPF.ar(WhiteNoise.ar, cfNoise * 1.02, 0.3) * chaos * 0.12;

        sigL = fbL + noiseL;
        sigR = fbR + noiseR;

        cf   = (cutoff * LFNoise2.kr(0.07).range(0.8, 1.2)).clip(80, 18000);
        sigL = RLPF.ar(sigL, cf,        0.5);
        sigR = RLPF.ar(sigR, cf * 0.97, 0.5);

        sigL = LeakDC.ar((sigL * 1.4).softclip);
        sigR = LeakDC.ar((sigR * 1.4).softclip);

        Out.ar(0, FreeVerb2.ar(sigL, sigR, mix: 0.45, room: 0.8, damp: 0.35) * amp);
    }).add;

    s.sync;
    "SynthDef定義完了: \\matoma_basic (FM)".postln;

    ~currentSynth = nil;

    OSCdef(\matoma_start, { |msg|
        { ~currentSynth = Synth(\matoma_basic); "シンセ開始".postln; }.defer;
    }, '/matoma/start', nil, 57200);

    OSCdef(\matoma_stop, { |msg|
        {
            if (~currentSynth.notNil) { ~currentSynth.free; ~currentSynth = nil; };
            "シンセ停止".postln;
        }.defer;
    }, '/matoma/stop', nil, 57200);

    OSCdef(\matoma_param, { |msg|
        var param = msg[1].asSymbol;
        var value = msg[2].asFloat;
        { if (~currentSynth.notNil) { ~currentSynth.set(param, value); }; }.defer;
    }, '/matoma/param', nil, 57200);

    // ══════════════════════════════════════════════════════════════
    // ■ STEP 4: GRANULAR — Drone素材粒分解型
    //
    //   ~droneBus の信号をリングバッファに録音し続け、
    //   GrainBuf でリアルタイムに粒に分解する。
    //   録音器は起動時から常時動く。
    //   spray: 0=規則的（Impulse）、1=ランダム（Dust）
    // ══════════════════════════════════════════════════════════════

    // グラニュラー用リングバッファ（Drone の 2秒分、ステレオ）
    ~granularRingBuf = Buffer.alloc(s, (s.sampleRate * 2.0).round.asInteger, 2);
    s.sync;
    "グラニュラー リングバッファ確保完了 (bufnum: %)".format(~granularRingBuf.bufnum).postln;

    // リングバッファ録音器
    SynthDef(\matoma_granular_recorder, {
        arg inBus, buf;
        var sig = In.ar(inBus, 2);
        // loop:1 でバッファ末尾に達したら先頭から上書き（永遠に録音）
        RecordBuf.ar(sig, buf, loop: 1, trigger: 1, doneAction: 0);
    }).add;

    // グラニュラー合成器（norns silo_grain パターン）
    SynthDef(\matoma_granular, {
        arg buf       = 0,
            density   = 20,
            spray     = 0.3,   // 0=Impulse(規則的) 1=Dust(ランダム)
            pos       = 0.5,
            size      = 0.12,
            jitter    = 0.08,
            room      = 0.5,
            amp       = 0.5,
            gate      = 1,
            outBus    = 0;

        var trig_regular, trig_random, trig, grainPos;
        var sig, wet, env;

        // spray: SelectX.kr でクロスフェード（norns silo_grain パターン）
        trig_regular = Impulse.kr(density);
        trig_random  = Dust.kr(density);
        trig         = SelectX.kr(spray, [trig_regular, trig_random]);

        // pos を中心に LFNoise0 で揺らす（jitter）
        grainPos = (pos + LFNoise0.kr(6).bipolar(jitter)).clip(0.0, 1.0);

        sig = GrainBuf.ar(
            numChannels: 2,
            trigger:     trig,
            dur:         size,
            sndbuf:      buf,
            rate:        1.0,
            pos:         grainPos,
            interp:      2,
            pan:         LFNoise1.kr(3).range(-0.7, 0.7),
            envbufnum:   -1
        );

        // 個別リバーブ（中程度：粒の形が残る程度）
        wet = FreeVerb2.ar(
            sig[0], sig[1],
            mix:  room.linlin(0.0, 1.0, 0.25, 0.75),
            room: room.linlin(0.0, 1.0, 0.45, 0.85),
            damp: room.linlin(0.0, 1.0, 0.6,  0.2)
        );

        env = EnvGen.ar(Env.adsr(0.5, 0.0, 1.0, 2.0), gate, doneAction: 2);

        Out.ar(outBus, wet * env * amp);
    }).add;

    s.sync;
    "SynthDef定義完了: \\matoma_granular_recorder, \\matoma_granular".postln;

    ~currentGranular  = nil;
    ~granularRecorder = nil;

    // ── 録音器の起動内部関数 ─────────────────────────────────────────
    ~startGranularRecorder = {
        if (~granularRecorder.notNil) { ~granularRecorder.free; };
        ~granularRecorder = Synth(\matoma_granular_recorder, [
            \inBus, ~droneBus,
            \buf,   ~granularRingBuf.bufnum
        ], addAction: \addToHead);
        "グラニュラー録音器: 起動 (droneBus: %, ringBuf: %)".format(
            ~droneBus, ~granularRingBuf.bufnum).postln;
    };

    // OSCdef: Granular 開始
    OSCdef(\matoma_granular_start, { |msg|
        {
            if (~currentGranular.notNil) { ~currentGranular.set(\gate, 0); };
            ~currentGranular = Synth(\matoma_granular, [
                \buf,    ~granularRingBuf.bufnum,
                \outBus, ~effectBus.index
            ], addAction: \addToTail);
            "グラニュラー開始 (ringBuf: %, outBus: %)".format(
                ~granularRingBuf.bufnum, ~effectBus.index).postln;
        }.defer;
    }, '/matoma/granular/start', nil, 57200);

    // OSCdef: Granular 停止
    OSCdef(\matoma_granular_stop, { |msg|
        {
            if (~currentGranular.notNil) {
                ~currentGranular.set(\gate, 0);
                ~currentGranular = nil;
                "グラニュラー停止（2秒フェードアウト）".postln;
            };
        }.defer;
    }, '/matoma/granular/stop', nil, 57200);

    // OSCdef: Granular パラメーター
    // density, spray, pos, size, room, amp を動的変更可能
    OSCdef(\matoma_granular_param, { |msg|
        var param = msg[1].asSymbol;
        var value = msg[2].asFloat;
        {
            if (~currentGranular.notNil) {
                ~currentGranular.set(param, value);
                "グラニュラー param: % = %".format(param, value.round(0.001)).postln;
            };
        }.defer;
    }, '/matoma/granular/param', nil, 57200);

    // ══════════════════════════════════════════════════════════════
    // ■ STEP 5: SPECTRAL — FFT スペクトル処理 + Decimator
    // ══════════════════════════════════════════════════════════════
    SynthDef(\matoma_spectral, {
        arg freq  = 200,
            smear = 0.6,
            bits  = 8,
            rate  = 0.5,
            chaos = 0.5,
            amp   = 0.5,
            gate  = 1;

        var fftBuf = LocalBuf(1024);
        var src, chain, sig;

        src = Mix([
            BPF.ar(GrayNoise.ar, freq * LFNoise2.kr(0.05 + chaos * 0.1).range(0.9, 1.1), 0.1),
            BPF.ar(GrayNoise.ar, freq * LFNoise2.kr(0.07 + chaos * 0.15).range(1.5, 2.5), 0.08),
            BPF.ar(GrayNoise.ar, freq * LFNoise2.kr(0.03 + chaos * 0.12).range(3.0, 5.0), 0.06),
            SinOscFB.ar(freq * LFNoise2.kr(0.04).range(0.99, 1.01), chaos * 0.5) * 0.15,
        ]) * 0.6;

        chain = FFT(fftBuf, src);
        chain = PV_MagSmear(chain, (smear * 8).round.asInteger.max(0));
        chain = PV_RandComb(chain, 1.0 - (chaos * 0.4).clip(0, 0.85), Impulse.kr(0.5));
        sig   = IFFT(chain);

        sig = Decimator.ar(
            sig,
            s.sampleRate * rate.clip(0.05, 1.0),
            bits.clip(4, 16).round.asInteger
        );
        sig = LeakDC.ar(sig.softclip);
        sig = FreeVerb.ar(sig, mix: 0.3, room: 0.5, damp: 0.5);
        sig = sig * Linen.kr(gate, 0.3, 1.0, 1.5, 2) * amp;
        Out.ar(0, sig ! 2);
    }).add;

    s.sync;
    "SynthDef定義完了: \\matoma_spectral".postln;

    ~currentSpectral = nil;

    OSCdef(\matoma_spectral_start, { |msg|
        {
            if (~currentSpectral.notNil) { ~currentSpectral.set(\gate, 0); };
            ~currentSpectral = Synth(\matoma_spectral);
            "スペクトルシンセ開始".postln;
        }.defer;
    }, '/matoma/spectral/start', nil, 57200);

    OSCdef(\matoma_spectral_stop, { |msg|
        {
            if (~currentSpectral.notNil) {
                ~currentSpectral.set(\gate, 0);
                ~currentSpectral = nil;
            };
            "スペクトルシンセ停止".postln;
        }.defer;
    }, '/matoma/spectral/stop', nil, 57200);

    OSCdef(\matoma_spectral_param, { |msg|
        var param = msg[1].asSymbol;
        var value = msg[2].asFloat;
        { if (~currentSpectral.notNil) { ~currentSpectral.set(param, value); }; }.defer;
    }, '/matoma/spectral/param', nil, 57200);

    // ══════════════════════════════════════════════════════════════
    // ■ STEP 6: EFFECTS — グローバルエフェクト層
    //
    //   ~effectBus から読んでエフェクトをかけ Out(0) へ届ける。
    //   パススルーは常時動く（エフェクトがなくても音が出る）。
    // ══════════════════════════════════════════════════════════════

    // Global Delay
    SynthDef(\matoma_delay, {
        arg inBus,
            out      = 0,
            time     = 0.25,
            feedback = 0.4,
            mix      = 0.35;

        var sig, delayed, fb_sig, wet;

        sig    = In.ar(inBus, 2);
        fb_sig = LocalIn.ar(2);

        delayed = [
            CombC.ar(sig[0] + (fb_sig[0] * feedback), 2.0, time,        time * 4.0),
            CombC.ar(sig[1] + (fb_sig[1] * feedback), 2.0, time * 1.03, time * 4.0)
        ];

        LocalOut.ar(delayed);

        wet = XFade2.ar(sig, delayed, mix * 2 - 1);
        Out.ar(out, wet);
    }).add;

    s.sync;
    "エフェクト定義完了: \\matoma_delay".postln;

    // Spectral Freeze + Blur
    SynthDef(\matoma_spectral_freeze, {
        arg inBus,
            out    = 0,
            freeze = 0.0,
            blur   = 0;

        var sig, chain, frozen;
        var fftBuf = LocalBuf(2048);

        sig   = In.ar(inBus, 2);
        chain = FFT(fftBuf, sig[0] + sig[1] * 0.5);
        chain = PV_MagFreeze(chain, freeze);
        chain = PV_MagSmear(chain, blur.clip(0, 32).round.asInteger);
        frozen = IFFT(chain);

        Out.ar(out, XFade2.ar(sig, (frozen ! 2), freeze * 2 - 1));
    }).add;

    s.sync;
    "エフェクト定義完了: \\matoma_spectral_freeze".postln;

    // Wavefolder
    SynthDef(\matoma_wavefolder, {
        arg inBus,
            out   = 0,
            drive = 0.0,
            mix   = 0.0;

        var sig, folded;

        sig    = In.ar(inBus, 2);
        folded = (sig * drive.linlin(0.0, 1.0, 1.0, 6.0)).fold(-1, 1);
        folded = LeakDC.ar(folded);

        Out.ar(out, XFade2.ar(sig, folded, mix * 2 - 1));
    }).add;

    s.sync;
    "エフェクト定義完了: \\matoma_wavefolder".postln;

    // Feedback Loop
    // amount の上限を 0.85 から実質 0.9 近くまで使えるよう clip を緩める
    SynthDef(\matoma_feedback_loop, {
        arg inBus,
            out    = 0,
            amount = 0.0,
            rate   = 0.5;

        var sig, fb, fed;

        sig = In.ar(inBus, 2);
        fb  = LocalIn.ar(2);

        // amount が大きいほど発散に近づくので Limiter で保護
        fed = AllpassC.ar(
            sig + (fb * amount.clip(0, 0.9)),
            2.0,
            [rate, rate * 1.07],
            rate * 3.0
        );

        LocalOut.ar(fed);
        Out.ar(out, Limiter.ar(sig + (fed * amount), 0.95));
    }).add;

    s.sync;
    "エフェクト定義完了: \\matoma_feedback_loop".postln;

    // Effect パススルー（~effectBus → ハード出力）
    // エフェクトが何も起動していなくても ~effectBus の音が聞こえるようにする
    SynthDef(\matoma_effect_out, {
        arg inBus, out = 0, amp = 1.0;
        var sig = In.ar(inBus, 2);
        Out.ar(out, sig * amp);
    }).add;

    s.sync;

    // エフェクトグローバル変数
    ~currentDelay       = nil;
    ~currentSpectralFrz = nil;
    ~currentWavefolder  = nil;
    ~currentFeedback    = nil;

    // パススルーを起動（常駐・必須）
    // これがないと ~effectBus の信号が Out(0) に届かない
    ~currentEffectOut = Synth(\matoma_effect_out, [
        \inBus, ~effectBus,
        \out, 0
    ], addAction: \addToTail);
    "エフェクトパススルー起動: ~effectBus → Out(0)".postln;

    // Effect OSCdef: Delay
    OSCdef(\matoma_delay_start, { |msg|
        {
            if (~currentDelay.notNil) { ~currentDelay.free; };
            ~currentDelay = Synth(\matoma_delay, [\inBus, ~effectBus, \out, 0],
                addAction: \addToTail);
            "ディレイ開始".postln;
        }.defer;
    }, '/matoma/effect/delay/start', nil, 57200);

    OSCdef(\matoma_delay_stop, { |msg|
        {
            if (~currentDelay.notNil) { ~currentDelay.free; ~currentDelay = nil; };
            "ディレイ停止".postln;
        }.defer;
    }, '/matoma/effect/delay/stop', nil, 57200);

    OSCdef(\matoma_delay_param, { |msg|
        var param = msg[1].asSymbol; var value = msg[2].asFloat;
        { if (~currentDelay.notNil) { ~currentDelay.set(param, value); }; }.defer;
    }, '/matoma/effect/delay/param', nil, 57200);

    // Effect OSCdef: Spectral Freeze
    OSCdef(\matoma_spectral_freeze_start, { |msg|
        {
            if (~currentSpectralFrz.notNil) { ~currentSpectralFrz.free; };
            ~currentSpectralFrz = Synth(\matoma_spectral_freeze,
                [\inBus, ~effectBus, \out, 0], addAction: \addToTail);
            "スペクトラルフリーズ開始".postln;
        }.defer;
    }, '/matoma/effect/spectral/start', nil, 57200);

    OSCdef(\matoma_spectral_freeze_stop, { |msg|
        {
            if (~currentSpectralFrz.notNil) {
                ~currentSpectralFrz.free; ~currentSpectralFrz = nil;
            };
            "スペクトラルフリーズ停止".postln;
        }.defer;
    }, '/matoma/effect/spectral/stop', nil, 57200);

    OSCdef(\matoma_spectral_freeze_param, { |msg|
        var param = msg[1].asSymbol; var value = msg[2].asFloat;
        { if (~currentSpectralFrz.notNil) { ~currentSpectralFrz.set(param, value); }; }.defer;
    }, '/matoma/effect/spectral/param', nil, 57200);

    // Effect OSCdef: Wavefolder
    OSCdef(\matoma_wavefolder_start, { |msg|
        {
            if (~currentWavefolder.notNil) { ~currentWavefolder.free; };
            ~currentWavefolder = Synth(\matoma_wavefolder,
                [\inBus, ~effectBus, \out, 0], addAction: \addToTail);
            "ウェーブフォルダー開始".postln;
        }.defer;
    }, '/matoma/effect/wavefolder/start', nil, 57200);

    OSCdef(\matoma_wavefolder_stop, { |msg|
        {
            if (~currentWavefolder.notNil) { ~currentWavefolder.free; ~currentWavefolder = nil; };
            "ウェーブフォルダー停止".postln;
        }.defer;
    }, '/matoma/effect/wavefolder/stop', nil, 57200);

    OSCdef(\matoma_wavefolder_param, { |msg|
        var param = msg[1].asSymbol; var value = msg[2].asFloat;
        { if (~currentWavefolder.notNil) { ~currentWavefolder.set(param, value); }; }.defer;
    }, '/matoma/effect/wavefolder/param', nil, 57200);

    // Effect OSCdef: Feedback Loop
    OSCdef(\matoma_feedback_loop_start, { |msg|
        {
            if (~currentFeedback.notNil) { ~currentFeedback.free; };
            ~currentFeedback = Synth(\matoma_feedback_loop,
                [\inBus, ~effectBus, \out, 0], addAction: \addToTail);
            "フィードバックループ開始".postln;
        }.defer;
    }, '/matoma/effect/feedback/start', nil, 57200);

    OSCdef(\matoma_feedback_loop_stop, { |msg|
        {
            if (~currentFeedback.notNil) { ~currentFeedback.free; ~currentFeedback = nil; };
            "フィードバックループ停止".postln;
        }.defer;
    }, '/matoma/effect/feedback/stop', nil, 57200);

    OSCdef(\matoma_feedback_loop_param, { |msg|
        var param = msg[1].asSymbol; var value = msg[2].asFloat;
        { if (~currentFeedback.notNil) { ~currentFeedback.set(param, value); }; }.defer;
    }, '/matoma/effect/feedback/param', nil, 57200);

    // ══════════════════════════════════════════════════════════════
    // ■ STEP 7: RHYTHMIC — Turing Machine + 5音源
    //
    //   確率的シフトレジスタが「どの音源を・いつ・どんな音程で」を決める。
    //   起動時に prob=0.2 の控えめな状態で自動スタートする。
    // ══════════════════════════════════════════════════════════════

    // リズム用バッファ（打撃感のある短いサイン波バースト）
    ~rhythmicBuf = Buffer.alloc(s, (s.sampleRate * 0.5).round.asInteger, 1);
    s.sync;
    ~rhythmicBuf.sine1(
        Array.fill(16, {|i| if(i < 3, (1.0/(i+1)), 0.0) }),
        asWavetable: false,
        normalize: true
    );
    s.sync;
    "リズム用バッファ生成完了 (bufnum: %)".format(~rhythmicBuf.bufnum).postln;

    // 音源 1: Granular 打撃音
    SynthDef(\matoma_rhythmic_grain, {
        arg buf = 0, freq = 440, amp = 0.5,
            pos = 0.1, size = 0.05, spray = 0.2, outBus = 0;

        var trig, sig, env;

        trig = SelectX.kr(spray, [
            Impulse.kr(freq / 440 * 8),
            Dust.kr(freq / 440 * 8)
        ]);

        sig = GrainBuf.ar(2, trig, size, buf,
            freq / 440.0,
            pos + LFNoise0.kr(4).bipolar(0.05),
            2, LFNoise1.kr(2).range(-0.5, 0.5), -1);

        sig = FreeVerb2.ar(sig[0], sig[1], mix: 0.2, room: 0.35, damp: 0.8);
        env = EnvGen.ar(Env.perc(0.001, 0.4), doneAction: 2);
        Out.ar(outBus, [sig[0], sig[1]] * env * amp);
    }).add;

    // 音源 2: Klank 金属共鳴（Alva Noto 的なガラス的グリッド音）
    SynthDef(\matoma_rhythmic_klank, {
        arg freq = 440, amp = 0.4, decay = 1.2, outBus = 0;

        var imp, sig, sig2, env;

        imp = Impulse.ar(0) * amp;

        sig = Klank.ar(`[
            [freq, freq * 2.756, freq * 5.404, freq * 8.933, freq * 13.34],
            [1.0, 0.5, 0.3, 0.15, 0.07],
            [decay, decay * 0.7, decay * 0.5, decay * 0.35, decay * 0.2]
        ], imp);

        sig2 = Klank.ar(`[
            [freq * 1.001, freq * 2.758, freq * 5.407],
            [0.9, 0.45, 0.27],
            [decay * 1.05, decay * 0.72, decay * 0.52]
        ], imp);

        sig = FreeVerb2.ar(sig, sig2, mix: 0.25, room: 0.4, damp: 0.7);
        env = EnvGen.ar(Env.perc(0.001, decay * 1.5), doneAction: 2);
        Out.ar(outBus, [sig[0], sig[1]] * env);
    }).add;

    // 音源 3: FM Percussion（Autechre 的な予測不能な金属打撃音）
    SynthDef(\matoma_rhythmic_fm, {
        arg freq = 220, amp = 0.45,
            iScale = 6.0, atk = 0.003, rel = 0.6, mRatio = 2.1, outBus = 0;

        var iEnv, env, mod, car, sig;

        iEnv = EnvGen.kr(Env([5.0, 5.0 * iScale, 0.3], [atk, rel], [-2, -4]));
        env  = EnvGen.ar(Env.perc(atk, rel, curve: [-2, -6]), doneAction: 2);

        mod = SinOsc.ar(freq * mRatio, mul: freq * mRatio * iEnv);
        car = SinOsc.ar(freq + mod) * env * amp;
        car = car + DelayC.ar(car, 0.03, LFNoise1.kr(Rand(5, 10), 0.008, 0.012));

        sig = FreeVerb2.ar(car, car * 0.95, mix: 0.2, room: 0.3, damp: 0.75);
        Out.ar(outBus, [sig[0], sig[1]]);
    }).add;

    // 音源 4: Spring + Ringz（有機的・金属的共鳴）
    SynthDef(\matoma_rhythmic_spring, {
        arg freq = 330, amp = 0.35,
            spring_const = 60.0, damp = 0.3, outBus = 0;

        var exc, sig, env;

        exc = Impulse.ar(0) + (WhiteNoise.ar(0.04) * EnvGen.ar(Env.perc(0.001, 0.04)));
        sig = Spring.ar(exc, spring_const, damp);
        sig = sig + Ringz.ar(exc, freq, 1.2, 0.5);
        sig = RLPF.ar(sig, freq * 4.5, 0.4);
        sig = FreeVerb2.ar(sig, DelayN.ar(sig, 0.03, 0.013),
            mix: 0.35, room: 0.55, damp: 0.5);

        env = EnvGen.ar(Env.perc(0.001, 2.0), doneAction: 2);
        Out.ar(outBus, [sig[0], sig[1]] * env * amp);
    }).add;

    // 音源 5: Chaos（LFNoise2 + SinOsc + Decimator）
    SynthDef(\matoma_rhythmic_chaos, {
        arg freq = 150, amp = 0.3, chaos = 0.7, outBus = 0;

        var src, sig, env;

        src = LFNoise2.ar(freq * chaos.linlin(0, 1, 1, 12))
            * SinOsc.ar(freq * LFNoise1.kr(chaos * 2).range(0.5, 2.0))
            * chaos.linlin(0, 1, 0.5, 1.5);

        sig = HPF.ar(src, 80);
        sig = Decimator.ar(sig,
            s.sampleRate * chaos.linlin(0, 1, 1.0, 0.25),
            chaos.linlin(0, 1, 16, 8).round.asInteger);
        sig = sig.softclip;
        sig = FreeVerb2.ar(sig, sig * 0.9, mix: 0.15, room: 0.3, damp: 0.85);

        env = EnvGen.ar(Env.perc(0.002, 0.5), doneAction: 2);
        Out.ar(outBus, [sig[0], sig[1]] * env * amp);
    }).add;

    s.sync;
    "SynthDef定義完了: リズム音源 5種".postln;

    // Turing Machine の状態
    ~turingRegister = Array.fill(16, { [0, 1].choose });
    ~turingStep     = 0;
    ~turingProb     = 0.2;    // 起動時は控えめな確率
    ~turingBpm      = 120.0;
    ~turingAmp      = 0.5;
    ~turingRoutine  = nil;

    ~rhythmicSynths = [\matoma_rhythmic_grain, \matoma_rhythmic_klank,
                       \matoma_rhythmic_fm, \matoma_rhythmic_spring,
                       \matoma_rhythmic_chaos];
    ~rhythmicScale  = [0, 3, 5, 7, 10, 12, 15, 17];  // マイナーペンタトニック拡張

    // Turing Machine シフトレジスタ更新関数
    ~turingAdvance = {
        var bit0   = ~turingRegister[0];
        var newBit = if (1.0.rand < ~turingProb) { 1 - bit0 } { bit0 };
        ~turingRegister = ~turingRegister[1..] ++ [newBit];
        ~turingStep = (~turingStep + 1) % 16;
        (
            synthIdx: (~turingRegister[0] * 2 + ~turingRegister[1]) % ~rhythmicSynths.size,
            scaleIdx: (~turingRegister[2] * 4 + ~turingRegister[3] * 2 +
                       ~turingRegister[4]) % ~rhythmicScale.size
        )
    };

    // Turing Machine のメインループを起動する内部関数
    ~startTuringMachine = {
        if (~turingRoutine.notNil) { ~turingRoutine.stop; };
        ~turingRoutine = Routine({
            loop {
                var result   = ~turingAdvance.();
                var synthSym = ~rhythmicSynths[result[\synthIdx]];
                var scaleDeg = ~rhythmicScale[result[\scaleIdx]];
                var freq     = 220.0 * (2 ** (scaleDeg / 12.0));
                var stepDur  = 60.0 / ~turingBpm;

                if (~turingRegister[0] == 1) {
                    var buf = if (synthSym == \matoma_rhythmic_grain) {
                        ~rhythmicBuf.bufnum } { 0 };
                    Synth(synthSym, [
                        \freq, freq, \amp, ~turingAmp * rrand(0.5, 1.0),
                        \buf, buf, \outBus, ~effectBus.index
                    ], addAction: \addToTail);
                };

                stepDur.wait;
            }
        }).play;
        "Turing Machine 開始 (prob: %, bpm: %)".format(
            ~turingProb.round(0.01), ~turingBpm.round(0.1)).postln;
    };

    // OSCdef: 特定音源を即叩く
    OSCdef(\matoma_rhythmic_trigger, { |msg|
        var synthName = msg[1].asSymbol;
        var freq = msg[2].asFloat;
        var amp  = msg[3].asFloat;
        {
            var buf = if (synthName == \matoma_rhythmic_grain) {
                ~rhythmicBuf.bufnum } { 0 };
            Synth(synthName, [\freq, freq, \amp, amp, \buf, buf,
                \outBus, ~effectBus.index], addAction: \addToTail);
            "リズムトリガー: % freq:% amp:%".format(
                synthName, freq.round(0.1), amp.round(0.01)).postln;
        }.defer;
    }, '/matoma/rhythmic/trigger', nil, 57200);

    // OSCdef: Turing Machine パラメーター
    OSCdef(\matoma_rhythmic_param, { |msg|
        var key = msg[1].asSymbol; var value = msg[2].asFloat;
        {
            switch(key)
            { \prob } { ~turingProb = value.clip(0.0, 1.0); }
            { \bpm  } { ~turingBpm  = value.clip(30, 200); }
            { \amp  } { ~turingAmp  = value.clip(0.0, 1.0); };
            "リズム param: % = %".format(key, value.round(0.001)).postln;
        }.defer;
    }, '/matoma/rhythmic/param', nil, 57200);

    // OSCdef: Turing Machine 開始
    OSCdef(\matoma_rhythmic_start, { |msg|
        { ~startTuringMachine.(); }.defer;
    }, '/matoma/rhythmic/start', nil, 57200);

    // OSCdef: Turing Machine 停止
    OSCdef(\matoma_rhythmic_stop, { |msg|
        {
            if (~turingRoutine.notNil) {
                ~turingRoutine.stop; ~turingRoutine = nil;
            };
            "Turing Machine 停止".postln;
        }.defer;
    }, '/matoma/rhythmic/stop', nil, 57200);

    // OSCdef: リズムバッファ ロード
    OSCdef(\matoma_rhythmic_load, { |msg|
        var path = msg[1].asString;
        {
            if (~rhythmicBuf.notNil) { ~rhythmicBuf.free; };
            ~rhythmicBuf = Buffer.read(s, path, action: { |buf|
                "リズムバッファ ロード: %".format(path).postln;
            });
        }.defer;
    }, '/matoma/rhythmic/load', nil, 57200);

    // ══════════════════════════════════════════════════════════════
    // ■ STEP 8: PERCUSSION — 16ステップパーカッションシーケンサー
    //
    //   percussion.scd をロードして SynthDef と OSCdef を登録する。
    //   4音源: metal(Klank) / fm(iScale) / noise(HPF) / spring(Spring+Ringz)
    //   16ステップ × 4トラックの Routine ベースシーケンサー。
    //   起動後はオフ状態（OSC /matoma/perc/start で手動スタート）。
    // ══════════════════════════════════════════════════════════════
    "パーカッションロード先: %".format(~matomaScDir).postln;
    load(~matomaScDir +/+ "percussion.scd");
    s.sync;
    "パーカッションシーケンサー ロード完了".postln;

    // ══════════════════════════════════════════════════════════════
    // ■ STEP 9: 常駐シンセ・自動スタート
    //
    //   【起動順序】
    //     1. Effect パススルー（既に起動済み）
    //     2. Granular Recorder（~droneBus → リングバッファ）
    //     3. Turing Machine（prob=0.2 で控えめに開始）
    //     4. Drone（起動直後から音が出る）
    // ══════════════════════════════════════════════════════════════

    // 2. Granular Recorder 起動（常時 ~droneBus を録音）
    // Drone が鳴っていれば素材が録音される。鳴っていなければ無音が録音（害なし）。
    { ~startGranularRecorder.(); }.defer;

    // 2b. Granular シンセ自動スタート（Drone素材をすぐ粒に変換してテクスチャを出す）
    // Recorder が録音を開始してから 2秒後に起動する。
    // この1行がないと GrainBuf は動くが音が一切出ない。
    {
        2.0.wait;
        ~currentGranular = Synth(\matoma_granular, [
            \buf,     ~granularRingBuf.bufnum,
            \outBus,  ~effectBus.index,
            \density, 12,
            \spray,   0.4,
            \amp,     0.4
        ], addAction: \addToTail);
        "グラニュラー自動スタート (density:12 spray:0.4)".postln;
    }.fork;

    // 3. Turing Machine を自動スタート（prob=0.2 の控えめな確率）
    // 音が出るのは ~effectBus 経由なので Effect パススルーが必須
    { 0.5.wait; ~startTuringMachine.(); }.fork;

    // 4. Drone を自動スタート（起動直後から音が出る）
    // Granular Recorder の起動後に開始することで素材がすぐ録音される
    {
        1.0.wait;  // Granular Recorder と同期を確実にする
        ~currentDrone = Synth(\matoma_drone, addAction: \addToHead);
        "ドローン自動スタート (v3 自己組織化FB)".postln;
    }.fork;

    // ── テスト音 ────────────────────────────────────────────────────
    // 動作確認用: 880Hzのビープを0.3秒鳴らしてPythonへ通知する
    OSCdef(\matoma_test_tone, { |msg|
        {
            { SinOsc.ar(880, 0, 0.25) *
                EnvGen.kr(Env.perc(0.01, 1.5), doneAction: 2) }.play;
            "テスト音再生 (880Hz)".postln;
            NetAddr("127.0.0.1", 9000).sendMsg('/matoma/test_tone/ok');
        }.defer;
    }, '/matoma/test_tone', nil, 57200);

    // ── 全停止 ─────────────────────────────────────────────────────
    // s.freeAll で全シンセを解放する。ドローン・グラニュラー・リズム含む。
    OSCdef(\matoma_all_stop, { |msg|
        {
            s.freeAll;
            ~currentDrone = nil;
            ~currentGranular = nil;
            ~turingRoutine !? { ~turingRoutine.stop; ~turingRoutine = nil; };
            ~percRoutine   !? { ~percRoutine.stop;  ~percRoutine  = nil; };
            "【全停止】全シンセを解放しました。".postln;
        }.defer;
    }, '/matoma/all/stop', nil, 57200);

    // ── 再セットアップ ──────────────────────────────────────────────
    // 全停止後に基本レイヤー（Effect/Granular/Drone）を自動で再起動する。
    OSCdef(\matoma_all_restart, { |msg|
        {
            // 1. 全シンセ解放
            s.freeAll;
            ~currentDrone = nil;
            ~currentGranular = nil;
            ~turingRoutine !? { ~turingRoutine.stop; ~turingRoutine = nil; };
            ~percRoutine   !? { ~percRoutine.stop;  ~percRoutine  = nil; };
            "【再セットアップ】リセット中...".postln;

            // 2. 少し待って再起動
            0.5.wait;
            // inBus を必ず渡す（省略するとバス0のフィードバックループが発生）
            ~currentEffectOut = Synth(\matoma_effect_out,
                [\inBus, ~effectBus, \out, 0], addAction: \addToTail);
            ~startGranularRecorder.();
            0.5.wait;
            // atk=0.5 で素早くフェードイン（通常起動の4秒より短く）
            ~currentDrone = Synth(\matoma_drone, [\atk, 0.5], addAction: \addToHead);
            "【再セットアップ】完了。".postln;
            NetAddr("127.0.0.1", 9000).sendMsg('/matoma/restarted');
        }.fork;
    }, '/matoma/all/restart', nil, 57200);

    // ══════════════════════════════════════════════════════════════
    // 起動完了 → Python ブリッジへ通知
    // ══════════════════════════════════════════════════════════════
    "".postln;
    "MaToMa v3 全モジュール起動完了".postln;
    "  Drone v3 FB     : /matoma/drone/start|stop|param".postln;
    "  Granular        : /matoma/granular/start|stop|param".postln;
    "  Turing Machine  : /matoma/rhythmic/start|stop|trigger|param".postln;
    "  Effects         : /matoma/effect/[delay|spectral|wavefolder|feedback]/start|stop|param".postln;
    "  Percussion      : /matoma/perc/start|stop|step|bpm|filter|amp|clear".postln;
    "".postln;
    "  自動起動済み:".postln;
    "    - Effect パススルー (~effectBus → Out 0)".postln;
    "    - Granular Recorder (~droneBus → リングバッファ)".postln;
    "    - Turing Machine (prob=0.2)".postln;
    "    - Drone v3 自己組織化フィードバックネットワーク".postln;
    "".postln;
    "  Drone パラメーター範囲:".postln;
    "    freq_norm    : 0.0〜1.0 → 20〜300Hz にマップ".postln;
    "    feedback_amt : 0.0〜0.75（0.5超で破壊的フィードバック）".postln;
    "    shimmer      : 0.0〜1.0（浮遊感の強さ）".postln;
    "    room         : 0.0〜1.0（空間の広さ）".postln;

    NetAddr("127.0.0.1", 9000).sendMsg('/matoma/ready');
    ">>> /matoma/ready 送信完了".postln;

    // ── 音声デバイスリストを Python へ送信 ─────────────────────────
    // /matoma/ready の後に遅延させて確実に届けるため 0.5秒待つ
    {
        var pythonAddr = NetAddr("127.0.0.1", 9000);
        var allDevices = ServerOptions.devices ? [];
        var currentDev = s.options.outDevice ? "";
        pythonAddr.sendMsg('/matoma/audio/devices', currentDev, *allDevices);
        "音声デバイスリスト送信: % デバイス / 現在: %".format(
            allDevices.size,
            if (currentDev.isEmpty) { "(デフォルト)" } { currentDev }
        ).postln;
    }.defer(0.5);

    // OSCdef: デバイスリストを要求された時に返す
    OSCdef(\matoma_audio_get_devices, { |msg|
        var pythonAddr = NetAddr("127.0.0.1", 9000);
        var allDevices = ServerOptions.devices ? [];
        var currentDev = s.options.outDevice ? "";
        { pythonAddr.sendMsg('/matoma/audio/devices', currentDev, *allDevices); }.defer;
    }, '/matoma/audio/get_devices', nil, 57200);
});
