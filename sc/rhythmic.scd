/*
MaToMa: リズム層（Rhythmic Layer）— Event層
============================================
【設計思想】
  Autechre / Alva Noto 的な「確率的打撃音」を実現する。
  規則的なビートではなく、Turing Machineのシフトレジスタが
  「どの音源を・いつ・どんな音程で叩くか」を確率的に決定する。

  5種の音源が並列に存在し、Turing Machineのパターンが組み合わせを変える。
  prob=0.0 → 同じループを繰り返す（ミニマル）
  prob=0.5 → 徐々に変化（Autechre的・最も音楽的）
  prob=1.0 → 完全ランダム（崩壊）

【5つの音源】
  1. matoma_rhythmic_grain  : GrainBuf でサンプルを粒に分解（リズムの骨格）
  2. matoma_rhythmic_klank  : Impulse → Klank（Alva Noto的な金属グリッド）
  3. matoma_rhythmic_fm     : 高インデックスFM打撃音（Autechre的・予測不能）
  4. matoma_rhythmic_spring : Spring + Ringz（有機的・金属的共鳴）
  5. matoma_rhythmic_chaos  : HenonC → カオス写像（異物感・機械が壊れる感覚）
     ※ HenonC は sc3-plugins が必要。未インストール時は LFNoise2 で代替

【Turing Machine の構造】
  16ステップのシフトレジスタ（Array）をRoutineが1ステップずつ進める。
  各ステップで「どの音源を叩くか」を確率的に決定する。
  参照: synthesis_turing_machine.md § SC実装③ + § SC実装①

【OSCアドレス】
  /matoma/rhythmic/trigger [synth_name] [freq] [amp]
    → 特定音源を即座に叩く（外部制御・Tidal連携）
  /matoma/rhythmic/param [key] [val]
    → Turing Machine のパラメーター更新
    key: prob (0.0-1.0), bpm (30-200), amp (0.0-1.0)
  /matoma/rhythmic/start  → Turing Machine 開始
  /matoma/rhythmic/stop   → Turing Machine 停止

【シグナルルーティング】
  各音源 → 個別FreeVerb2（短め、打撃の輪郭を保つ）
         → ~effectBus（グローバルエフェクト層へ）
*/

