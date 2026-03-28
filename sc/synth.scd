/*
MaToMa: 基本シンセ（v2）
===================
複数のこぎり波をデチューンして重ね、LFOで揺らし、ステレオリバーブで空間を作る。
ブラウザのスライダーで freq・cutoff・amp・detune・drift・room をリアルタイム制御する。

パラメーター:
  freq   : 音の高さ（Hz）。220 = ラ（低め）、440 = ラ（標準）
  cutoff : 音の明るさ（Hz）。低い = こもった音、高い = 明るい音
  amp    : 音量（0.0〜1.0）
  detune : 音の厚み（0.0〜1.0）。複数の波をずらして重ねることで倍音と厚みを出す
  drift  : 揺らぎの速さと深さ（0.0〜1.0）。LFOがcutoffを揺らす
  room   : 空間の広さ（0.0〜1.0）。リバーブの量
*/

(
s.waitForBoot({

    SynthDef(\matoma_basic, {
        arg freq = 220, cutoff = 1000, amp = 0.3,
            detune = 0.3, drift = 0.2, room = 0.5;

        var lfoRate, lfoSignal, cutoffMod, detuneHz;
        var sigL, sigR, sig;

        // ── LFO: drift が速度と深度を同時に制御 ─────────────────────
        // drift が大きいほど、cutoffが速く・大きく揺れる（呼吸するような動き）
        lfoRate   = drift.linexp(0.001, 1, 0.05, 0.5);
        lfoSignal = LFNoise1.kr(lfoRate);
        cutoffMod = (cutoff * (1 + lfoSignal * drift)).clip(80, 16000);

        // ── オシレーター: L/R で逆方向にデチューン → 真のステレオ ───
        // 複数のSaw波を微妙にずらして重ねることで倍音と厚みが生まれる。
        // 1オクターブ上の成分（freq*2）を薄く加えて倍音の密度を上げる。
        detuneHz = freq * detune * 0.05;
        sigL = Mix([
            Saw.ar(freq),
            Saw.ar(freq + detuneHz),
            Saw.ar(freq + detuneHz * 0.4),
            Saw.ar(freq * 2 + detuneHz * 0.3) * 0.3,  // 1オクターブ上
        ]) * 0.25;
        sigR = Mix([
            Saw.ar(freq + detuneHz * 0.6),
            Saw.ar(freq - detuneHz),
            Saw.ar(freq - detuneHz * 0.4),
            Saw.ar(freq * 2 - detuneHz * 0.3) * 0.3,
        ]) * 0.25;

        // ── ローパスフィルター（rq=0.4: 中程度のレゾナンス） ─────────
        // L/R で cutoff を微妙にずらして広がりをさらに強調
        sigL = RLPF.ar(sigL, cutoffMod,        0.4);
        sigR = RLPF.ar(sigR, cutoffMod * 0.97, 0.4);

        // ── ステレオリバーブ（FreeVerb2 = 真のステレオ空間） ─────────
        sig = FreeVerb2.ar(sigL, sigR, mix: room, room: room, damp: 0.4);

        Out.ar(0, sig * amp);
    }).add;

    "シンセ定義完了: \\matoma_basic v2".postln;

    ~currentSynth = nil;

    OSCdef(\matoma_start, { |msg|
        {
            if (~currentSynth.notNil) {
                ~currentSynth.free;
            };
            ~currentSynth = Synth(\matoma_basic);
            "音を開始".postln;
        }.defer;
    }, '/matoma/start');

    OSCdef(\matoma_stop, { |msg|
        {
            if (~currentSynth.notNil) {
                ~currentSynth.free;
                ~currentSynth = nil;
                "音を停止".postln;
            };
        }.defer;
    }, '/matoma/stop');

    OSCdef(\matoma_param, { |msg|
        var param = msg[1].asSymbol;
        var value = msg[2].asFloat;
        {
            if (~currentSynth.notNil) {
                ~currentSynth.set(param, value);
                "パラメーター更新: % = %".format(param, value.round(0.01)).postln;
            };
        }.defer;
    }, '/matoma/param');

    "MaToMa シンセ起動完了。".postln;
});
)
