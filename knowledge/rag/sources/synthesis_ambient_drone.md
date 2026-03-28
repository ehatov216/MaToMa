---
title: Ambient and Drone Synthesis in SuperCollider
category: synth
tags: [ambient, drone, static, slowly-evolving, feedback, texture, long-form, atmosphere]
---

## Ambient and Drone Synthesis in SuperCollider

Ambient and drone patches are designed for **sustained, evolving texture** over
long durations. Use when analysis shows `timescale == "static"` or
`"slowly-evolving"`, low `bpm` (< 80), or high `rt60` (> 1.5 s).

### Principles
- Long attack (2–8 s) and release (3–10 s) to avoid sharp edges
- Very slow LFO modulation (0.01–0.15 Hz) for imperceptible drift
- Heavy reverb (room ≥ 0.75, mix ≥ 0.45) to create space
- Detuned unison for "floating" quality (± 0.3–1 Hz off-tune)

---

### Floating Drone (detuned oscillator cloud)
```supercollider
SynthDef(\sa_float_drone, {
    arg freq = 110, amp = 0.18, gate = 1, pan = 0,
        lfo_rate = 0.04, cutoff = 900;
    var sigs, sig, lfo, env;

    // Slowly drifting detuning
    lfo = SinOsc.kr(lfo_rate).range(0.997, 1.003);

    sigs = [
        Saw.ar(freq * lfo),
        Saw.ar(freq * 0.501),          // sub octave
        Saw.ar(freq * 1.0013),
        Saw.ar(freq * 2.0017),         // octave with micro detune
        SinOsc.ar(freq * 3.001, 0, 0.3)
    ];
    sig = Splay.ar(sigs);
    sig = RLPF.ar(sig,
        cutoff + (SinOsc.kr(lfo_rate * 0.37) * cutoff * 0.4),
        0.55);
    sig = FreeVerb2.ar(sig[0], sig[1], mix: 0.55, room: 0.88, damp: 0.25);

    env = EnvGen.ar(Env.adsr(5.0, 0.5, 0.9, 6.0), gate, doneAction: 2);
    Out.ar(0, Balance2.ar(sig[0], sig[1], pan) * env * amp);
}).add;
```

### Feedback Drone (LocalIn / LocalOut loop)
```supercollider
SynthDef(\sa_feedback_drone, {
    arg freq = 80, amp = 0.15, gate = 1, pan = 0,
        feedback_amt = 0.35;
    var fb, sig, env;

    fb  = LocalIn.ar(2);
    sig = SinOsc.ar([freq, freq * 1.004]) + (fb * feedback_amt);
    sig = Limiter.ar(sig, 0.6);
    sig = AllpassC.ar(LPF.ar(sig, 2400), 0.08,
        [LFNoise1.kr(0.11).range(0.03, 0.07),
         LFNoise1.kr(0.09).range(0.04, 0.08)], 2.0);
    LocalOut.ar(sig);

    sig = FreeVerb2.ar(sig[0], sig[1], mix: 0.6, room: 0.92, damp: 0.18);

    env = EnvGen.ar(Env.adsr(4.0, 0.3, 0.85, 8.0), gate, doneAction: 2);
    Out.ar(0, Balance2.ar(sig[0], sig[1], pan) * env * amp);
}).add;
```

### Spectral Shimmer Pad (pitch-shifted reverb tail)
```supercollider
SynthDef(\sa_shimmer, {
    arg freq = 220, amp = 0.2, gate = 1, pan = 0, shift = 2.0;
    var sigs, sig, shifted, env;

    sigs = [Saw.ar(freq * 1.003), Saw.ar(freq), Saw.ar(freq * 0.997)];
    sig  = Splay.ar(sigs);
    sig  = RLPF.ar(sig, 1800, 0.6);

    // Shimmer: pitch-shift reverb tail up an octave
    shifted = PitchShift.ar(sig, 0.1, shift, 0.01, 0.005);
    sig = FreeVerb2.ar(sig[0] + (shifted[0] * 0.3),
                       sig[1] + (shifted[1] * 0.3),
                       mix: 0.65, room: 0.95, damp: 0.1);

    env = EnvGen.ar(Env.adsr(3.5, 0.2, 0.88, 5.0), gate, doneAction: 2);
    Out.ar(0, Balance2.ar(sig[0], sig[1], pan) * env * amp);
}).add;
```

