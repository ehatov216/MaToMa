/*
MaToMa: 5種類のドローンジェネレーター
================================================================
【概要】
  GitHubオープンソースから取り込んだ5種類のドローン合成手法。
  各ドローンは独立した SynthDef + OSCdef を持ち、同時に複数起動できる。
  このファイルは run_headless.scd の s.waitForBoot({}) 内で
  load() して使う（独自の waitForBoot ラッパーを持たない）。

【ドローン一覧】
  1. \matoma_drone_fm        — FM + グリッサンド（a_loss_of_self由来）
  2. \matoma_drone_noise     — 多声バンドパスノイズ（DroneCollider由来）
  3. \matoma_drone_wavetable — ウェーブテーブル + デグレード（SCgazer由来）
  4. \matoma_drone_feedback  — フィードバックネットワーク（rumush由来）
  5. \matoma_drone_sines     — 揺れるSinOsc雲（Meandering Sines由来）

【OSCアドレス】（ポート 57200）
  /matoma/drone/<type>/start   → 開始 (type: fm/noise/wavetable/feedback/sines)
  /matoma/drone/<type>/stop    → 停止（8〜10秒フェードアウト）
  /matoma/drone/<type>/param   → パラメーター更新 [名前] [値]
  /matoma/drone/all/stop       → 全ドローン停止

【共通パラメーター（全ドローン）】
  freq_norm : 0.0〜1.0 → 20〜300 Hz にマップ
  room      : 0.0〜1.0 → リバーブの広さ
  amp       : 0.0〜1.0 → 音量
  gate      : 1=持続、0=フェードアウト（直接送信可）
*/

// ════════════════════════════════════════════════════════════════
// STEP 0: ウェーブテーブルバッファ確保（Drone 3 用）
//
//   4種類の倍音構成を Buffer.sine1 で書き込む。
//   Osc.ar がこのバッファをウェーブテーブルとして読む。
//   asWavetable: true でSC内部のウェーブテーブル形式に変換。
// ════════════════════════════════════════════════════════════════

~droneWtBufs = Array.fill(4, { Buffer.alloc(s, 2048, 1) });
s.sync;

// 0: 奇数倍音優勢（中空管的・クラリネット質感）
~droneWtBufs[0].sine1([1.0, 0.0, 0.7, 0.0, 0.5, 0.0, 0.3, 0.0],
    normalize: true, asWavetable: true);
// 1: 低次倍音（偶数・奇数混在、温かいパッド感）
~droneWtBufs[1].sine1([1.0, 0.8, 0.3, 0.6, 0.1, 0.4],
    normalize: true, asWavetable: true);
// 2: 高次倍音まで広がる（金属的・明るい）
~droneWtBufs[2].sine1([1.0, 0.5, 0.8, 0.3, 0.6, 0.2, 0.7, 0.15],
    normalize: true, asWavetable: true);
// 3: 1/n^2 減衰（弦楽的・自然な倍音減衰）
~droneWtBufs[3].sine1([1.0, 0.25, 0.11, 0.063, 0.04, 0.028, 0.02, 0.016],
    normalize: true, asWavetable: true);
s.sync;

"ウェーブテーブルバッファ確保完了 (4種: bufs %)".format(
    ~droneWtBufs.collect(_.bufnum)).postln;

