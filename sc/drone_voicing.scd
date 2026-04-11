// ══════════════════════════════════════════════════════════════════
//  MaToMa drone_voicing.scd — ドローン・ボイシング制御 v1
//
//  【美学的立脚点】
//    Tim Hecker（層状持続音・霧の中の和声・制御された崩壊）×
//    OPN（記憶考古学的音色変容・粒子化）
//
//  【RAGコードからの変更点】
//    sa_cluster_pad の固定比率配列から
//    → Scale.degreeToKey による調性制約付き動的ボイシングへ変更
//    各音に独立LFOデチューン（0.07〜0.05Hz）で浮遊感
//
//  【ボイシングプリセット】
//    close:   [0, 2, 4]    — 密集コード（濃厚・緊張）
//    open:    [0, 4, 7]    — 開いた響き（澄んだ・空間的）
//    cluster: [0, 1, 2, 5] — 半音クラスター（緊張・現代的）
//    wide:    [0, 7, 14]   — 2オクターブ開放（広大・崇高）
//
//  【OSCアドレス】(port 57200)
//    /matoma/drone/voicing/start [voicingKey]  → ドローン開始
//    /matoma/drone/voicing/stop                → フェードアウト停止
//    /matoma/drone/voicing/set   [voicingKey]  → ボイシング変更（クロスフェード）
//    /matoma/drone/voicing/key   [midiNote]    → ルートキー変更
//
//  【Pdef パターン】(必要に応じて .play で起動)
//    Pdef(\drone)      → 静的ボイシングの持続ドローン（dur:999）
//    Pdef(\stackDrone) → strum:2.0 で音を積み重ねるレイヤー
// ══════════════════════════════════════════════════════════════════

// ── SynthDef ─────────────────────────────────────────────────────
SynthDef(\matoma_drone_pad, {
    arg freq    = 220,
        amp     = 0.25,
        gate    = 1,
        atk     = 5.0,
        rel     = 8.0,
        cutoff  = 900,
        pan     = 0.0;

    // var 宣言（SC: すべての var は関数先頭に置く必要あり）
    var detune1, detune2, osc1, osc2, sub, sig, wet, env;

    // 独立 LFO デチューン: 各音が微妙にずれて浮遊感を生む
    detune1 = LFNoise1.kr(0.07).range(-0.4, 0.4);
    detune2 = LFNoise1.kr(0.05).range(-0.6, 0.6);

    osc1 = LFTri.ar(freq + detune1);
    osc2 = LFTri.ar(freq * 1.0019 + detune2);  // わずかにピッチずれ
    sub  = SinOsc.ar(freq * 0.5) * 0.18;        // サブオクターブで低域補強

    sig = (osc1 + osc2 + sub) * 0.38;
    sig = tanh(sig * 1.2) * 0.83;               // 温かみのサチュレーション（正規化済み）
    sig = RLPF.ar(sig, cutoff.clip(200, 4000), 0.6);

    // GVerb: revtime:12, roomsize:100 — knowledge.md 確認済みの長残響
    wet = GVerb.ar(
        sig,
        roomsize: 100,
        revtime:  12,
        damping:  0.2,
        inputbw:  0.8,
        mul:      0.4
    );
    sig = (sig + wet) * 0.5;

    env = EnvGen.kr(Env.asr(atk, 1.0, rel), gate, doneAction: 2);
    Out.ar(0, Pan2.ar(sig * amp * env, pan));
}).add;

// ── 状態変数 ─────────────────────────────────────────────────────
~harm = (
    root:    48,               // C3 (MIDI 48)
    scale:   Scale.dorian,
    degree:  0,                // スケール基点（0 = ルート）
    voicings: (
        close:   [0, 2, 4],    // 密集: ルート・短3度・5度
        open:    [0, 4, 7],    // 開放: ルート・5度・オクターブ
        cluster: [0, 1, 2, 5], // クラスター: 隣接音+6度
        wide:    [0, 7, 14]    // 広大: ルート・1oct・2oct
    ),
    current: \open
);

~dronePadSynths = [];

// ── ボイシング → 周波数配列変換 ──────────────────────────────────
// スケール度数 → MIDI ノート → Hz に変換する
~chordFromVoicing = { |voicingKey|
    var v, scaleSize, degrees;
    v         = ~harm.voicings[voicingKey];
    scaleSize = ~harm.scale.degrees.size;  // Dorian = 7
    degrees   = v.collect({ |offset| ~harm.degree + offset });
    degrees.collect({ |d|
        var scaleDeg, octave, semitones;
        scaleDeg  = d % scaleSize;
        octave    = (d / scaleSize).floor.asInteger;
        semitones = ~harm.scale.degreeToKey(scaleDeg);
        (~harm.root + semitones + (octave * 12)).midicps
    });
};

