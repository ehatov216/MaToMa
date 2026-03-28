---
title: Wavetable Synthesis in SuperCollider
category: synth
tags: [wavetable, Osc, VOsc, morphing, static-timbre, oscillator-mix]
---

## Wavetable Synthesis in SuperCollider

Wavetable synthesis reads a single-cycle waveform from a buffer.
Morphing between wavetables (VOsc) creates smooth timbral evolution.
Use when Layer 1 shows **high oscillator_mix**, **static or slowly-evolving
timescale**, or when you need precise waveform control over tonal content.

### Key UGens

| UGen | Description |
|------|-------------|
| `Osc.ar(buf, freq, phase)` | Single wavetable oscillator |
| `OscN.ar(buf, freq)` | Non-interpolating (lower CPU) |
| `VOsc.ar(bufpos, freq)` | Interpolates between adjacent wavetable buffers |
| `VOsc3.ar(bufpos, freq, freqB, freqC)` | Three-voice vector oscillator |
| `Signal.fill(n, fn).asWavetable` | Build wavetable from a function |

### Building Wavetables at Boot
```supercollider
// In s.waitForBoot { } — create wavetables for different timbres
var makeBuf = { |fn|
    var sig = Signal.fill(512, fn);
    var wt  = sig.asWavetable;
    var buf = Buffer.alloc(s, 1024, 1);
    buf.loadCollection(wt);
    buf
};

~wtSine = makeBuf.({ |i| sin(2pi * i / 512) });
~wtSaw  = makeBuf.({ |i| (2 * (i / 512)) - 1 });
~wtSq   = makeBuf.({ |i| if(i < 256) { 1 } { -1 } });
s.sync;
```

### Static Wavetable Pad (oscillator_mix controls waveform blend)
```supercollider
SynthDef(\sa_wt_pad, {
    arg freq = 440, amp = 0.25, gate = 1, pan = 0,
        osc_mix = 0.5,       // 0=sine, 0.5=between, 1=saw
        cutoff = 1600, lfo_rate = 0.3;
    var bufpos, sigs, sig, env;

    // osc_mix maps to fractional position between two wavetable buffers
    // Requires ~wtSine and ~wtSaw to be in consecutive buffer slots
    bufpos = ~wtSine.bufnum + osc_mix;

    sigs = [
        VOsc.ar(bufpos, freq * 1.005),
        VOsc.ar(bufpos, freq * 1.001),
        VOsc.ar(bufpos, freq),
        VOsc.ar(bufpos, freq * 0.999),
        VOsc.ar(bufpos, freq * 0.995)
    ];
    sig = Splay.ar(sigs);
    sig = RLPF.ar(sig, cutoff + (SinOsc.kr(lfo_rate) * 300), 0.5);
    sig = FreeVerb2.ar(sig[0], sig[1], mix: 0.3, room: 0.65, damp: 0.4);

    env = EnvGen.ar(Env.adsr(0.4, 0.2, 0.8, 1.2), gate, doneAction: 2);
    Out.ar(0, Balance2.ar(sig[0], sig[1], pan) * env * amp);
}).add;
```

### Morphing Wavetable (slowly-evolving texture)
```supercollider
SynthDef(\sa_wt_morph, {
    arg freq = 440, amp = 0.2, gate = 1, pan = 0,
        morph_rate = 0.15;
    var pos, sig, env;

    // Slowly sweep through the wavetable bank
    pos = LFTri.kr(morph_rate).range(~wtSine.bufnum, ~wtSaw.bufnum);
    sig = VOsc3.ar(pos, freq * 1.003, freq, freq * 0.997);
    sig = Splay.ar([sig]);
    sig = FreeVerb2.ar(sig[0], sig[1], mix: 0.35, room: 0.7);

    env = EnvGen.ar(Env.adsr(0.5, 0.1, 0.85, 1.5), gate, doneAction: 2);
    Out.ar(0, Balance2.ar(sig[0], sig[1], pan) * env * amp);
}).add;
```

### Mapping Layer 1 Features to Wavetable Parameters

| Layer 1 feature | Mapping |
|---|---|
| `oscillator_mix` 0–1 | `bufpos = baseBuf + oscillator_mix` for waveform blend |
| `timescale == "static"` | Use fixed `bufpos` (no morphing LFO) |
| `timescale == "slowly-evolving"` | Morph with `LFTri.kr(0.05–0.3)` |
| `spectral_centroid` < 800 Hz | Lower `cutoff` (600–1200 Hz), use sine-heavy wavetable |
| `lfo_rate` from Layer 1 | Use as `morph_rate` for `VOsc` position LFO |

### Important: Buffer Size Rule
- `Signal.fill(N, fn)` → `asWavetable` doubles size → allocate `Buffer.alloc(s, N*2)`
- `VOsc` requires adjacent buffer numbers with identical size
- Always call `s.sync` after `buf.loadCollection(wt)` before using the buffer
