---
title: Subtractive Synthesis with Stereo Design in SuperCollider
category: synth
tags: [subtractive, filter, stereo, Splay, pad, lead, bass]
---

## Subtractive Synthesis with Stereo Design

Subtractive synthesis starts from a harmonically rich source (Saw, Pulse, Noise)
and sculpts it with filters and envelopes. This is the most common synthesis
approach; combine with stereo widening techniques for professional results.

### Oscillator Sources

| Source | Character | Use case |
|--------|-----------|---------|
| `Saw.ar(freq)` | Bright, all harmonics | Lead, pad, bass |
| `Pulse.ar(freq, width)` | Hollow or buzzy | Bass, pluck |
| `LFSaw.ar(freq)` | Aliased, raw | Sub-bass |
| `VarSaw.ar(freq, wd)` | Variable waveshape | Versatile lead |
| `WhiteNoise.ar` | Flat spectrum | Percussion, texture |

### Filters

| Filter | Character |
|--------|-----------|
| `RLPF.ar(sig, cutoff, rq)` | Low-pass with resonance |
| `RHPF.ar(sig, cutoff, rq)` | High-pass with resonance |
| `BPF.ar(sig, freq, bw)` | Band-pass (formant-like) |
| `MoogFF.ar(sig, cutoff, gain)` | Moog ladder (sc3-plugins) |

### Stereo Pad (Technique A: Splay.ar)
```supercollider
SynthDef(\sa_sub_pad, {
    arg freq = 440, amp = 0.2, gate = 1, pan = 0,
        cutoff = 1200, lfo_rate = 0.3, lfo_depth = 0.3;
    var sigs, sig, env;

    // Five detuned saws spread across stereo field
    sigs = [
        Saw.ar(freq * 1.007), Saw.ar(freq * 1.002), Saw.ar(freq),
        Saw.ar(freq * 0.998), Saw.ar(freq * 0.993)
    ];
    sig = Splay.ar(sigs);

    // Filter with LFO modulation (lfo_rate from Layer 1)
    sig = RLPF.ar(sig,
        cutoff + (SinOsc.kr(lfo_rate) * lfo_depth * cutoff),
        0.4);

    // Stereo chorus + reverb
    sig = sig + [
        DelayC.ar(sig[0], 0.05, LFNoise1.kr(0.31).range(0.007, 0.021)) * 0.3,
        DelayC.ar(sig[1], 0.05, LFNoise1.kr(0.29).range(0.011, 0.023)) * 0.3
    ];
    sig = FreeVerb2.ar(sig[0], sig[1], mix: 0.35, room: 0.7, damp: 0.38);

    env = EnvGen.ar(Env.adsr(0.3, 0.1, 0.8, 1.2), gate, doneAction: 2);
    Out.ar(0, Balance2.ar(sig[0], sig[1], pan) * env * amp);
}).add;
```

### Lead Synth (Technique B: Haas effect)
```supercollider
SynthDef(\sa_sub_lead, {
    arg freq = 440, amp = 0.3, gate = 1, pan = 0,
        cutoff = 2000, res = 0.4;
    var sig, haas, env;

    sig  = VarSaw.ar(freq, 0, 0.5) + VarSaw.ar(freq * 1.003, 0, 0.5, 0.3);
    sig  = RLPF.ar(sig, cutoff, res);

    // Haas effect: ~11ms delay → stereo width without comb filtering
    haas = DelayN.ar(sig, 0.03, 0.011);
    sig  = FreeVerb2.ar(sig, haas, mix: 0.2, room: 0.5, damp: 0.4);

    env = EnvGen.ar(Env.adsr(0.05, 0.1, 0.7, 0.4), gate, doneAction: 2);
    Out.ar(0, Balance2.ar(sig[0], sig[1], pan) * env * amp);
}).add;
```

### Bass (Mono — critical for mix translation)
```supercollider
SynthDef(\sa_sub_bass, {
    arg freq = 60, amp = 0.5, gate = 1, cutoff = 800, res = 0.3;
    var sig, env;

    sig = LFSaw.ar(freq) + LFPulse.ar(freq * 0.5, 0, 0.5, 0.4);
    sig = RLPF.ar(sig, cutoff, res);

    env = EnvGen.ar(Env.adsr(0.01, 0.2, 0.6, 0.15), gate, doneAction: 2);
    // Always Pan2 at 0 for bass — mono center for mix translation
    Out.ar(0, Pan2.ar(sig * env * amp, 0));
}).add;
```

### Mapping Layer 1 Features to Subtractive Parameters

| Layer 1 feature | Mapping |
|---|---|
| `spectral_centroid` → `cutoff` | centroid × 2.0 (Hz), clip 200–8000 |
| `hpss_harmonic_ratio` > 3 | Use Saw (rich harmonics); < 1 use Pulse/Noise |
| `lfo_rate`, `lfo_depth` | Apply to filter cutoff modulation directly |
| `oscillator_mix` 0–1 | Blend Saw (0) ↔ Pulse (1) using `XFade2.ar` |
| `noise_level` > 0.2 | Mix in `WhiteNoise.ar(noise_level * 0.3)` |