// ── ヘルパー: ドローン開始 ────────────────────────────────────────
~startDronePad = { |voicingKey = \open|
    var freqs, pans;
    freqs = ~chordFromVoicing.(voicingKey);
    pans  = [-0.3, 0.0, 0.3, -0.15];      // 最大4音のパンニング
    ~harm.current = voicingKey;
    ~dronePadSynths.do({ |s| s.set(\gate, 0) });  // 既存をフェードアウト
    ~dronePadSynths = freqs.collect({ |f, i|
        Synth(\matoma_drone_pad,
            [\freq, f, \amp, 0.25, \atk, 5.0, \gate, 1, \pan, pans.wrapAt(i)],
            addAction: \addToTail)
    });
    "ドローンパッド開始: % (%音, %Hz...)".format(
        voicingKey, freqs.size, freqs[0].round(0.1)).postln;
};

// ── ヘルパー: ボイシング変更（クロスフェード）────────────────────
// 新しい Synth を atk=4s でフェードイン、旧 Synth を rel=8s でフェードアウト
~setVoicing = { |voicingKey|
    var old, freqs, pans;
    old   = ~dronePadSynths.copy;
    freqs = ~chordFromVoicing.(voicingKey);
    pans  = [-0.3, 0.0, 0.3, -0.15];
    ~harm.current = voicingKey;
    ~dronePadSynths = freqs.collect({ |f, i|
        Synth(\matoma_drone_pad,
            [\freq, f, \amp, 0.25, \atk, 4.0, \gate, 1, \pan, pans.wrapAt(i)],
            addAction: \addToTail)
    });
    old.do({ |s| s.set(\gate, 0) });  // 旧 Synth: rel=8s でフェードアウト
    "ボイシング変更: %".format(voicingKey).postln;
};

// ── ヘルパー: ドローン停止 ────────────────────────────────────────
~stopDronePad = {
    Pdef(\drone).stop;
    Pdef(\stackDrone).stop;
    ~dronePadSynths.do({ |s| s.set(\gate, 0) });
    ~dronePadSynths = [];
    "ドローンパッド停止（rel=8s フェードアウト）".postln;
};

// ── Pdef パターン ─────────────────────────────────────────────────
// 基本ドローン: 現在のボイシングを999拍持続させる
Pdef(\drone, Pbind(
    \instrument, \matoma_drone_pad,
    \freq,    Pfunc { ~chordFromVoicing.(~harm.current) },
    \amp,     0.25,
    \dur,     999,
    \sustain, 998
));

// スタック・ドローン: strum=2拍でゆっくり積み重ね
Pdef(\stackDrone, Pbind(
    \instrument, \matoma_drone_pad,
    \freq,    Pfunc { ~chordFromVoicing.(~harm.current) },
    \amp,     0.2,
    \dur,     Pseq([8, 8, 8, 8], inf),
    \sustain, 7,
    \strum,   2.0
));

// ── OSCdef: ドローン開始 ─────────────────────────────────────────
OSCdef(\matoma_drone_voicing_start, { |msg|
    var key     = if (msg.size > 1) { msg[1].asSymbol } { \open };
    var allowed = #[\close, \open, \cluster, \wide];
    {
        if (allowed.includes(key).not) { key = \open };
        ~startDronePad.(key);
    }.defer;
}, '/matoma/drone/voicing/start', nil, 57200);

// ── OSCdef: ドローン停止 ─────────────────────────────────────────
OSCdef(\matoma_drone_voicing_stop, { |msg|
    { ~stopDronePad.(); }.defer;
}, '/matoma/drone/voicing/stop', nil, 57200);

// ── OSCdef: ボイシング変更 ────────────────────────────────────────
OSCdef(\matoma_drone_voicing_set, { |msg|
    var key     = msg[1].asSymbol;
    var allowed = #[\close, \open, \cluster, \wide];
    {
        if (allowed.includes(key)) {
            ~setVoicing.(key);
        } {
            "ドローンボイシング: 不正なキー '%'（close/open/cluster/wide）".format(key).postln;
        };
    }.defer;
}, '/matoma/drone/voicing/set', nil, 57200);

// ── OSCdef: ルートキー変更 ────────────────────────────────────────
// midiNote: 24(C1)〜72(C5)
OSCdef(\matoma_drone_voicing_key, { |msg|
    var midiNote = msg[1].asInteger.clip(24, 72);
    {
        ~harm.root = midiNote;
        if (~dronePadSynths.size > 0) {
            ~setVoicing.(~harm.current);  // 新しいキーで Synth を再構成
        };
        "ルートキー変更: MIDI % (%.freq: %Hz)".format(
            midiNote, midiNote, midiNote.midicps.round(0.1)).postln;
    }.defer;
}, '/matoma/drone/voicing/key', nil, 57200);

"ドローン・ボイシング (\\matoma_drone_pad) ロード完了".postln;