### Breath Pad (slowly pulsing amplitude / filter)
```supercollider
SynthDef(\sa_breath_pad, {
    arg freq = 440, amp = 0.2, gate = 1,
        breath_rate = 0.12, cutoff = 1200;
    var sigs, sig, breath, env;

    // Breath modulation: gentle sine on amplitude
    breath = SinOsc.kr(breath_rate).range(0.5, 1.0);

    sigs = [Pulse.ar(freq * 1.004, 0.5),
            Pulse.ar(freq, 0.48),
            SinOsc.ar(freq * 0.5, 0, 0.5)];
    sig = Splay.ar(sigs) * breath;
    sig = RLPF.ar(sig,
        cutoff + (SinOsc.kr(breath_rate * 0.63) * cutoff * 0.5),
        0.65);
    sig = FreeVerb2.ar(sig[0], sig[1], mix: 0.50, room: 0.80, damp: 0.3);

    env = EnvGen.ar(Env.adsr(4.0, 0.3, 0.85, 5.0), gate, doneAction: 2);
    Out.ar(0, Balance2.ar(sig[0], sig[1], 0) * env * amp);
}).add;
```

### Wind / Air Texture (filtered noise + resonance)
```supercollider
SynthDef(\sa_wind_texture, {
    arg amp = 0.22, gate = 1, freq = 300, gust_rate = 0.15;
    var gust, sig, env;

    // Gusting amplitude envelope
    gust = SinOsc.kr(gust_rate).range(0.15, 1.0) *
           LFNoise1.kr(0.4).range(0.4, 1.0);

    sig  = HPF.ar(PinkNoise.ar, 100);
    sig  = BPF.ar(sig, freq, 0.5, gust);
    sig  = sig + BPF.ar(PinkNoise.ar, freq * 1.618, 0.3, gust * 0.4);
    sig  = FreeVerb2.ar(sig, sig * 0.9, mix: 0.70, room: 0.95, damp: 0.15);

    env = EnvGen.ar(Env.adsr(3.0, 0.2, 0.9, 6.0), gate, doneAction: 2);
    Out.ar(0, Balance2.ar(sig[0], sig[1], 0) * env * amp);
}).add;
```

### Tonal Cluster Pad (many close intervals, cluster chord)
```supercollider
SynthDef(\sa_cluster_pad, {
    arg freq = 261, amp = 0.15, gate = 1, spread = 0.08;
    var ratios, sigs, sig, env;

    // Cluster: 7 pitches within a major 7th
    ratios = [1.0, 1.035, 1.07, 1.122, 1.189, 1.26, 1.334];
    sigs = ratios.collect { |r, i|
        var lp = SinOsc.kr(0.05 + (i * 0.013)).range(0.996, 1.004);
        VarSaw.ar(freq * r * lp, 0, 0.4 + (i * 0.05))
    };
    sig = Splay.ar(sigs);
    sig = RLPF.ar(sig, 1500 + (SinOsc.kr(0.03) * 600), 0.55);
    sig = FreeVerb2.ar(sig[0], sig[1], mix: 0.60, room: 0.90, damp: 0.22);

    env = EnvGen.ar(Env.adsr(5.0, 0.3, 0.88, 6.0), gate, doneAction: 2);
    Out.ar(0, Balance2.ar(sig[0], sig[1], 0) * env * amp);
}).add;
```

### Mapping to Layer 1 Features

| Feature | Mapping |
|---------|---------|
| `rt60 > 1.5 s` | Heavy reverb: `room=0.9, mix=0.6, damp=0.15` |
| `rt60 < 0.4 s` | Lighter reverb: `room=0.4, mix=0.2, damp=0.6` |
| `timescale == "static"` | Use `sa_float_drone` or `sa_breath_pad`; very slow LFO |
| `timescale == "slowly-evolving"` | Use `sa_shimmer` or `sa_feedback_drone`; lfo_rate = 0.05–0.12 |
| `stereo_width > 0.7` | Use wider Splay spread, strong chorus, high reverb mix |
| `stereo_width < 0.2` | Mono-friendly: narrow spread, `Pan2.ar(sig, 0)` |
| `lfo_rate` from stem | Apply to breath modulation or filter sweep rate directly |
| `noise_level > 0.3` | Use `sa_wind_texture` or add `PinkNoise` component |
| `oscillator_mix > 0.6` | Use additive `sa_cluster_pad`; mix multiple partials |
