---
title: Percussion Synthesis in SuperCollider (Kick, Snare, Hi-hat, Cymbal, Clap, Rim)
category: percussion
tags: [drums, kick, snare, hihat, cymbal, clap, rimshot, percussion, rhythm]
---

## Percussion Synthesis in SuperCollider

Synthesize drums and percussion entirely from UGens — no samples needed.
Use the **Drum Grid** supplied in the user prompt to schedule exact onset times.
Always keep percussion **mono** via `Pan2.ar(sig, 0)` unless noted.

### Scheduling Hits from the Grid
```supercollider
// Grid: |X...|.X..|..X.|...X|
// step_dur = beat / 4  (= 60 / bpm / 4)
fork {
    var onset_times = [0.0, 1.25, 2.5, 3.75] * step_dur; // example
    onset_times.do { |t|
        var now = 0; // tracker
        (t - now).wait;
        Synth(\sa_kick, [freq: 60]);
        now = t;
    };
};
```

---

### Kick Drum (sine sweep + noise click)
```supercollider
SynthDef(\sa_kick, {
    arg amp = 0.7, freq = 60, decay = 0.45, click = 0.08;
    var pitch, sig, env, click_sig;

    // Pitch sweep: high→low for sub-punch
    pitch = XLine.kr(freq * 3.5, freq, 0.06);
    sig   = SinOsc.ar(pitch);
    env   = EnvGen.ar(Env([0, 1, 0.4, 0], [0.001, 0.06, decay]), doneAction: 2);

    // Transient click for attack
    click_sig = WhiteNoise.ar(click) * EnvGen.ar(Env.perc(0.0005, 0.015));

    sig = (sig * env) + click_sig;
    sig = sig.tanh;                // soft clip to avoid digital clipping
    Out.ar(0, Pan2.ar(sig * amp, 0));
}).add;
```

### Deep Sub-Kick (808-style)
```supercollider
SynthDef(\sa_kick_808, {
    arg amp = 0.6, freq = 50, decay = 0.9, pitch_env = 0.25;
    var pitch, sig, env;

    pitch = XLine.kr(freq * 4.0, freq, pitch_env);
    sig   = SinOsc.ar(pitch);
    env   = EnvGen.ar(Env([0, 1, 0], [0.001, decay]), doneAction: 2);
    Out.ar(0, Pan2.ar((sig * env * amp).tanh, 0));
}).add;
```

### Snare (noise band + tonal body)
```supercollider
SynthDef(\sa_snare, {
    arg amp = 0.5, decay = 0.18, tone = 200, snap = 0.6;
    var body, noise, sig, env_b, env_n;

    // Tonal body (two-tone ringing)
    env_b = EnvGen.ar(Env.perc(0.001, decay * 0.5));
    body  = (SinOsc.ar(tone) + SinOsc.ar(tone * 1.52)) * env_b * 0.4;

    // Snappy noise (filtered white noise)
    env_n = EnvGen.ar(Env([0, 1, 0.5, 0], [0.001, decay * snap, decay * (1 - snap)]),
            doneAction: 2);
    noise = BPF.ar(WhiteNoise.ar, 3500, 0.7) * env_n;

    sig = (body + noise) * amp;
    Out.ar(0, Pan2.ar(sig, 0));
}).add;
```

### Rimshot
```supercollider
SynthDef(\sa_rimshot, {
    arg amp = 0.4, decay = 0.06;
    var sig, env;

    env = EnvGen.ar(Env.perc(0.001, decay), doneAction: 2);
    sig = (SinOsc.ar(1200) + BPF.ar(WhiteNoise.ar, 5000, 0.5)) * env;
    Out.ar(0, Pan2.ar(sig * amp, 0));
}).add;
```

### Closed Hi-hat (HPF noise burst)
```supercollider
SynthDef(\sa_hat_closed, {
    arg amp = 0.3, decay = 0.06;
    var sig, env;

    env = EnvGen.ar(Env.perc(0.0005, decay), doneAction: 2);
    // Multiple BPF bands simulating metallic resonance
    sig = Mix([
        BPF.ar(WhiteNoise.ar, 8000, 0.3, 1.0),
        BPF.ar(WhiteNoise.ar, 12000, 0.4, 0.5),
        BPF.ar(WhiteNoise.ar, 5500, 0.2, 0.3)
    ]);
    sig = HPF.ar(sig, 5000) * env;
    Out.ar(0, Pan2.ar(sig * amp, 0));
}).add;
```