// ════════════════════════════════════════════════════════════════
// DRONE 1: FM + グリッサンド型
//
//   参照: github_drone_generators.md > a_loss_of_self
//   2オペレーターFM + 位相変調。
//   アタック時に XLine.ar でピッチが glide*freq → freq へ上昇。
//   Pluck.ar で弦共鳴を追加し、AmpCompA.kr で高音域を自然に補正。
//
//   パラメーター:
//     freq        : 基音 Hz (20〜300)
//     mod_index   : FM変調深さ (0〜6)
//     phase_mod   : 位相変調深さ (0〜3)
//     glide       : アタック時のグリッサンド比率 (0.8〜1.0)
//     pluck_mix   : Pluck共鳴のミックス量 (0〜0.6)
//     room / amp / gate
// ════════════════════════════════════════════════════════════════
SynthDef(\matoma_drone_fm, {
    arg freq      = 60,
        mod_index = 2.0,
        phase_mod = 1.5,
        glide     = 0.97,
        pluck_mix = 0.3,
        room      = 0.7,
        amp       = 0.3,
        gate      = 1;

    var mod, phasemod, carrier, pluck, sig, env;

    // FMモジュレーター（基音の半波 + アタック中にインデックスを0から引き上げ）
    mod      = SinOsc.ar(freq * 0.5, 0, Line.ar(0, mod_index * freq, 8.0));
    // 位相変調器
    phasemod = SinOsc.ar(freq, 0, phase_mod);
    // キャリア（XLine: glide*freq → freq のグリッサンド）
    carrier  = SinOsc.ar(XLine.ar(glide * freq, freq, 8.0) + mod, phasemod);

    // Pluck共鳴レイヤー（a_loss_of_self手法）
    pluck = Pluck.ar(carrier, PinkNoise.ar(), 0.2, freq.reciprocal, 48.0, 0.5);
    sig   = (carrier * 0.75) + (pluck * pluck_mix.clip(0, 0.6));

    sig = RLPF.ar(sig, (freq * 9.0).clip(200, 18000), 0.5);
    sig = tanh(sig * 1.2) * 0.7;
    // Resonz 胴鳴り感（a_loss_of_self: sig * 0.75 + Resonz * 1.125 手法）
    sig = (sig * 0.75) + (Resonz.ar(sig, freq, 0.15) * 0.9);
    // 聴覚補正（高音域を自然に圧縮）
    sig = sig * AmpCompA.kr(freq, 12.978271799373);
    sig = Compander.ar(sig, sig, 0.3, 0.5, 1, 0.001, 0.08);
    sig = sig.dup;

    env = EnvGen.ar(Env.adsr(6.0, 0.5, 0.85, 10.0), gate, doneAction: 2);
    sig = sig * env;

    Out.ar(~droneBus, sig);
    Out.ar(~effectBus, FreeVerb2.ar(sig[0], sig[1],
        mix:  room.linlin(0, 1, 0.40, 0.90),
        room: room.linlin(0, 1, 0.55, 0.95),
        damp: room.linlin(0, 1, 0.60, 0.10)) * 0.8);
    Out.ar(0, FreeVerb2.ar(sig[0], sig[1],
        mix:  room.linlin(0, 1, 0.40, 0.90),
        room: room.linlin(0, 1, 0.55, 0.95),
        damp: room.linlin(0, 1, 0.60, 0.10)) * amp);
}).add;

// ════════════════════════════════════════════════════════════════
// DRONE 2: 多声バンドパスノイズ型
//
//   参照: github_drone_generators.md > DroneCollider
//   8声のBPFフィルターWhiteNoiseをMixして倍音ノイズドローンを生成。
//   各ボイスは非整数倍音比率 × freq を中心周波数に持ち LFNoise1 で揺れる。
//   音量は 1/(i+0.8)^damp_exp で高次倍音ほど自然に下がる。
//
//   パラメーター:
//     freq      : 基音 Hz
//     filter_rq : バンドパスのQ逆数 (0.05〜0.4、小さいほど鋭い)
//     damp_exp  : 倍音減衰の指数 (0.5〜2.0)
//     detune    : 各ボイスの周波数ゆらぎ幅（±比率, 0〜0.05）
//     room / amp / gate
// ════════════════════════════════════════════════════════════════
SynthDef(\matoma_drone_noise, {
    arg freq      = 60,
        filter_rq = 0.15,
        damp_exp  = 1.2,
        detune    = 0.015,
        room      = 0.75,
        amp       = 0.28,
        gate      = 1;

    // 非整数倍音比率（DroneCollider手法: 整数倍音でない → 金属的でなく空気感）
    var ratios = [1.0, 1.502, 2.003, 3.006, 4.009, 5.402, 6.805, 8.011];
    var sig, env;

    sig = Mix.fill(8, { |i|
        var centerFreq   = freq * ratios[i];
        // LFNoise1でゆっくり揺れる中心周波数（rrandはSynthDef構築時に評価→声ごとに固定）
        var detunedFreq  = centerFreq * (1 + LFNoise1.kr(rrand(0.03, 0.12), detune));
        // 音量: 高次倍音ほど小さく（DroneCollider: (1/(i+offset))^kDamp）
        var vol          = (1.0 / (i + 0.8)).pow(damp_exp);
        Pan2.ar(
            BPF.ar(WhiteNoise.ar(), detunedFreq.clip(20, 18000), filter_rq) * vol,
            LFNoise1.kr(rrand(0.04, 0.18)).range(-0.75, 0.75)
        )
    });

    sig = HPF.ar(sig, 40);
    sig = LeakDC.ar(sig.tanh) * 3.5;  // 8声Mix後の音量補正

    env = EnvGen.ar(Env.adsr(5.0, 0.5, 0.9, 8.0), gate, doneAction: 2);
    sig = sig * env;

    Out.ar(~droneBus, sig);
    Out.ar(~effectBus, FreeVerb2.ar(sig[0], sig[1],
        mix:  room.linlin(0, 1, 0.50, 0.90),
        room: room.linlin(0, 1, 0.60, 0.95),
        damp: room.linlin(0, 1, 0.65, 0.10)) * 0.8);
    Out.ar(0, FreeVerb2.ar(sig[0], sig[1],
        mix:  room.linlin(0, 1, 0.50, 0.90),
        room: room.linlin(0, 1, 0.60, 0.95),
        damp: room.linlin(0, 1, 0.65, 0.10)) * amp);
}).add;

