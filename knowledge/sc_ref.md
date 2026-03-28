# SuperCollider SynthDef Design Guidelines

## 1. Interface Requirements

すべての SynthDef は、動的な音色制御と自動最適化を可能にするために、以下の引数（Control Names）を実装しなければなりません。

| Argument | Description | Default | Range |
|----------|-------------|---------|-------|
| `freq` | 基本周波数 (Hz) | 440 | 20 - 20000 |
| `amp` | 振幅 (0.0 - 1.0) | 0.5 | 0.0 - 1.0 |
| `gate` | エンベロープ制御 (1=on, 0=off) | 1 | 0 または 1 |
| `brightness` | 倍音の明るさ (Spectral Centroid) | 0.5 | 0.0 - 1.0 |
| `noisiness` | ノイズ成分の割合 | 0.1 | 0.0 - 1.0 |
| `timbreVec` | 音色キャラクター (Array [4]) | `[0,0,0,0]`| -1.0 - 1.0 |

## 2. Example Template

```supercollider
(
SynthDef(\sa_base, {
    arg out=0, freq=440, amp=0.5, gate=1, 
        brightness=0.5, noisiness=0.1, timbreVec=#[0,0,0,0],
        pan=0;
    
    var sig, env, filterFreq, noise;
    
    // Envelope
    env = EnvGen.kr(Env.adsr(0.01, 0.3, 0.5, 0.1), gate, doneAction: 2);
    
    // Oscillators influenced by timbreVec
    sig = Saw.ar(freq * [1, 1.001 + (timbreVec[0] * 0.01)]);
    sig = sig + SinOsc.ar(freq * 0.5, 0, timbreVec[1] * 0.5);
    
    // Filtering based on brightness
    filterFreq = freq * (1 + (brightness * 10));
    sig = LPF.ar(sig, filterFreq.clip(20, 20000));
    
    // Noise integration
    noise = WhiteNoise.ar(noisiness);
    sig = (sig * (1 - noisiness)) + (noise * noisiness);
    
    Out.ar(out, Pan2.ar(sig * env * amp, pan));
}).add;
)
```

## 3. Best Practices
- **FM/AM**: 音色の複雑さを出すために積極的な変調を使用すること。
- **Normalization**: 入力パラメーターは 0.0 - 1.0 にスケーリングすること。
- **Stereo**: 常にステレオ（Pan2）で出力すること。

## 4. Sonic Anatomy Project Synths

Sonic Anatomy では、以下の project synth が中核的な役割を果たします。

### sa_bass − ベース音
- **Role**: Low frequency foundation (20-200 Hz)
- **Routing**: Direct → SuperDirt bus (typically `out` arg = 0)
- **Key Parameters**:
  - `freq`: Fundamental from MIDI or analysis (default 55 Hz)
  - `cutoff`: VCF frequency (default 1000)
  - `resonance`: Q factor of filter (default 2.0)
  - `glide`: Portamento time in seconds (default 0)
  - `amp`: Output level (0.0-1.0)

### sa_drums − パーカッション
- **Role**: Rhythmic transients and percussion (50-8000 Hz)
- **Key Parameters**:
  - `attack`: Envelope attack time (0.001-0.3)
  - `sustain`: Sustain level (0.0-1.0)
  - `decay`: Decay time (0.01-2.0)
  - `pitch_mod`: FM depth for tonal variation
- **Note**: 常に short envelope、低持続性

### sa_lead − メロディライン
- **Role**: Melodic lead voice (200-4000 Hz)
- **Key Parameters**:
  - `freq`: MIDI pitch or analysis result
  - `brightness`: Spectral centroid control
  - `vibrato_rate`: LFO modulation (0-10 Hz)
  - `vibrato_depth`: Modulation amount (0.0-50 cents)

