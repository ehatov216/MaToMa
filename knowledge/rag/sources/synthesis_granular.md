---
title: Granular Synthesis in SuperCollider
category: synth
tags: [granular, texture, GrainBuf, TGrains, slowly-evolving, noise]
---

## Granular Synthesis in SuperCollider

Granular synthesis creates textures by overlapping many short grains (10–100 ms)
of audio. Use when Layer 1 shows **high noise_level**, **slowly-evolving
timescale**, or **low hpss_harmonic_ratio** (percussive/noisy character).

### Key UGens

| UGen | Best for |
|------|---------|
| `GrainBuf.ar(numCh, trig, dur, buf, rate, pos)` | Sampling/freezing a recorded sound |
| `TGrains.ar(numCh, trig, buf, rate, pos, dur, pan, amp)` | Real-time triggered grains |
| `GrainSin.ar(numCh, trig, dur, freq, pan, amp)` | Buffer-free sine grains |
| `GrainFM.ar(numCh, trig, dur, carFreq, modFreq, index, pan)` | FM grains (no buffer) |
| `Dust.ar(density)` | Random trigger for irregular grain density |

### Synthesis-only Granular Drone (no buffer required)
```supercollider
SynthDef(\sa_granular_drone, {
    arg freq = 220, amp = 0.3, gate = 1,
        grain_rate = 18, grain_dur = 0.07,
        noise_level = 0.3, pan = 0;
    var trig, sig, noise, env;

    trig = Dust.ar(grain_rate);

    // Sine grains detuned slightly for width
    sig = GrainSin.ar(
        numChannels: 2,
        trigger:     trig,
        dur:         grain_dur,
        freq:        freq * LFNoise1.kr(0.5).range(0.99, 1.01),
        pan:         LFNoise0.kr(8).range(-0.8, 0.8),
        amp:         amp
    );

    // Blend in noise for textural density (noise_level from Layer 1)
    noise = HPF.ar(WhiteNoise.ar(noise_level * 0.15), 800);
    sig   = sig + noise;

    env = EnvGen.ar(Env.adsr(1.0, 0.1, 0.9, 2.5), gate, doneAction: 2);
    Out.ar(0, sig * env);
}).add;
```

### FM Granular Texture (GrainFM — no buffer)
```supercollider
SynthDef(\sa_grain_fm, {
    arg freq = 300, amp = 0.25, gate = 1,
        grain_rate = 25, fm_index = 2.0, pan = 0;
    var trig, sig, env;

    trig = Impulse.ar(grain_rate) + Dust.ar(grain_rate * 0.3);
    sig  = GrainFM.ar(
        numChannels: 2,
        trigger:     trig,
        dur:         0.05,
        carFreq:     freq * LFNoise1.kr(0.2).range(0.98, 1.02),
        modFreq:     freq * 1.5,
        index:       fm_index,
        pan:         LFNoise1.kr(3).range(-0.7, 0.7),
        amp:         amp
    );

    env = EnvGen.ar(Env.adsr(0.8, 0.1, 0.85, 2.0), gate, doneAction: 2);
    Out.ar(0, sig * env);
}).add;
```

### Grain Parameter Guidelines (from Layer 1 features)

| Layer 1 feature | Mapping |
|---|---|
| `noise_level` > 0.4 | Increase `grain_rate` (20–30), shorten `grain_dur` (0.03–0.06s) |
| `timescale == "slowly-evolving"` | Slow `posSpeed` (0.01–0.05), longer grain dur (0.08–0.12s) |
| `timescale == "fast-evolving"` | `Dust` trigger, short grains (0.02–0.05s), wider pan range |
| `hpss_harmonic_ratio` < 0.5 | Use `GrainFM` or `GrainSin` (no buffer) for harmonic texture |
| `lfo_rate` > 1.0 | Modulate `grain_rate` with an LFO at that rate |
| `spectral_centroid` < 500 Hz | Base freq in 80–200 Hz range, use `HPF` to avoid muddiness |