// ════════════════════════════════════════════════════════════════
// DRONE 3: ウェーブテーブル + デジタルデグレード型
//
//   参照: github_drone_generators.md > SCgazer (stjoernuithrott)
//   事前生成したウェーブテーブル (~droneWtBufs) を Osc.ar で読み、
//   Decimator でビット/サンプルレートを削減してデジタルグリッチを加える。
//   Select.kr で3種類のLFO波形をリアルタイム選択可能。
//
//   パラメーター:
//     freq     : 基音 Hz
//     buf0     : 主ウェーブテーブルのbufnum (OSC側から渡す)
//     buf1     : 副ウェーブテーブルのbufnum
//     detune   : デチューン量 (0〜0.01)
//     lfo_rate : LFO速度 Hz (0.01〜0.5)
//     lfo_type : LFO波形タイプ (0=LFCub, 1=LFTri, 2=LFSaw)
//     degrade  : デグレード量 (0=原音, 1=最大グリッチ)
//     room / amp / gate
// ════════════════════════════════════════════════════════════════
SynthDef(\matoma_drone_wavetable, {
    arg freq     = 60,
        buf0     = 0,
        buf1     = 0,
        detune   = 0.003,
        lfo_rate = 0.05,
        lfo_type = 0,
        degrade  = 0.0,
        room     = 0.65,
        amp      = 0.3,
        gate     = 1;

    var lfo, osc1, osc2, sig, degraded, env;

    // Select.kr でLFO波形タイプをランタイム選択（SCgazer手法）
    lfo = Select.kr(lfo_type.clip(0, 2), [
        LFCub.kr(lfo_rate),
        LFTri.kr(lfo_rate),
        LFSaw.kr(lfo_rate)
    ]);

    // 2基のOscオシレーター（デチューン + 5度上の副声）
    osc1 = Osc.ar(buf0, freq * (1 + (lfo * detune)));
    osc2 = Osc.ar(buf1, freq * 1.5 * (1 - (lfo * detune * 0.7)));
    sig  = (osc1 * 0.65) + (osc2 * 0.45);

    // RLPF: LFOでフィルターをゆっくり変調（Moogフィルター的）
    sig = RLPF.ar(sig,
        (freq * LFCub.kr(lfo_rate * 0.3).range(2.0, 8.0)).clip(80, 18000),
        0.35);

    // Decimator: デジタルデグレード（SCgazer: alias + redux）
    degraded = Decimator.ar(sig,
        s.sampleRate * degrade.linlin(0, 1, 1.0, 0.12).clip(0.05, 1.0),
        degrade.linlin(0, 1, 16, 6).clip(4, 16).round.asInteger);
    sig = XFade2.ar(sig, degraded, degrade.linlin(0, 1, -1, 1));
    sig = LeakDC.ar(sig.softclip).dup;

    env = EnvGen.ar(Env.adsr(4.0, 0.5, 0.88, 8.0), gate, doneAction: 2);
    sig = sig * env;

    Out.ar(~droneBus, sig);
    Out.ar(~effectBus, FreeVerb2.ar(sig[0], sig[1],
        mix:  room.linlin(0, 1, 0.35, 0.85),
        room: room.linlin(0, 1, 0.50, 0.92),
        damp: room.linlin(0, 1, 0.60, 0.15)) * 0.8);
    Out.ar(0, FreeVerb2.ar(sig[0], sig[1],
        mix:  room.linlin(0, 1, 0.35, 0.85),
        room: room.linlin(0, 1, 0.50, 0.92),
        damp: room.linlin(0, 1, 0.60, 0.15)) * amp);
}).add;