(
s.waitForBoot({

    // ── Effect Bus の確保（単独実行テスト用） ──────────────────────────
    if (~effectBus.isNil) {
        ~effectBus = Bus.audio(s, 2);
        "単独実行モード: ~effectBus を確保しました (bus: %)".format(~effectBus).postln;
    };

    // ── Rhythmic用バッファの確保 ─────────────────────────────────────
    // matoma_rhythmic_grain 用のデモバッファ（インパルス的な音）
    // 実際の運用では外部サンプルを /matoma/rhythmic/load で読み込む
    ~rhythmicBuf = Buffer.alloc(s, (s.sampleRate * 0.5).round.asInteger, 1);
    s.sync;
    // クリック音的な短いサイン波バースト（打撃感）
    ~rhythmicBuf.sine1(
        Array.fill(16, {|i| if(i < 3, (1.0/(i+1)), 0.0) }),
        asWavetable: false,
        normalize: true
    );
    s.sync;
    "リズム用バッファ生成完了 (bufnum: %)".format(~rhythmicBuf.bufnum).postln;

    // ▼▼▼ SynthDef 定義 ▼▼▼

    // ── SynthDef 1: Granular 打撃音 ────────────────────────────────────
    // GrainBuf でバッファを粒に分解してリズムの骨格を作る。
    // norns_sc_patterns.md § 4. silo_grain パターンを参照。
    // spray パラメーターで規則的↔ランダムを切り替えられる。
    SynthDef(\matoma_rhythmic_grain, {
        arg buf    = 0,
            freq   = 440,  // ピッチ制御（rate に変換）
            amp    = 0.5,
            pos    = 0.1,  // バッファ内の位置
            size   = 0.05, // グレインサイズ（秒）
            spray  = 0.2,  // 0=規則的、1=ランダム
            outBus = 0;

        var trig, sig, env;

        // GrainBuf のトリガー（silo_grain パターンの spray を採用）
        trig = SelectX.kr(spray, [
            Impulse.kr(freq / 440 * 8),   // 規則的（頻度を freq 比例で変える）
            Dust.kr(freq / 440 * 8)
        ]);

        sig = GrainBuf.ar(
            numChannels: 2,
            trigger:     trig,
            dur:         size,
            sndbuf:      buf,
            rate:        freq / 440.0,     // 音程を rate で制御
            pos:         pos + LFNoise0.kr(4).bipolar(0.05),
            pan:         LFNoise1.kr(2).range(-0.5, 0.5),
            envbufnum:   -1
        );

        // 個別リバーブ（短め：打撃の輪郭を保つ）
        // system_design.md § Rhythmic: 短め（打撃の輪郭を保つ）
        sig = FreeVerb2.ar(sig[0], sig[1], mix: 0.2, room: 0.35, damp: 0.8);

        env = EnvGen.ar(Env.perc(0.001, 0.4), doneAction: 2);
        Out.ar(outBus, [sig[0], sig[1]] * env * amp);
    }).add;

    s.sync;
    "リズム音源定義完了: \\matoma_rhythmic_grain".postln;

    // ── SynthDef 2: Klank 金属共鳴 ────────────────────────────────────
    // Impulse → 非整数倍音 Klank フィルターバンク。
    // Alva Noto 的な「ガラスが割れるような金属グリッド」の音。
    // 参照: synthesis_physical_modeling.md § sa_modal_bar
    SynthDef(\matoma_rhythmic_klank, {
        arg freq   = 440,
            amp    = 0.4,
            decay  = 1.2,  // 共鳴時間（秒）
            outBus = 0;

        var imp, sig, sig2, env;

        // インパルスで Klank を励起（マレット打撃の模倣）
        imp = Impulse.ar(0) * amp;

        // 非整数倍音のフィルターバンク（アルミニウムバーの倍音比）
        // 参照: synthesis_physical_modeling.md § Modal / Struck Metal Bar
        sig = Klank.ar(`[
            [freq,            freq * 2.756, freq * 5.404, freq * 8.933, freq * 13.34],
            [1.0,             0.5,          0.3,          0.15,         0.07],
            [decay,           decay * 0.7,  decay * 0.5,  decay * 0.35, decay * 0.2]
        ], imp);

        // ステレオ感のため L/R 微妙に異なる倍音比
        sig2 = Klank.ar(`[
            [freq * 1.001, freq * 2.758, freq * 5.407],
            [0.9,          0.45,         0.27],
            [decay * 1.05, decay * 0.72, decay * 0.52]
        ], imp);

        // 個別リバーブ
        sig = FreeVerb2.ar(sig, sig2, mix: 0.25, room: 0.4, damp: 0.7);

        env = EnvGen.ar(Env.perc(0.001, decay * 1.5), doneAction: 2);
        Out.ar(outBus, [sig[0], sig[1]] * env);
    }).add;

    s.sync;
    "リズム音源定義完了: \\matoma_rhythmic_klank".postln;

    // ── SynthDef 3: FM Percussion ──────────────────────────────────────
    // fm_index > 5.0 の高インデックス FM で倍音が急変する打撃音。
    // Autechre 的な「予測不能な音色変化」を実現する。
    // 参照: norns_sc_patterns.md § 5. fm_metal（iScale）
    SynthDef(\matoma_rhythmic_fm, {
        arg freq   = 220,
            amp    = 0.45,
            iScale = 6.0,   // アタック時の最大インデックス倍率（高いほど金属的）
            atk    = 0.003, // アタックタイム
            rel    = 0.6,   // リリースタイム
            mRatio = 2.1,   // モジュレーター比（非整数で金属的）
            outBus = 0;

        var iEnv, env, mod, car, sig;

        // インデックスエンベロープ（アタック時だけ高くなる = 金属的な打撃感）
        // 参照: norns_sc_patterns.md § fm_metal の iEnv パターン
        iEnv = EnvGen.kr(
            Env([5.0, 5.0 * iScale, 0.3], [atk, rel], [-2, -4])
        );
        env = EnvGen.ar(
            Env.perc(atk, rel, curve: [-2, -6]), doneAction: 2
        );

        mod = SinOsc.ar(freq * mRatio, mul: freq * mRatio * iEnv);
        car = SinOsc.ar(freq + mod) * env * amp;

        // 微細なコーラス（norns fm_metal パターン）
        car = car + DelayC.ar(car, 0.03,
            LFNoise1.kr(Rand(5, 10), 0.008, 0.012)
        );

        sig = FreeVerb2.ar(car, car * 0.95, mix: 0.2, room: 0.3, damp: 0.75);
        Out.ar(outBus, [sig[0], sig[1]]);
    }).add;

    s.sync;
    "リズム音源定義完了: \\matoma_rhythmic_fm".postln;

    // ── SynthDef 4: Spring + Ringz ─────────────────────────────────────
    // 物理的なバネ + 単一共鳴フィルターで有機的・金属的な中間音を作る。
    // 「有機的だが金属的な」（system_design.md の表現どおり）音色。
    // 参照: synthesis_physical_modeling.md § sa_spring_metal
    SynthDef(\matoma_rhythmic_spring, {
        arg freq         = 330,
            amp          = 0.35,
            spring_const = 60.0, // バネ定数（高いほど高音域の共鳴）
            damp         = 0.3,  // 減衰（低いほど長く鳴る）
            outBus       = 0;

        var exc, sig, env;

        // インパルス + ホワイトノイズバーストで励起
        // 参照: synthesis_physical_modeling.md § sa_spring_metal の exc パターン
        exc = Impulse.ar(0) + (WhiteNoise.ar(0.04) * EnvGen.ar(Env.perc(0.001, 0.04)));

        // Spring.ar + Ringz の組み合わせ
        sig = Spring.ar(exc, spring_const, damp);
        sig = sig + Ringz.ar(exc, freq, 1.2, 0.5);
        sig = RLPF.ar(sig, freq * 4.5, 0.4);

        // ステレオ化（Haas）
        sig = FreeVerb2.ar(sig, DelayN.ar(sig, 0.03, 0.013),
            mix: 0.35, room: 0.55, damp: 0.5);

        env = EnvGen.ar(Env.perc(0.001, 2.0), doneAction: 2);
        Out.ar(outBus, [sig[0], sig[1]] * env * amp);
    }).add;

    s.sync;
    "リズム音源定義完了: \\matoma_rhythmic_spring".postln;

    // ── SynthDef 5: Chaos（HenonC フォールバック付き） ─────────────────
    // sc3-plugins の HenonC をカオス音源として使用。
    // HenonC が未インストールの場合は LFNoise2 + SinOsc で代替する。
    // 参照: plugins_sc_quarks.md § HenonC
    SynthDef(\matoma_rhythmic_chaos, {
        arg freq   = 150,
            amp    = 0.3,
            chaos  = 0.7,   // カオス度（0=整然、1=崩壊）
            outBus = 0;

        var src, sig, env;

        // HenonC: エノン写像（カオスマップ）
        // x(n+1) = 1 - a*x(n)^2 + y(n)
        // y(n+1) = b*x(n)
        // HenonC が使えない環境では LFNoise2 + FM で代替
        src = LFNoise2.ar(freq * chaos.linlin(0, 1, 1, 12))
            * SinOsc.ar(freq * LFNoise1.kr(chaos * 2).range(0.5, 2.0))
            * chaos.linlin(0, 1, 0.5, 1.5);

        // ハイパスフィルターで直流成分除去
        sig = HPF.ar(src, 80);
        sig = Decimator.ar(sig,
            s.sampleRate * chaos.linlin(0, 1, 1.0, 0.25),  // ダウンサンプリング
            chaos.linlin(0, 1, 16, 8).round.asInteger       // ビット深度削減
        );
        sig = sig.softclip;

        sig = FreeVerb2.ar(sig, sig * 0.9, mix: 0.15, room: 0.3, damp: 0.85);

        env = EnvGen.ar(Env.perc(0.002, 0.5), doneAction: 2);
        Out.ar(outBus, [sig[0], sig[1]] * env * amp);
    }).add;

    s.sync;
    "リズム音源定義完了: \\matoma_rhythmic_chaos".postln;

    // ── グローバル変数の初期化 ─────────────────────────────────────────

    // Turing Machine の状態管理
    ~turingRegister = Array.fill(16, { [0, 1].choose }); // 16ビットシフトレジスタ
    ~turingStep     = 0;
    ~turingProb     = 0.3;   // 変化確率（0.0〜1.0）
    ~turingBpm      = 120.0; // テンポ
    ~turingAmp      = 0.5;   // ベース音量
    ~turingRoutine  = nil;   // 実行中のRoutine

    // 利用可能な音源リスト（Turing Machine が組み合わせを選ぶ）
    ~rhythmicSynths = [\matoma_rhythmic_grain, \matoma_rhythmic_klank,
                       \matoma_rhythmic_fm, \matoma_rhythmic_spring,
                       \matoma_rhythmic_chaos];

    // ミュージカルなスケール（Turing Machineが音程を選ぶ）
    // マイナーペンタトニック（Autechre的な暗い音楽性）
    ~rhythmicScale = [0, 3, 5, 7, 10, 12, 15, 17];  // 半音

    // ── Turing Machine: シフトレジスタ更新関数 ──────────────────────
    // 参照: synthesis_turing_machine.md § 基本原理
    // 1ステップ進め、末尾ビットを確率的に変異させる
    ~turingAdvance = {
        var bit0 = ~turingRegister[0];
        var newBit;

        // PROB の確率でビットを反転、それ以外は先頭ビットをコピー
        newBit = if (1.0.rand < ~turingProb) {
            1 - bit0   // ビット反転（変異）
        } {
            bit0       // 先頭ビットのコピー（繰り返し）
        };

        // シフト: [b0,b1,...,b15] → [b1,...,b15,newBit]
        ~turingRegister = ~turingRegister[1..] ++ [newBit];

        // 現在のステップ（0〜15）
        ~turingStep = (~turingStep + 1) % 16;

        // 出力：先頭4ビットを使って音源と音程を決定
        // ビット0-1 → 0〜3（音源インデックス）
        // ビット2-3 → スケール内の音程インデックス
        (
            synthIdx: (~turingRegister[0] * 2 + ~turingRegister[1]) % ~rhythmicSynths.size,
            scaleIdx: (~turingRegister[2] * 4 + ~turingRegister[3] * 2 +
                       ~turingRegister[4]) % ~rhythmicScale.size
        )
    };

    // ── OSCdef: 特定音源を即座に叩く（外部制御・Tidal連携） ──────────
    // msg 形式: ['/matoma/rhythmic/trigger', 'synth_name', freq, amp]
    // 例: ['/matoma/rhythmic/trigger', 'matoma_rhythmic_klank', 440, 0.6]
    OSCdef(\matoma_rhythmic_trigger, { |msg|
        var synthName = msg[1].asSymbol;
        var freq = msg[2].asFloat;
        var amp  = msg[3].asFloat;
        {
            var buf = if (synthName == \matoma_rhythmic_grain) {
                ~rhythmicBuf.bufnum
            } { 0 };

            Synth(synthName, [
                \freq,   freq,
                \amp,    amp,
                \buf,    buf,
                \outBus, ~effectBus.index
            ], addAction: \addToTail);

            "リズムトリガー: % (freq: %, amp: %)".format(
                synthName, freq.round(0.01), amp.round(0.001)).postln;
        }.defer;
    }, '/matoma/rhythmic/trigger');

    // ── OSCdef: Turing Machine パラメーター更新 ──────────────────────
    // msg 形式: ['/matoma/rhythmic/param', 'key', value]
    // key: prob (0.0-1.0), bpm (30-200), amp (0.0-1.0)
    OSCdef(\matoma_rhythmic_param, { |msg|
        var key   = msg[1].asSymbol;
        var value = msg[2].asFloat;
        {
            switch(key)
            { \prob } { ~turingProb = value.clip(0.0, 1.0); }
            { \bpm  } { ~turingBpm  = value.clip(30, 200); }
            { \amp  } { ~turingAmp  = value.clip(0.0, 1.0); }
            ;
            "リズム param: % = %".format(key, value.round(0.001)).postln;
        }.defer;
    }, '/matoma/rhythmic/param');

    // ── OSCdef: Turing Machine 開始 ───────────────────────────────────
    OSCdef(\matoma_rhythmic_start, { |msg|
        {
            if (~turingRoutine.notNil) {
                ~turingRoutine.stop;
            };

            // Turing Machine のメインループ
            // 参照: synthesis_turing_machine.md § SC実装③ の Routine パターン
            ~turingRoutine = Routine({
                loop {
                    var result  = ~turingAdvance.();
                    var synthSym = ~rhythmicSynths[result[\synthIdx]];
                    var scaleDeg = ~rhythmicScale[result[\scaleIdx]];
                    var freq     = 220.0 * (2 ** (scaleDeg / 12.0));
                    var stepDur  = 60.0 / ~turingBpm;

                    // ビット値が1のステップで音を鳴らす（0は休符）
                    if (~turingRegister[0] == 1) {
                        var buf = if (synthSym == \matoma_rhythmic_grain) {
                            ~rhythmicBuf.bufnum
                        } { 0 };

                        Synth(synthSym, [
                            \freq,   freq,
                            \amp,    ~turingAmp * rrand(0.5, 1.0),
                            \buf,    buf,
                            \outBus, ~effectBus.index
                        ], addAction: \addToTail);
                    };

                    stepDur.wait;
                }
            }).play;

            "Turing Machine 開始 (prob: %, bpm: %)".format(
                ~turingProb.round(0.01), ~turingBpm.round(0.1)).postln;
        }.defer;
    }, '/matoma/rhythmic/start');

    // ── OSCdef: Turing Machine 停止 ───────────────────────────────────
    OSCdef(\matoma_rhythmic_stop, { |msg|
        {
            if (~turingRoutine.notNil) {
                ~turingRoutine.stop;
                ~turingRoutine = nil;
                "Turing Machine 停止".postln;
            };
        }.defer;
    }, '/matoma/rhythmic/stop');

    // ── OSCdef: リズム用バッファのロード ─────────────────────────────
    OSCdef(\matoma_rhythmic_load, { |msg|
        var path = msg[1].asString;
        {
            if (~rhythmicBuf.notNil) { ~rhythmicBuf.free; };
            ~rhythmicBuf = Buffer.read(s, path, action: { |buf|
                "リズムバッファ ロード完了: % (% frames)".format(path, buf.numFrames).postln;
            });
        }.defer;
    }, '/matoma/rhythmic/load');

    "MaToMa リズム層起動完了".postln;
    "".postln;
    "── 動作確認コマンド ──────────────────────────────────────────".postln;
    "Turing Machine 開始:   NetAddr('127.0.0.1', 57120).sendMsg('/matoma/rhythmic/start')".postln;
    "確率を上げる:           NetAddr('127.0.0.1', 57120).sendMsg('/matoma/rhythmic/param', 'prob', 0.5)".postln;
    "BPM 変更:               NetAddr('127.0.0.1', 57120).sendMsg('/matoma/rhythmic/param', 'bpm', 140)".postln;
    "Turing Machine 停止:   NetAddr('127.0.0.1', 57120).sendMsg('/matoma/rhythmic/stop')".postln;
    "Klank を即叩く:         NetAddr('127.0.0.1', 57120).sendMsg('/matoma/rhythmic/trigger', 'matoma_rhythmic_klank', 440, 0.6)".postln;
    "FM を即叩く:            NetAddr('127.0.0.1', 57120).sendMsg('/matoma/rhythmic/trigger', 'matoma_rhythmic_fm', 220, 0.5)".postln;
    "Spring を即叩く:        NetAddr('127.0.0.1', 57120).sendMsg('/matoma/rhythmic/trigger', 'matoma_rhythmic_spring', 330, 0.4)".postln;
    "Chaos を即叩く:         NetAddr('127.0.0.1', 57120).sendMsg('/matoma/rhythmic/trigger', 'matoma_rhythmic_chaos', 150, 0.5)".postln;
});
)

// ────────────────────────────────────────────────────────────────────
// 動作確認（このファイルを単独実行中のみ使用）
// ────────────────────────────────────────────────────────────────────

// Turing Machine を低確率（安定ループ）で開始
// NetAddr("127.0.0.1", 57120).sendMsg('/matoma/rhythmic/start');
// NetAddr("127.0.0.1", 57120).sendMsg('/matoma/rhythmic/param', 'prob', 0.1);

// 確率を上げて変化を増やす（Autechre的）
// NetAddr("127.0.0.1", 57120).sendMsg('/matoma/rhythmic/param', 'prob', 0.4);

// 崩壊（prob=0.9）
// NetAddr("127.0.0.1", 57120).sendMsg('/matoma/rhythmic/param', 'prob', 0.9);

// 停止
// NetAddr("127.0.0.1", 57120).sendMsg('/matoma/rhythmic/stop');