### sa_master − マスター処理
- **Role**: Mixing and FX bus (receives all stems)
- **Processing Chain**:
  1. Input mixing (drums + bass + lead)
  2. Compression (optional, Constitution VII: local-first)
  3. Limiting to prevent clipping
  4. Stereo bus out

## 5. TidalCycles Cross-Reference

SuperCollider synths と TidalCycles の連携方法。

### Synth Triggering from TidalCycles
```haskell
-- Set SuperCollider synth parameters from Tidal
d1 $ s "sa_lead" # n "0 7 12 5" # cutoff "1000 1500 800"
d2 $ s "sa_bass" # freq "55 110" # glide "0.1"
```

**TranslationMapping**:
| TidalCycles Param | SC SynthDef Arg | Example |
|------------------|----------------|---------|
| `n` (pitch) | `freq` | `n "0 7 12"` → freq 440 Hz basis |
| Custom string | Direct control | `cutoff "1000 1500"` |
| `amp` | `amp` | Global amplitude |
| `legato` | `gate` / `glide` | Portamento behavior |

### Routing Best Practices
- Use SuperDirt's OSC bus mapping for low latency
- Each synth defined with `out=0` (SuperDirt bus)
- Always respond to `gate` for note-off (Constitution VII)

## 6. Common NG Patterns

SC コード生成時によくある間違い（anti-patterns）。

### ❌ NG Pattern 1: Superfluous SC Notation in TidalCycles
```haskell
-- WRONG: SinOsc notation in Tidal
d1 $ s "SinOsc" # freq "440"

-- CORRECT: Use synth name
d1 $ s "sa_lead" # n "0"
```

### ❌ NG Pattern 2: MIDI Number ↔ Frequency Confusion
```supercollider
// WRONG: MIDI note as frequency
SinOsc.ar(60, 0, 0.1)  // Expects Hz, not MIDI!

// CORRECT: Convert MIDI to freq
freq = (60 - 69).midicps  // ~261 Hz
SinOsc.ar(freq, 0, 0.1)
```

### ❌ NG Pattern 3: BPM/CPS Mismatch
```haskell
-- WRONG: Confusing tempo units
setcps(120)  -- BPM, not CPS!

-- CORRECT: Use CPS (cycles per second)
setcps(2)  -- 2 beats per second = 120 BPM
```

### ❌ NG Pattern 4: gate Parameter Ignored
```supercollider
// WRONG: No response to gate
SynthDef(\broken, {
    arg freq=440, amp=0.5, gate=1;  // gate defined but...
    var sig = SinOsc.ar(freq) * amp;
    Out.ar(0, sig);  // Never stops!
}).add;

// CORRECT: Use gate for note-off
SynthDef(\correct, {
    arg freq=440, amp=0.5, gate=1;
    var env = EnvGen.kr(Env.adsr(0.01, 0.1, 0.5, 0.1), 
                        gate, doneAction: 2);
    var sig = SinOsc.ar(freq) * env * amp;
    Out.ar(0, sig);
}).add;
```

### ❌ NG Pattern 5: Hardcoded out Bus
```supercollider
// WRONG: Bus hardcoded
Out.ar(0, signal)

// CORRECT: Use out argument (SuperDirt compatible)
arg out=0;
Out.ar(out, signal);
```

### ✅ Debugging Checklist
- [ ] All SynthDefs accept `out` argument
- [ ] All SynthDefs respond to `gate` with `doneAction: 2`
- [ ] Frequencies are in Hz, not MIDI numbers
- [ ] ADSR envelope times are reasonable (< 2 seconds typically)
- [ ] Output routed via `Pan2.ar()` for stereo
- [ ] No CPU-intensive operations in real-time loop

---

## 8. Granular Synthesis

Granular synthesis slices audio into short grains (10–100 ms) and
reassembles them to create textures and evolving timbres.

### Key UGens