// ════════════════════════════════════════════════════════════════
// DRONE 4: フィードバックネットワーク型
//
//   参照: github_drone_generators.md > Feedback Ambient (rumush)
//   Saw波を LocalIn/LocalOut フィードバックループに入れ、
//   AllpassC × 2 + DelayC で倍音が自己組織化するドローンを生成。
//   PitchShift(pitchRatio<1.0)で微小なダウンシフトを加えて浮遊感を演出。
//   ビルトインUGenのみ使用（sc3-plugins不要）。
//
//   パラメーター:
//     freq       : 基音 Hz
//     feedback   : フィードバック量 (0〜0.85、0.7超から自己発振に近い)
//     drift_rate : 揺れの速さ (0.01〜0.5 Hz)
//     pitch_drop : 微小ピッチダウン量 (0=なし, 1=明確な下降)
//     room / amp / gate
// ════════════════════════════════════════════════════════════════
SynthDef(\matoma_drone_feedback, {
    arg freq       = 60,
        feedback   = 0.6,
        drift_rate = 0.07,
        pitch_drop = 0.3,
        room       = 0.8,
        amp        = 0.25,
        gate       = 1;

    var src, fb, loc, shifted, sig, env;

    // Saw波ソース（ステレオ: わずかにデチューン）
    src = (Saw.ar([freq, freq * 1.001]) * 0.3);
    fb  = LocalIn.ar(2);

    // フィードバック信号と混合しAllpassCで空間拡散（rumush手法）
    loc = src + (fb * feedback.clip(0, 0.85));
    loc = AllpassC.ar(loc, 0.12,
        [LFNoise1.kr(drift_rate).range(0.015, 0.09),
         LFNoise1.kr(drift_rate * 0.8).range(0.020, 0.11)],
        3.5);
    loc = loc + DelayC.ar(loc, 0.35,
        LFNoise2.kr([drift_rate * 0.5, drift_rate * 0.6]).range(0.05, 0.25));
    loc = loc + AllpassC.ar(loc, 0.08,
        [LFNoise0.kr(drift_rate * 1.5).range(0.01, 0.07),
         LFNoise0.kr(drift_rate * 2.0).range(0.015, 0.065)],
        2.0);

    // HPF: DCオフセット除去（rumush: HPF.ar(loc, 100)）
    loc = HPF.ar(loc, 80);
    // LocalOut: フィードバック出口（増幅して持続、rumush: * 1.75）
    LocalOut.ar(loc * 1.4);

    // 微小ピッチダウンシフト（PitchShift で 1.0 → 0.990 の範囲）
    // pitch_drop=0 は原音比1.0、pitch_drop=1 は0.990（-0.17半音）
    shifted = PitchShift.ar(loc, 0.08,
        pitch_drop.linlin(0, 1, 1.0, 0.990), 0.0, 0.002);
    sig = (loc * 0.65) + (shifted * pitch_drop * 0.5);
    sig = Limiter.ar(sig, 0.8);

    env = EnvGen.ar(Env.adsr(5.0, 0.5, 0.88, 8.0), gate, doneAction: 2);
    sig = sig * env;

    Out.ar(~droneBus, sig);
    Out.ar(~effectBus, FreeVerb2.ar(sig[0], sig[1],
        mix:  room.linlin(0, 1, 0.55, 0.92),
        room: room.linlin(0, 1, 0.65, 0.97),
        damp: room.linlin(0, 1, 0.65, 0.05)) * 0.8);
    Out.ar(0, FreeVerb2.ar(sig[0], sig[1],
        mix:  room.linlin(0, 1, 0.55, 0.92),
        room: room.linlin(0, 1, 0.65, 0.97),
        damp: room.linlin(0, 1, 0.65, 0.05)) * amp);
}).add;

