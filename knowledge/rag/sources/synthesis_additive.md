---
title: Additive Synthesis in SuperCollider
category: synth
tags: [additive, harmonics, partials, tonal, hpss, harmonic-ratio]
---

## Additive Synthesis in SuperCollider

Additive synthesis builds timbres by summing sine waves (partials) at
harmonic or inharmonic frequency ratios. Use when Layer 1 shows
**high hpss_harmonic_ratio** (tonal, harmonic content), **low noise_level**,
or you need precise control over the harmonic spectrum.

### Key UGens

| UGen | Description |
|------|-------------|
| `SinOsc.ar(freq, phase, mul)` | Single sine partial |
| `Klang.ar(specificationsArray, freqScale, freqOffset)` | Bank of sine oscillators |
| `DynKlang.ar(specificationsArray)` | Dynamic version (modulatable) |
| `Mix(array)` | Sum an array of signals |
| `Array.fill(n, fn)` | Generate harmonic series programmatically |

### Harmonic Series Pad
```supercollider
SynthDef(\sa_additive_pad, {
    arg freq = 220, amp = 0.2, gate = 1, pan = 0,
        brightness = 0.5;   // 0=dark (few harmonics), 1=bright (many)

    var n_harmonics = (brightness * 12 + 2).round.asInteger;
    var partials, amps, sig, env;

    // Harmonic series with amplitude roll-off
    partials = Array.fill(n_harmonics, { |i|
        var harmonic = i + 1;
        var amp_k    = 1.0 / harmonic;         // natural roll-off
        SinOsc.ar(freq * harmonic, 0, amp_k)
    });

    sig = Mix(partials) * (1.0 / n_harmonics.sqrt);  // normalise
    sig = Pan2.ar(sig, 0);
    sig = FreeVerb2.ar(sig[0], sig[1], mix: 0.25, room: 0.6);

    env = EnvGen.ar(Env.adsr(0.3, 0.2, 0.8, 1.0), gate, doneAction: 2);
    Out.ar(0, Balance2.ar(sig[0], sig[1], pan) * env * amp);
}).add;
```

### Klang Bell (inharmonic partials)
```supercollider
SynthDef(\sa_klang_bell, {
    arg freq = 440, amp = 0.3, gate = 1, pan = 0;
    var spec, sig, env;

    // Inharmonic ratios typical of metal bars / bells
    spec = `[
        Array.with(freq, freq*2.756, freq*5.404, freq*8.933, freq*13.34),
        Array.with(0, 0, 0, 0, 0),       // phases
        Array.with(1.0, 0.6, 0.4, 0.25, 0.1)  // amps
    ];
    sig  = Klang.ar(spec, 1, 0);
    sig  = Splay.ar([sig, sig * 0.99]);   // subtle width
    sig  = FreeVerb2.ar(sig[0], sig[1], mix: 0.3, room: 0.7);

    env = EnvGen.ar(Env.perc(0.001, 2.5), gate, doneAction: 2);
    Out.ar(0, Balance2.ar(sig[0], sig[1], pan) * env * amp);
}).add;
```

### Mapping Layer 1 Features to Additive Parameters

| Layer 1 feature | Mapping |
|---|---|
| `hpss_harmonic_ratio` > 2.0 | Strong harmonic content → use harmonic series, many partials |
| `spectral_centroid` > 2000 Hz | Use `brightness = 0.7–1.0` (upper harmonics) |
| `spectral_centroid` < 600 Hz | Use `brightness = 0.1–0.3` (fundamental + 2nd harmonic only) |
| `noise_level` < 0.1 | Pure tonal → full additive without noise mix |
| `timescale == "slowly-evolving"` | Animate partial amplitudes with slow LFO |
| `lfo_rate` from Layer 1 | Modulate individual partial amplitudes at that rate |

### Animating Partials
```supercollider
// Slowly breathing additive pad using DynKlang
SynthDef(\sa_breathing_pad, {
    arg freq = 220, amp = 0.2, gate = 1, lfo_rate = 0.3;
    var freqs, amps, sig, env;

    freqs = (1..8) * freq;
    // Each partial breathes at a slightly different rate
    amps  = Array.fill(8, { |i|
        var rate = lfo_rate * (1 + (i * 0.1));
        SinOsc.kr(rate).range(0.05, 1.0 / (i + 1))
    });

    sig  = DynKlang.ar(`[freqs, nil, amps]);
    sig  = Pan2.ar(sig * (1 / 4), 0);
    sig  = FreeVerb2.ar(sig[0], sig[1], mix: 0.3, room: 0.7);

    env = EnvGen.ar(Env.adsr(0.5, 0.1, 0.9, 1.5), gate, doneAction: 2);
    Out.ar(0, Balance2.ar(sig[0], sig[1], 0) * env * amp);
}).add;
```