### Open Hi-hat (longer decay)
```supercollider
SynthDef(\sa_hat_open, {
    arg amp = 0.28, decay = 0.35;
    var sig, env;

    env = EnvGen.ar(Env.perc(0.001, decay), doneAction: 2);
    sig = Mix([
        BPF.ar(WhiteNoise.ar, 9000, 0.35, 0.9),
        BPF.ar(WhiteNoise.ar, 13000, 0.45, 0.45),
        BPF.ar(WhiteNoise.ar, 6000, 0.2, 0.25)
    ]);
    sig = HPF.ar(sig, 4500) * env;
    // Slightly wider panning for open hat
    Out.ar(0, Pan2.ar(sig * amp, 0.3));
}).add;
```

### Cymbal / Crash (dense metallic inharmonics)
```supercollider
SynthDef(\sa_cymbal, {
    arg amp = 0.35, decay = 1.8;
    var freqs, sig, env;

    // Inharmonic partial set for cymbal character
    freqs = [205, 318, 435, 701, 912, 1230, 1680, 2100, 2890, 3540];
    sig = Mix(freqs.collect { |f, i|
        SinOsc.ar(f * LFNoise1.kr(0.03).range(0.998, 1.002)) *
            EnvGen.ar(Env.perc(0.001, decay * (0.5 + (i * 0.06))))
    }) * 0.035;
    sig = sig + (HPF.ar(WhiteNoise.ar(0.04), 4000) *
        EnvGen.ar(Env.perc(0.001, decay * 0.4)));
    sig = FreeVerb2.ar(sig, sig * 0.8, mix: 0.3, room: 0.6, damp: 0.35);

    env = EnvGen.ar(Env.perc(0.001, decay), doneAction: 2);
    Out.ar(0, Balance2.ar(sig[0], sig[1], 0) * amp);
}).add;
```

### Clap (layered noise bursts)
```supercollider
SynthDef(\sa_clap, {
    arg amp = 0.45;
    var pre, body, sig;

    // Pre-hits (multiple brief bursts = hand cupping effect)
    pre  = Mix(Array.fill(4, { |i|
        WhiteNoise.ar * EnvGen.ar(Env.perc(0.001, 0.012),
            Impulse.ar(0, 1 - (i * 0.025)))
    }));
    // Main body
    body = BPF.ar(WhiteNoise.ar, 1800, 0.8) *
        EnvGen.ar(Env.perc(0.001, 0.14), doneAction: 2);
    sig = (pre * 0.3 + body) * amp;
    Out.ar(0, Pan2.ar(sig, 0));
}).add;
```

### Tom (pitched membrane)
```supercollider
SynthDef(\sa_tom, {
    arg amp = 0.5, freq = 120, decay = 0.35;
    var pitch, body, noise, sig, env_b, env_n;

    pitch = XLine.kr(freq * 2.0, freq, 0.04);
    env_b = EnvGen.ar(Env.perc(0.001, decay));
    body  = SinOsc.ar(pitch) * env_b;

    env_n = EnvGen.ar(Env.perc(0.001, decay * 0.3), doneAction: 2);
    noise = HPF.ar(WhiteNoise.ar, 1000) * env_n * 0.2;

    sig = (body + noise) * amp;
    Out.ar(0, Pan2.ar(sig, 0));
}).add;
```

### Percussion Parameter Guidelines

| Parameter | Kick | Snare | Hi-hat | Cymbal |
|-----------|------|-------|--------|--------|
| Base freq | 50–80 Hz | 180–250 Hz | 5–9 kHz | 200–3500 Hz (inharmonics) |
| Decay | 0.3–0.9 s | 0.08–0.25 s | 0.03–0.08 s (closed) | 1.0–2.5 s |
| Noise | ≤5% | 40–60% | 80–100% | 50–70% |

### Mapping Layer 1 Drum Grid to Rhythm
- Each 4-char block = 1 beat; `X` = trigger, `.` = rest
- Convert step index → onset time: `onset = step_index * (beat / 4)`
- In `fork{}`, sort onsets and schedule with successive `.wait` calls