// ════════════════════════════════════════════════════════════════
// DRONE 5: 揺れるSinOsc雲型
//
//   参照: github_drone_generators.md > Meandering Sines (emergent)
//   8声のSinOscをスケール音程に配置し、各ボイスが独立した速度の
//   LFNoise1 で周波数・振幅・パンを揺らし続ける。
//   chord_type でモードを切り替えてハーモニーを変える。
//
//   パラメーター:
//     freq       : 基音 Hz
//     detune_amt : 周波数ゆれ幅（比率, 0〜0.02）
//     lfo_rate   : LFO速度の基準値（各ボイスはこれを ×0.2〜×3.0 でランダムスケール）
//     chord_type : モード (0=元音程, 1=+4半音, 2=-3半音, 3=+7半音)
//     room / amp / gate
// ════════════════════════════════════════════════════════════════
SynthDef(\matoma_drone_sines, {
    arg freq       = 60,
        detune_amt = 0.004,
        lfo_rate   = 0.025,
        chord_type = 0,
        room       = 0.85,
        amp        = 0.28,
        gate       = 1;

    // マイナーペンタトニック拡張（8ボイス分の半音オフセット）
    var semitones = [0, 3, 5, 7, 10, 12, 15, 17];
    var chord_shift, sig, env;

    // chord_type でモード全体をシフト（定数配列 → Select.kr で選択）
    // 0: 元音程, 1: +4半音, 2: -3半音（相対的にマイナー→メジャー感）, 3: +7半音
    chord_shift = Select.kr(chord_type.clip(0, 3), [0, 4, -3, 7]);

    sig = Mix.fill(8, { |i|
        // コンパイル時の定数: semitones[i] は Integerとして評価済み
        var base_ratio  = 2.0 ** (semitones[i] / 12.0);
        // chord_shiftはUGen（kr）なので乗算でスケールする
        var chord_ratio = 2.0 ** (chord_shift / 12.0);
        var voiceFreq   = freq * base_ratio * chord_ratio *
            (1 + LFNoise1.kr(lfo_rate * rrand(0.3, 3.0), detune_amt));

        // 振幅: ゆっくりフェードイン/アウト + 高次倍音は自然に小さく
        var voiceAmp = LFNoise1.kr(lfo_rate * rrand(0.2, 2.0)).range(0.15, 1.0) *
                       (1.0 / (i * 0.18 + 1.0));

        // パン: ボイスごとに独立した速度で揺れる
        var voicePan = LFNoise1.kr(lfo_rate * rrand(0.1, 1.5)).range(-0.75, 0.75);

        Pan2.ar(SinOsc.ar(voiceFreq.clip(20, 18000)) * voiceAmp, voicePan)
    });

    sig = HPF.ar(sig, 30);
    sig = LeakDC.ar(sig) * 0.35;   // 8声Mix後の音量補正

    env = EnvGen.ar(Env.adsr(5.0, 0.5, 0.9, 10.0), gate, doneAction: 2);
    sig = sig * env;

    Out.ar(~droneBus, sig);
    Out.ar(~effectBus, FreeVerb2.ar(sig[0], sig[1],
        mix:  room.linlin(0, 1, 0.45, 0.92),
        room: room.linlin(0, 1, 0.60, 0.97),
        damp: room.linlin(0, 1, 0.70, 0.05)) * 0.8);
    Out.ar(0, FreeVerb2.ar(sig[0], sig[1],
        mix:  room.linlin(0, 1, 0.45, 0.92),
        room: room.linlin(0, 1, 0.60, 0.97),
        damp: room.linlin(0, 1, 0.70, 0.05)) * amp);
}).add;

s.sync;
"SynthDef定義完了: 5種のドローンジェネレーター".postln;

// ════════════════════════════════════════════════════════════════
// グローバル状態管理
//   ~droneGenerators : Symbol → Synth の Dictionary
//   ~stopDroneGenerator : ドローン停止の共通関数
// ════════════════════════════════════════════════════════════════

