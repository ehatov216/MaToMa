# SuperCollider SynthDef Knowledge Base

## Synth Categories

### 1. Melodic Synths

#### Subtractive Standard
```supercollider
(
SynthDef(\sa_melodic_sub, {
    arg out=0, freq=440, amp=0.5, gate=1, brightness=0.5, timbreVec=#[0,0,0,0];
    var sig, env;
    env = EnvGen.kr(Env.adsr(0.01, 0.2, 0.6, 0.1), gate, doneAction: 2);
    sig = VarSaw.ar(freq, 0, timbreVec[0].linlin(0, 1, 0.1, 0.9));
    sig = MoogFF.ar(sig, freq * (1 + (brightness * 8)), timbreVec[1] * 2);
    Out.ar(out, Pan2.ar(sig * env * amp));
}).add;
)
```

#### FM Simple
```supercollider
(
SynthDef(\sa_melodic_fm, {
    arg out=0, freq=440, amp=0.5, gate=1, brightness=0.5, timbreVec=#[0,0,0,0];
    var sig, env, mod;
    env = EnvGen.kr(Env.perc(0.01, 0.4), gate, doneAction: 2);
    mod = SinOsc.ar(freq * (1 + timbreVec[0]), 0, freq * brightness * 5);
    sig = SinOsc.ar(freq + mod);
    Out.ar(out, Pan2.ar(sig * env * amp));
}).add;
)
```

### 2. Bass Synths

#### Aggressive Bass
```supercollider
(
SynthDef(\sa_bass_heavy, {
    arg out=0, freq=50, amp=0.5, gate=1, brightness=0.5, timbreVec=#[0,0,0,0];
    var sig, env;
    env = EnvGen.kr(Env.adsr(0.05, 0.1, 0.5, 0.2), gate, doneAction: 2);
    sig = LFSaw.ar(freq) + LFPulse.ar(freq * 0.5, 0, timbreVec[0]);
    sig = RLPF.ar(sig, freq * (1 + (brightness * 5)), 0.3);
    sig = (sig * (1 + (timbreVec[1] * 10))).distort;
    Out.ar(out, Pan2.ar(sig * env * amp * 0.5));
}).add;
)
```
