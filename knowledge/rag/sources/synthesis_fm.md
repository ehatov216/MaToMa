---
title: FM and Phase Modulation Synthesis in SuperCollider
category: synth
tags: [fm, phase-modulation, PMOsc, SinOsc, dynamic-timbre]
---

## FM and Phase Modulation Synthesis in SuperCollider

FM (Frequency Modulation) synthesis produces rich, dynamic timbres by using
one oscillator (modulator) to modulate the frequency of another (carrier).
Use FM when audio analysis shows **high fm_index**, **mid-to-high spectral
centroid**, or **fast-evolving texture**.

### Key UGens

| UGen | Description |
|------|-------------|
| `PMOsc.ar(carFreq, modFreq, pmIndex, modPhase)` | Phase modulation oscillator (cleaner than raw FM) |
| `SinOsc.ar(freq + SinOsc.ar(modFreq) * index)` | Classic FM with inline modulator |
| `FM7.ar(ctlMatrix, modMatrix)` | 6-operator FM (sc3-plugins) |
| `Line.kr(start, end, dur)` | Time-varying modulation index for evolving timbres |

### Basic FM Bell / Lead
```supercollider
SynthDef(\sa_fm_lead, {
    arg freq = 440, amp = 0.3, gate = 1, pan = 0,
        fm_index = 2.0, mod_ratio = 1.5;
    var mod, sig, haas, env;

    // Modulator: frequency = carrier × ratio
    mod = SinOsc.ar(freq * mod_ratio) * freq * fm_index;
    sig = SinOsc.ar(freq + mod);

    // Haas stereo widening
    haas = DelayN.ar(sig, 0.03, 0.011);
    sig  = FreeVerb2.ar(sig, haas, mix: 0.2, room: 0.5, damp: 0.4);

    env = EnvGen.ar(Env.adsr(0.05, 0.1, 0.7, 0.4), gate, doneAction: 2);
    Out.ar(0, Balance2.ar(sig[0], sig[1], pan) * env * amp);
}).add;
```

### Evolving FM Pad (time-varying index)
```supercollider
SynthDef(\sa_fm_pad, {
    arg freq = 440, amp = 0.2, gate = 1, pan = 0,
        fm_index = 3.0;
    var index, sigs, sig, env;

    // Index decays over time → bell-like onset then pure tone
    index = EnvGen.kr(Env([fm_index, fm_index * 0.3, 0.5], [0.3, 2.0]));

    sigs = [
        PMOsc.ar(freq * 1.003, freq * 2.0, index),
        PMOsc.ar(freq,         freq * 2.0, index),
        PMOsc.ar(freq * 0.997, freq * 1.5, index * 0.7)
    ];
    sig = Splay.ar(sigs);
    sig = FreeVerb2.ar(sig[0], sig[1], mix: 0.3, room: 0.65);

    env = EnvGen.ar(Env.adsr(0.3, 0.2, 0.8, 1.0), gate, doneAction: 2);
    Out.ar(0, Balance2.ar(sig[0], sig[1], pan) * env * amp);
}).add;
```

### FM Index Guidelines (fm_index from Layer 1)
| fm_index value | Timbre character | Recommended use |
|---|---|---|
| 0 – 0.5 | Near-sine, warm | Soft pad, bass |
| 0.5 – 2.0 | Mellow with overtones | Lead, pad |
| 2.0 – 5.0 | Bright, metallic | Bell, pluck, lead |
| 5.0+ | Harsh, noisy | Percussion, texture |

### Mapping Layer 1 Features to FM Parameters
- `fm_index` (from `virtual_synth_parameters`) → use directly as `pmIndex`
- `spectral_centroid` > 2000 Hz → increase `mod_ratio` to 2.0–3.0
- `hpss_harmonic_ratio` > 2.0 → use time-varying index for organic feel
- `lfo_rate` > 0 → add slow LFO on `fm_index` for evolving texture:
  ```supercollider
  index = fm_index + (SinOsc.kr(lfo_rate) * fm_index * lfo_depth);
  ```