~droneGenerators = Dictionary.new;

~stopDroneGenerator = { |key|
    var synth = ~droneGenerators[key];
    if (synth.notNil) {
        synth.set(\gate, 0);
        ~droneGenerators[key] = nil;
        "ドローン停止（フェードアウト）: %".format(key).postln;
    };
};

// ════════════════════════════════════════════════════════════════
// OSCdef: DRONE 1 — FM + グリッサンド
// ════════════════════════════════════════════════════════════════

OSCdef(\matoma_drone_fm_start, { |msg|
    {
        ~stopDroneGenerator.(\fm);
        ~droneGenerators[\fm] = Synth(\matoma_drone_fm, addAction: \addToHead);
        "ドローン開始: FM+グリッサンド".postln;
    }.defer;
}, '/matoma/drone/fm/start', nil, 57200);

OSCdef(\matoma_drone_fm_stop, { |msg|
    { ~stopDroneGenerator.(\fm); }.defer;
}, '/matoma/drone/fm/stop', nil, 57200);

OSCdef(\matoma_drone_fm_param, { |msg|
    var param = msg[1].asSymbol;
    var value = msg[2].asFloat;
    {
        var synth = ~droneGenerators[\fm];
        if (synth.notNil) {
            if (param == \freq_norm) {
                var hz = value.linexp(0, 1, 20, 300);
                synth.set(\freq, hz);
                "ドローンFM freq_norm:% → % Hz".format(value.round(0.01), hz.round(0.1)).postln;
            } {
                synth.set(param, value);
                "ドローンFM %=%".format(param, value.round(0.001)).postln;
            };
        };
    }.defer;
}, '/matoma/drone/fm/param', nil, 57200);

// ════════════════════════════════════════════════════════════════
// OSCdef: DRONE 2 — 多声バンドパスノイズ
// ════════════════════════════════════════════════════════════════

OSCdef(\matoma_drone_noise_start, { |msg|
    {
        ~stopDroneGenerator.(\noise);
        ~droneGenerators[\noise] = Synth(\matoma_drone_noise, addAction: \addToHead);
        "ドローン開始: 多声バンドパスノイズ (8ボイス)".postln;
    }.defer;
}, '/matoma/drone/noise/start', nil, 57200);

OSCdef(\matoma_drone_noise_stop, { |msg|
    { ~stopDroneGenerator.(\noise); }.defer;
}, '/matoma/drone/noise/stop', nil, 57200);

OSCdef(\matoma_drone_noise_param, { |msg|
    var param = msg[1].asSymbol;
    var value = msg[2].asFloat;
    {
        var synth = ~droneGenerators[\noise];
        if (synth.notNil) {
            if (param == \freq_norm) {
                var hz = value.linexp(0, 1, 20, 300);
                synth.set(\freq, hz);
                "ドローンNoise freq_norm:% → % Hz".format(value.round(0.01), hz.round(0.1)).postln;
            } {
                synth.set(param, value);
                "ドローンNoise %=%".format(param, value.round(0.001)).postln;
            };
        };
    }.defer;
}, '/matoma/drone/noise/param', nil, 57200);

// ════════════════════════════════════════════════════════════════
// OSCdef: DRONE 3 — ウェーブテーブル + デグレード
// ════════════════════════════════════════════════════════════════

OSCdef(\matoma_drone_wavetable_start, { |msg|
    {
        ~stopDroneGenerator.(\wavetable);
        // buf0: 奇数倍音（中空管的）、buf1: 高次倍音（明るい）をデフォルトペアに
        ~droneGenerators[\wavetable] = Synth(\matoma_drone_wavetable, [
            \buf0, ~droneWtBufs[0].bufnum,
            \buf1, ~droneWtBufs[2].bufnum
        ], addAction: \addToHead);
        "ドローン開始: ウェーブテーブル+デグレード".postln;
    }.defer;
}, '/matoma/drone/wavetable/start', nil, 57200);

OSCdef(\matoma_drone_wavetable_stop, { |msg|
    { ~stopDroneGenerator.(\wavetable); }.defer;
}, '/matoma/drone/wavetable/stop', nil, 57200);

