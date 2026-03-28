---
title: Physical Modeling Synthesis in SuperCollider
category: synth
tags: [physical-modeling, Pluck, Karplus-Strong, modal, resonator, Ringz, Klank, plucked-string]
---

## Physical Modeling Synthesis in SuperCollider

Physical modeling simulates the physics of acoustic instruments: resonating
bodies, struck/plucked strings, blown tubes. Use when analysis shows
**percussive transients**, **high hpss_harmonic_ratio** with **low noise_level**,
or you want organic, evolving timbres distinctly different from oscillator pads.

### Key UGens

| UGen | Description |
|------|-------------|
| `Pluck.ar(in, trig, maxDelay, delay, decay, coef)` | Karplus-Strong plucked string |
| `Ringz.ar(in, freq, decayTime)` | Resonant filter (bell/bar resonance) |
| `Klank.ar(specificationsArray, in, freqScale)` | Bank of resonators (struck metal, glass) |
| `DynKlank.ar(specificationsArray, in)` | Modulatable resonator bank |
| `Spring.ar(in, spring, damp)` | Spring + mass system (bouncy resonance) |
| `CombL.ar(in, maxDelay, delay, decay)` | Comb filter (room / string resonance) |

---

### Karplus-Strong Plucked String
```supercollider
SynthDef(\sa_pluck_string, {
    arg freq = 220, amp = 0.4, gate = 1, pan = 0,
        decay = 4.0, coef = 0.3;
    var exc, sig, env;

    // Noise burst excitation
    exc = WhiteNoise.ar(0.1) * EnvGen.ar(Env.perc(0.001, 0.02));
    sig = Pluck.ar(exc, Impulse.ar(0), freq.reciprocal, freq.reciprocal, decay, coef);

    // Subtle stereo: Haas on second channel
    sig = FreeVerb2.ar(sig, DelayN.ar(sig, 0.03, 0.009),
        mix: 0.15, room: 0.4, damp: 0.6);

    env = EnvGen.ar(Env.adsr(0.001, 0.1, 0.6, decay * 0.3), gate, doneAction: 2);
    Out.ar(0, Balance2.ar(sig[0], sig[1], pan) * env * amp);
}).add;
```

### Bowed String (CombL resonance)
```supercollider
SynthDef(\sa_bowed_string, {
    arg freq = 220, amp = 0.25, gate = 1, pan = 0,
        bow_pressure = 0.5;
    var exc, sig, env;

    // Noise excitation → comb gives pitch
    exc = BrownNoise.ar(bow_pressure * 0.3);
    sig = CombL.ar(exc, freq.reciprocal, freq.reciprocal, 4.0);
    sig = RLPF.ar(sig, freq * 3.5, 0.6);

    // Slow tremolo for bow movement realism
    sig = sig * (1 + (SinOsc.kr(5.2).range(-0.08, 0.08)));

    // Stereo spread
    sig = Splay.ar([sig, sig * LFNoise1.kr(0.2).range(0.97, 1.03)]);
    sig = FreeVerb2.ar(sig[0], sig[1], mix: 0.25, room: 0.55);

    env = EnvGen.ar(Env.adsr(0.3, 0.05, 0.8, 0.4), gate, doneAction: 2);
    Out.ar(0, Balance2.ar(sig[0], sig[1], pan) * env * amp);
}).add;
```

### Modal / Struck Metal Bar (Klank resonators)
```supercollider
SynthDef(\sa_modal_bar, {
    arg freq = 440, amp = 0.35, gate = 1, pan = 0;
    var imp, sig, env;

    // Impulse excitation (mallet strike)
    imp = Impulse.ar(0) * amp;

    // Inharmonic partials of aluminum bar
    sig = Klank.ar(`[
        [freq, freq * 2.756, freq * 5.404, freq * 8.933, freq * 13.34],
        [1.0,  0.5,          0.3,          0.15,         0.07],
        [2.0,  1.5,          1.0,          0.7,          0.4]
    ], imp);

    // Stereo spread via tiny L/R detuning in two Klanks
    var sig2 = Klank.ar(`[
        [freq*1.001, freq*2.758, freq*5.407],
        [0.9, 0.45, 0.27],
        [2.1, 1.55, 1.05]
    ], imp);
    sig = FreeVerb2.ar(sig, sig2, mix: 0.3, room: 0.6, damp: 0.5);

    env = EnvGen.ar(Env.perc(0.001, 3.0), gate, doneAction: 2);
    Out.ar(0, Balance2.ar(sig[0], sig[1], pan) * env);
}).add;
```

### Spring Reverb / Metallic Resonance
```supercollider
SynthDef(\sa_spring_metal, {
    arg freq = 330, amp = 0.3, gate = 1, pan = 0,
        spring_const = 60.0, damp = 0.3;
    var exc, sig, env;

    exc  = Impulse.ar(0) + (WhiteNoise.ar(0.03) * EnvGen.ar(Env.perc(0.001, 0.04)));
    sig  = Spring.ar(exc, spring_const, damp);
    sig  = sig + Ringz.ar(exc, freq, 1.5, 0.6);
    sig  = RLPF.ar(sig, freq * 4, 0.45);
    sig  = FreeVerb2.ar(sig, DelayN.ar(sig, 0.03, 0.013),
            mix: 0.4, room: 0.75, damp: 0.35);

    env = EnvGen.ar(Env.perc(0.001, 2.5), gate, doneAction: 2);
    Out.ar(0, Balance2.ar(sig[0], sig[1], pan) * env * amp);
}).add;
```

### Resonator Bank / Glass Harmonica
```supercollider
SynthDef(\sa_glass_resonator, {
    arg freq = 523, amp = 0.2, gate = 1, pan = 0, lfo_rate = 0.5;
    var exc, sigs, sig, env;

    exc = WhiteNoise.ar(0.08) * SinOsc.kr(lfo_rate).range(0.3, 1.0);

    // Harmonic series resonators with slight detuning
    sigs = Array.fill(6, { |i|
        Ringz.ar(exc, freq * (i + 1) * LFNoise1.kr(0.1).range(0.995, 1.005),
            3.0 / (i + 1))
    });
    sig = Mix(sigs) * 0.14;
    sig = Splay.ar([sig, sig * LFNoise1.kr(0.07).range(0.96, 1.04)]);
    sig = FreeVerb2.ar(sig[0], sig[1], mix: 0.45, room: 0.85, damp: 0.2);

    env = EnvGen.ar(Env.adsr(1.0, 0.1, 0.85, 2.0), gate, doneAction: 2);
    Out.ar(0, Balance2.ar(sig[0], sig[1], pan) * env * amp);
}).add;
```

### Mapping Layer 1 Features to Physical Modeling

| Layer 1 feature | Mapping |
|---|---|
| `hpss_harmonic_ratio` > 3.0 | Use Klank/Ringz resonators (rich harmonics) |
| `hpss_harmonic_ratio` < 0.5 | Use Pluck with noise excitation (inharmonic) |
| `spectral_centroid` > 3000 Hz | High partial frequencies; `decay` short (0.3–1.0s) |
| `spectral_centroid` < 500 Hz | Low fundamentals; `decay` long (3–8s) |
| `fm_index` > 2.0 | Use Spring.ar or DynKlank with excited resonators |
| `noise_level` > 0.3 | Noise-excited Pluck or bowed (CombL) models |
| `timescale == "fast-evolving"` | Short `decay`, Impulse triggers at beat subdivisions |
| `timescale == "static"` | Long sustaining resonators (Ringz, glass) |