| UGen | Purpose |
|------|---------|
| `TGrains.ar(numCh, trig, buf, rate, pos, dur, pan, amp)` | Triggered grain generator from buffer |
| `GrainBuf.ar(numCh, trig, dur, buf, rate, pos, interp, pan)` | Grain with Hann envelope from buffer |
| `GrainSin.ar(numCh, trig, dur, freq, pan, amp)` | Sine-based grain (no buffer needed) |
| `Dust.ar(density)` | Random trigger for cloud-like grain density |

### Stereo Granular Pad
```supercollider
SynthDef(\sa_granular_pad, {
    arg buf = 0, amp = 0.3, gate = 1,
        grainRate = 15, grainDur = 0.08, posSpeed = 0.03;
    var pos, trig, sig, env;
    pos  = LFSaw.kr(posSpeed).range(0, 1);
    trig = Impulse.ar(grainRate + LFNoise1.kr(2).range(-3, 3));
    sig  = GrainBuf.ar(2, trig, grainDur, buf, 1.0, pos, 2,
               LFNoise1.kr(1).range(-0.7, 0.7));
    env  = EnvGen.ar(Env.adsr(1.5, 0.1, 0.9, 2.0), gate, doneAction: 2);
    Out.ar(0, sig * env * amp);
}).add;
```

### Granular Tips
- **Grain rate 8–20 Hz**: smooth continuous cloud texture.
- **Grain rate 1–6 Hz**: audible individual grains (choppy / rhythmic).
- **`posSpeed` ≈ 0**: freeze position → drone/pad.
- **Random `pan` per grain**: wide stereo image without extra processing.

---

## 9. Wavetable Synthesis

Wavetable synthesis reads one cycle of a waveform stored in a buffer,
enabling smooth timbral morphing by interpolating between tables.

### Key UGens

| UGen | Purpose |
|------|---------|
| `Osc.ar(buf, freq)` | Single wavetable oscillator |
| `OscN.ar(buf, freq)` | Non-interpolating (cheaper CPU) |
| `VOsc.ar(bufpos, freq)` | Vector oscillator — interpolates between adjacent buffers |
| `VOsc3.ar(bufpos, freq, freqB, freqC)` | Three-oscillator vector synthesis |

### Building a Wavetable
```supercollider
~sig   = Signal.fill(512, { |i| sin(2pi * i / 512) });  // one cycle
~wt    = ~sig.asWavetable;                               // SC internal format
~wtBuf = Buffer.alloc(s, 1024, 1);                       // size × 2 !
~wtBuf.loadCollection(~wt);
s.sync;
```

### Morphing Wavetable Pad (VOsc)
```supercollider
SynthDef(\sa_wt_morph, {
    arg buf = 0, freq = 440, amp = 0.25, gate = 1,
        morphRate = 0.2, cutoff = 1800, pan = 0;
    var pos, sigs, sig, env;
    pos  = SinOsc.kr(morphRate).range(buf, buf + 1);  // morph between buf and buf+1
    sigs = [VOsc.ar(pos, freq * 1.005), VOsc.ar(pos, freq), VOsc.ar(pos, freq * 0.995)];
    sig  = Splay.ar(sigs);
    sig  = RLPF.ar(sig, cutoff + (SinOsc.kr(0.4) * 400), 0.5);
    sig  = FreeVerb2.ar(sig[0], sig[1], mix: 0.3, room: 0.6);
    env  = EnvGen.ar(Env.adsr(0.3, 0.1, 0.8, 0.8), gate, doneAction: 2);
    Out.ar(0, Balance2.ar(sig[0], sig[1], pan) * env * amp);
}).add;
```

### Wavetable Tips
- Buffer size **must be power-of-2**; `asWavetable` doubles the size (512 → 1024).
- `VOsc` requires adjacent buffer numbers of equal size.
- Slow morph (0.1–0.5 Hz) → evolving pad; fast morph (2–10 Hz) → timbral vibrato.
- Combine 5 detuned `VOsc` voices with `Splay.ar` for a rich stereo pad.