OSCdef(\matoma_drone_wavetable_param, { |msg|
    var param = msg[1].asSymbol;
    var value = msg[2].asFloat;
    {
        var synth = ~droneGenerators[\wavetable];
        if (synth.notNil) {
            switch(param)
            { \freq_norm } {
                var hz = value.linexp(0, 1, 20, 300);
                synth.set(\freq, hz);
                "ドローンWT freq_norm:% → % Hz".format(value.round(0.01), hz.round(0.1)).postln;
            }
            // buf_idx: 0〜3 でウェーブテーブルの種類を切り替え
            { \buf_idx } {
                var idx = value.round.asInteger.clip(0, 3);
                synth.set(\buf0, ~droneWtBufs[idx].bufnum);
                "ドローンWT buf_idx:%".format(idx).postln;
            }
            { synth.set(param, value); "ドローンWT %=%".format(param, value.round(0.001)).postln; };
        };
    }.defer;
}, '/matoma/drone/wavetable/param', nil, 57200);

// ════════════════════════════════════════════════════════════════
// OSCdef: DRONE 4 — フィードバックネットワーク
// ════════════════════════════════════════════════════════════════

OSCdef(\matoma_drone_feedback_start, { |msg|
    {
        ~stopDroneGenerator.(\feedback);
        ~droneGenerators[\feedback] = Synth(\matoma_drone_feedback, addAction: \addToHead);
        "ドローン開始: フィードバックネットワーク".postln;
    }.defer;
}, '/matoma/drone/feedback/start', nil, 57200);

OSCdef(\matoma_drone_feedback_stop, { |msg|
    { ~stopDroneGenerator.(\feedback); }.defer;
}, '/matoma/drone/feedback/stop', nil, 57200);

OSCdef(\matoma_drone_feedback_param, { |msg|
    var param = msg[1].asSymbol;
    var value = msg[2].asFloat;
    {
        var synth = ~droneGenerators[\feedback];
        if (synth.notNil) {
            if (param == \freq_norm) {
                var hz = value.linexp(0, 1, 20, 300);
                synth.set(\freq, hz);
                "ドローンFB freq_norm:% → % Hz".format(value.round(0.01), hz.round(0.1)).postln;
            } {
                synth.set(param, value);
                "ドローンFB %=%".format(param, value.round(0.001)).postln;
            };
        };
    }.defer;
}, '/matoma/drone/feedback/param', nil, 57200);

// ════════════════════════════════════════════════════════════════
// OSCdef: DRONE 5 — 揺れるSinOsc雲
// ════════════════════════════════════════════════════════════════

OSCdef(\matoma_drone_sines_start, { |msg|
    {
        ~stopDroneGenerator.(\sines);
        ~droneGenerators[\sines] = Synth(\matoma_drone_sines, addAction: \addToHead);
        "ドローン開始: 揺れるSinOsc雲 (8ボイス)".postln;
    }.defer;
}, '/matoma/drone/sines/start', nil, 57200);

OSCdef(\matoma_drone_sines_stop, { |msg|
    { ~stopDroneGenerator.(\sines); }.defer;
}, '/matoma/drone/sines/stop', nil, 57200);

OSCdef(\matoma_drone_sines_param, { |msg|
    var param = msg[1].asSymbol;
    var value = msg[2].asFloat;
    {
        var synth = ~droneGenerators[\sines];
        if (synth.notNil) {
            if (param == \freq_norm) {
                var hz = value.linexp(0, 1, 20, 300);
                synth.set(\freq, hz);
                "ドローンSines freq_norm:% → % Hz".format(value.round(0.01), hz.round(0.1)).postln;
            } {
                synth.set(param, value);
                "ドローンSines %=%".format(param, value.round(0.001)).postln;
            };
        };
    }.defer;
}, '/matoma/drone/sines/param', nil, 57200);

// ════════════════════════════════════════════════════════════════
// OSCdef: 全ドローン停止
// ════════════════════════════════════════════════════════════════

OSCdef(\matoma_drone_all_stop, { |msg|
    {
        [\fm, \noise, \wavetable, \feedback, \sines].do { |key|
            ~stopDroneGenerator.(key);
        };
        "全ドローンジェネレーター停止".postln;
    }.defer;
}, '/matoma/drone/all/stop', nil, 57200);

