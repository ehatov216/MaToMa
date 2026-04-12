// sc/melody.scd
// MaToMa メロディーシンセ（Phase 1）
// ====================================
// Tidalから /matoma/rhythmic/trigger で呼び出すメロディー専用 SynthDef。
// matoma_rhythmic_* と同じOSCパスを共有するため、
// run_headless.scd のホワイトリストに \matoma_lead を追加すること。
//
// 【設計哲学】
//   - per-note 型: エンベロープ付き、doneAction:2 で自己解放
//   - Saw × RLPF: サブトラクティブの素直な音色
//   - わずかなデチューン（1.008倍）で厚みを出す（Aphex Twin的薄さ）
//   - outBus: 0 直出し（エフェクトバスはPhase 4以降で追加）
//
// 【TidalでのPhase 1用法】
//   d8 $ s "matoma_lead" # freq "<261.63 293.66 329.63>" # amp 0.4
//   d8 $ slow 2 $ s "matoma_lead" # freq "<261.63 329.63 392.0 349.23>" # amp 0.4

(
SynthDef(\matoma_lead, {
    arg freq = 440, amp = 0.5, cutoff = 2000,
        atk = 0.02, rel = 0.5, outBus = 0;
    var env, sig, sigL, sigR;

    // percussive エンベロープ（atk短め・rel長め）
    env = EnvGen.kr(Env.perc(atk, rel), doneAction: 2);

    // デチューンしたデュアルSaw（わずかな広がり）
    sig  = Saw.ar(freq);
    sigL = Saw.ar(freq * 0.997);  // 左チャンネル: わずか低め
    sigR = Saw.ar(freq * 1.003);  // 右チャンネル: わずか高め

    // サブトラクティブフィルター
    sigL = RLPF.ar(sigL, cutoff, 0.45);
    sigR = RLPF.ar(sigR, cutoff, 0.45);

    Out.ar(outBus, [sigL, sigR] * amp * env);
}).add;

"matoma_lead SynthDef ロード完了".postln;
)
