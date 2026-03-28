---
title: Spectral and Waveshaping Synthesis in SuperCollider
category: synth
tags: [spectral, PV, phase-vocoder, waveshaping, Shaper, ring-modulation, AM, bitcrusher, distortion]
---

## Spectral and Waveshaping Synthesis in SuperCollider

These techniques manipulate existing signals in the frequency domain (PV_* UGens)
or reshape waveforms nonlinearly (Shaper, distortion). Especially useful for
**evolving textural pads**, **frozen spectral drones**, **metallic cross-synthesis**,
and **lo-fi / industrial textures**.

### Key UGens

| UGen | Description |
|------|-------------|
| `PV_MagSmear(buf, amount)` | Blur/smear magnitudes across frequency bins (freeze-like) |
| `PV_MagFreeze(buf, freeze)` | Freeze current spectrum when freeze=1 |
| `PV_BrickWall(buf, wipe)` | Brick-wall spectral filter (high/low pass in freq domain) |
| `PV_RandComb(buf, wipe, trig)` | Zero random bins (metallic comb effect) |
| `PV_HainsworthFoote(buf, ...)` | Onset detection in spectral domain |
| `Shaper.ar(buf, in)` | Waveshaping via wavetable lookup |
| `WaveShaper.ar(in, low, high)` | Simple wavefolder/clipper |
| `Decimator.ar(in, rate, bits)` | Bit-crushing / sample-rate reduction (lo-fi) |
| `FreqShift.ar(in, freq, phase)` | Frequency shift (not pitch shift — creates inharmonics) |
| `Hilbert.ar(in)` | Hilbert transform → ring mod / SSB |

---

### Spectral Freeze / Shimmer Drone
```supercollider
SynthDef(\sa_spectral_freeze, {
    arg freq = 220, amp = 0.2, gate = 1, pan = 0,
        freeze = 1.0, smear = 1.5;
    var src, chain, sig, env;

    // Source: short oscillator burst → freeze its spectrum
    src   = SinOsc.ar(freq) * EnvGen.ar(Env.perc(0.001, 0.2));
    chain = FFT(LocalBuf(2048), src);
    chain = PV_MagSmear(chain, smear);
    chain = PV_MagFreeze(chain, freeze);

    sig   = IFFT(chain);
    sig   = Splay.ar([sig, FreqShift.ar(sig, 0.5)]);   // sub-Hz shift for beating
    sig   = FreeVerb2.ar(sig[0], sig[1], mix: 0.65, room: 0.92, damp: 0.15);

    env = EnvGen.ar(Env.adsr(2.0, 0.1, 0.9, 4.0), gate, doneAction: 2);
    Out.ar(0, Balance2.ar(sig[0], sig[1], pan) * env * amp);
}).add;
```

### Spectral Comb / Metallic Texture
```supercollider
SynthDef(\sa_spectral_comb, {
    arg freq = 300, amp = 0.25, gate = 1, pan = 0, wipe = 0.6;
    var src, chain, sig, env;

    src   = Saw.ar(freq) + SinOsc.ar(freq * 3.01, 0, 0.3);
    chain = FFT(LocalBuf(1024), src);
    chain = PV_RandComb(chain, wipe, Impulse.kr(0.5));
    chain = PV_MagSmear(chain, 0.8);

    sig = IFFT(chain);
    sig = FreeVerb2.ar(sig, DelayN.ar(sig, 0.03, 0.011),
          mix: 0.4, room: 0.7, damp: 0.35);

    env = EnvGen.ar(Env.adsr(0.3, 0.1, 0.8, 1.0), gate, doneAction: 2);
    Out.ar(0, Balance2.ar(sig[0], sig[1], pan) * env * amp);
}).add;
```

### Waveshaping (Chebyshev polynomials — harmonic enhancement)
```supercollider
SynthDef(\sa_waveshaped_lead, {
    arg freq = 440, amp = 0.3, gate = 1, pan = 0, shape = 0.6;
    var sig, shaped, env;

    // Build waveshaper table using Chebyshev polynomials
    var shaper_buf = Buffer.alloc(s, 1024, 1);
    shaper_buf.chebyMsg([0.3, 0.7, 0.2, 0.1, 0.05], true);

    sig    = SinOsc.ar(freq);
    shaped = Shaper.ar(shaper_buf, sig * shape);
    sig    = XFade2.ar(sig, shaped, shape.linlin(0, 1, -1, 1));
    sig    = RLPF.ar(sig, freq * 3.5, 0.5);

    // Stereo via Haas
    var haas = DelayN.ar(sig, 0.03, 0.010);
    sig = FreeVerb2.ar(sig, haas, mix: 0.25, room: 0.55, damp: 0.45);

    env = EnvGen.ar(Env.adsr(0.05, 0.1, 0.75, 0.5), gate, doneAction: 2);
    Out.ar(0, Balance2.ar(sig[0], sig[1], pan) * env * amp);
}).add;
```