// ════════════════════════════════════════════════════════════════
// 起動完了メッセージ
// ════════════════════════════════════════════════════════════════
"".postln;
"── MaToMa ドローンジェネレーター (5種) 登録完了 ──".postln;
"  1. FM+グリッサンド  : /matoma/drone/fm/start|stop|param".postln;
"     params: freq_norm, mod_index(0-6), glide(0.8-1.0), pluck_mix(0-0.6)".postln;
"  2. 多声バンドパスNoise: /matoma/drone/noise/start|stop|param".postln;
"     params: freq_norm, filter_rq(0.05-0.4), damp_exp(0.5-2.0), detune(0-0.05)".postln;
"  3. ウェーブテーブル  : /matoma/drone/wavetable/start|stop|param".postln;
"     params: freq_norm, degrade(0-1), lfo_rate(0.01-0.5), lfo_type(0-2), buf_idx(0-3)".postln;
"  4. フィードバックNW  : /matoma/drone/feedback/start|stop|param".postln;
"     params: freq_norm, feedback(0-0.85), drift_rate(0.01-0.5), pitch_drop(0-1)".postln;
"  5. 揺れるSinOsc雲   : /matoma/drone/sines/start|stop|param".postln;
"     params: freq_norm, chord_type(0-3), detune_amt(0-0.02), lfo_rate(0.01-0.2)".postln;
"  全停止: /matoma/drone/all/stop".postln;
"".postln;

// ════════════════════════════════════════════════════════════════
// 動作確認コマンド（単独実行時）
// s.waitForBoot({ load("sc/drone_generators.scd"); }) でブート後に実行
// ════════════════════════════════════════════════════════════════

// 1. FM + グリッサンド
// NetAddr("127.0.0.1", 57200).sendMsg('/matoma/drone/fm/start');
// NetAddr("127.0.0.1", 57200).sendMsg('/matoma/drone/fm/param', 'mod_index', 3.5);
// NetAddr("127.0.0.1", 57200).sendMsg('/matoma/drone/fm/param', 'freq_norm', 0.35);
// NetAddr("127.0.0.1", 57200).sendMsg('/matoma/drone/fm/stop');

// 2. 多声バンドパスノイズ
// NetAddr("127.0.0.1", 57200).sendMsg('/matoma/drone/noise/start');
// NetAddr("127.0.0.1", 57200).sendMsg('/matoma/drone/noise/param', 'damp_exp', 0.7);
// NetAddr("127.0.0.1", 57200).sendMsg('/matoma/drone/noise/stop');

// 3. ウェーブテーブル + デグレード
// NetAddr("127.0.0.1", 57200).sendMsg('/matoma/drone/wavetable/start');
// NetAddr("127.0.0.1", 57200).sendMsg('/matoma/drone/wavetable/param', 'degrade', 0.5);
// NetAddr("127.0.0.1", 57200).sendMsg('/matoma/drone/wavetable/param', 'lfo_type', 2);
// NetAddr("127.0.0.1", 57200).sendMsg('/matoma/drone/wavetable/stop');

// 4. フィードバックネットワーク
// NetAddr("127.0.0.1", 57200).sendMsg('/matoma/drone/feedback/start');
// NetAddr("127.0.0.1", 57200).sendMsg('/matoma/drone/feedback/param', 'feedback', 0.72);
// NetAddr("127.0.0.1", 57200).sendMsg('/matoma/drone/feedback/param', 'pitch_drop', 0.5);
// NetAddr("127.0.0.1", 57200).sendMsg('/matoma/drone/feedback/stop');

// 5. 揺れるSinOsc雲
// NetAddr("127.0.0.1", 57200).sendMsg('/matoma/drone/sines/start');
// NetAddr("127.0.0.1", 57200).sendMsg('/matoma/drone/sines/param', 'chord_type', 2);
// NetAddr("127.0.0.1", 57200).sendMsg('/matoma/drone/sines/param', 'lfo_rate', 0.05);
// NetAddr("127.0.0.1", 57200).sendMsg('/matoma/drone/sines/stop');

// 全停止
// NetAddr("127.0.0.1", 57200).sendMsg('/matoma/drone/all/stop');