### Ring Modulation / AM (metallic, robotic, sideband tones)
```supercollider
SynthDef(\sa_ring_mod, {
    arg freq = 440, amp = 0.3, gate = 1, pan = 0,
        mod_freq = 117, mix = 0.5;
    var carrier, modulator, ring, sig, env;

    carrier  = Saw.ar(freq);
    modulator = SinOsc.ar(mod_freq);

    // Ring modulation: (carrier × modulator) → sum & difference sidebands
    ring = carrier * modulator;

    // Mix dry and ring-modulated
    sig = XFade2.ar(carrier, ring, mix.linlin(0, 1, -1, 1));
    sig = RLPF.ar(sig, (freq + mod_freq) * 1.5, 0.5);
    sig = FreeVerb2.ar(sig, DelayN.ar(sig, 0.03, 0.012),
          mix: 0.3, room: 0.6, damp: 0.4);

    env = EnvGen.ar(Env.adsr(0.01, 0.1, 0.7, 0.4), gate, doneAction: 2);
    Out.ar(0, Balance2.ar(sig[0], sig[1], pan) * env * amp);
}).add;
```

### Frequency Shift (inharmonic timbres, alien quality)
```supercollider
SynthDef(\sa_freqshift_pad, {
    arg freq = 220, amp = 0.2, gate = 1, pan = 0, shift = 12.5;
    var sigs, sig, env;

    sigs = [Saw.ar(freq * 1.0), Saw.ar(freq * 1.002)];
    sigs = Splay.ar(sigs);
    sigs = RLPF.ar(sigs, 2000, 0.5);

    // Frequency shift L/R differently for stereo movement
    sig = [FreqShift.ar(sigs[0], shift * 0.7),
           FreqShift.ar(sigs[1], shift * -0.5)];
    sig = [sig[0] + (sigs[0] * 0.5), sig[1] + (sigs[1] * 0.5)];
    sig = FreeVerb2.ar(sig[0], sig[1], mix: 0.45, room: 0.8, damp: 0.3);

    env = EnvGen.ar(Env.adsr(1.0, 0.2, 0.85, 2.0), gate, doneAction: 2);
    Out.ar(0, Balance2.ar(sig[0], sig[1], pan) * env * amp);
}).add;
```

### Lo-Fi / Bitcrushed (degraded digital texture)
```supercollider
SynthDef(\sa_lofi, {
    arg freq = 440, amp = 0.35, gate = 1, pan = 0,
        bit_depth = 6, crush_freq = 11025;
    var sig, crushed, env;

    sig = VarSaw.ar(freq, 0, 0.3) + VarSaw.ar(freq * 1.004, 0, 0.7, 0.5);
    sig = RLPF.ar(sig, 2500, 0.4);

    // Bit crush: quantize to n bits, downsample
    crushed = Decimator.ar(sig, crush_freq, bit_depth.round.asInteger);
    sig = XFade2.ar(sig, crushed, 0.4);  // blend crushed with clean

    // Subtle chorus to widen the lo-fi
    sig = sig + [
        DelayC.ar(sig, 0.02, LFNoise1.kr(1.1).range(0.004, 0.012)) * 0.3,
        DelayC.ar(sig, 0.02, LFNoise1.kr(0.9).range(0.006, 0.016)) * 0.3
    ];

    env = EnvGen.ar(Env.adsr(0.01, 0.1, 0.75, 0.4), gate, doneAction: 2);
    Out.ar(0, Balance2.ar(sig[0], sig[1], pan) * env * amp);
}).add;
```

### Mapping Layer 1 Features to Spectral/Waveshaping

| Feature | Mapping |
|---------|---------|
| `timescale == "static"` | `PV_MagFreeze` with freeze=1 for held spectral snapshot |
| `timescale == "fast-evolving"` | `PV_RandComb` retriggered at beat rate |
| `fm_index > 3.0` | Ring modulation with `mod_freq = freq * fm_index * 0.3` |
| `noise_level > 0.4` | Add `Decimator` or `WhiteNoise` component |
| `spectral_centroid > 4000 Hz` | `FreqShift` upward by 50–200 Hz for airy shimmer |
| `hpss_harmonic_ratio < 0.5` | Use spectral smear + comb; embrace inharmonic quality |
| `rt60 > 1.5 s` | Source signal into PV_MagFreeze; extend reverb tail |
| `stereo_width > 0.7` | Different `FreqShift` amounts L vs R; Splay wide |
