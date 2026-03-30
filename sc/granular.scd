/*
MaToMa: グラニュラーモジュール v2 — Drone素材粒分解型
==========================================================
【設計思想】
  Drone が作り出した「湿った空気」を、そのまま粒に分解してテクスチャを作る。
  Tim Hecker 的な「残響ごと粒になる」密度を実現するため、
  ~droneBus（Shimmer Reverb後の信号）をリングバッファに録音し続け、
  GrainBuf でリアルタイムに粒に変換する。

【シグナルチェーンのイメージ】
  ~droneBus（Droneのウェット信号）
    → RecordBuf で2秒のリングバッファに継続録音
    → GrainBuf で粒に分解（spray: 0=規則的/1=ランダム）
    → 個別FreeVerb2リバーブ
    → ~effectBus（グローバルエフェクト層へ）
    → Out（スピーカー出力）

【パラメーター】
  density : 1秒あたりのグレイン数（5〜80）
  spray   : 0=Impulse（規則的）↔ 1=Dust（ランダム）。SelectX.kr でブレンド
  pos     : バッファ内の再生位置（0.0〜1.0）
  size    : グレインの長さ（秒）。小=ざらざら、大=滑らか
  room    : 個別リバーブのroom size（0.0〜1.0）
  amp     : 音量（0.0〜1.0）

【OSCアドレス】
  /matoma/granular/start              → グラニュラー開始
  /matoma/granular/stop               → フェードアウト停止
  /matoma/granular/param [名前] [値]  → パラメーター更新
    例: /matoma/granular/param density 30
        /matoma/granular/param spray 0.7

【技術的補足】
  - RecordBuf の loop:1 で2秒のリングバッファを維持する
  - GrainBuf の pos は 0〜1 で「バッファのどこを使うか」を指定する
  - SelectX.kr で Impulse ↔ Dust をブレンドすることで
    spray パラメーター1つで「機械的↔有機的」を連続的に制御できる
    （参照: norns_sc_patterns.md / silo_grain パターン）
*/

(
s.waitForBoot({

    // ── Wet Drone Bus と Effect Bus の確保 ──────────────────────────────
    // ~droneBus は drone.scd（または run_headless.scd）で定義済み。
    // ここでは単独実行テスト用に nil チェックして確保する。
    if (~droneBus.isNil) {
        ~droneBus = Bus.audio(s, 2);
        "単独実行モード: ~droneBus を確保しました（bus: %)".format(~droneBus).postln;
    };
    if (~effectBus.isNil) {
        ~effectBus = Bus.audio(s, 2);
        "単独実行モード: ~effectBus を確保しました（bus: %)".format(~effectBus).postln;
    };

    // ── グラニュラー用リングバッファ ──────────────────────────────────
    // Drone の2秒分（ステレオ）をリングバッファに録音し続ける。
    // GrainBuf はこのバッファから pos に従って粒を読む。
    ~granularRingBuf = Buffer.alloc(s, (s.sampleRate * 2.0).round.asInteger, 2);

    s.sync;
    "グラニュラー リングバッファ確保完了 (bufnum: %)".format(~granularRingBuf.bufnum).postln;

    // ── SynthDef: リングバッファ録音器 ────────────────────────────────
    // ~droneBus の信号を継続的にリングバッファへ書き込む。
    // RecordBuf の loop:1 で永遠に上書き録音を続ける（リングバッファ）。
    SynthDef(\matoma_granular_recorder, {
        arg inBus, buf;
        var sig = In.ar(inBus, 2);
        // loop:1 でバッファ末尾に達したら先頭から上書き
        RecordBuf.ar(sig, buf, loop: 1, trigger: 1, doneAction: 0);
    }).add;

    s.sync;

    // ── SynthDef: グラニュラー合成器 ──────────────────────────────────
    // norns_sc_patterns.md の silo_grain パターンを基に実装。
    // spray パラメーター: SelectX.kr で Impulse/Dust を連続ブレンド。
    SynthDef(\matoma_granular, {
        arg buf       = 0,    // リングバッファ番号
            density   = 20,   // グレイン/秒
            spray     = 0.3,  // 0=Impulse(規則的) 1=Dust(ランダム)
            pos       = 0.5,  // バッファ内の読み取り位置（0.0〜1.0）
            size      = 0.12, // グレインの長さ（秒）
            jitter    = 0.08, // 位置のランダム幅（norns silo_grain のjitter相当）
            room      = 0.5,  // 個別リバーブのroom size
            amp       = 0.5,
            gate      = 1,
            outBus    = 0,    // 出力先バス（0=ハード出力、~effectBus=エフェクト層）
            // Layer A: 外部から深さを制御できる
            a2_depth  = 1.0,  // A2（心拍）の深さ倍率 0.0〜1.0
            a3_depth  = 1.0;  // A3（神経）の深さ倍率

        var trig_regular, trig_random, trig, grainPos;
        var sig, wet, env;
        // Layer A2: 心拍（0.1〜0.5 Hz）— density と room を揺らす
        var a2_density_mod, a2_room_mod;
        // Layer A3: 神経（1〜5 Hz）— 粒の位置をさらに微細に揺らす
        var a3_jitter_mod;
        // 有機値
        var density_live, room_live;

        // ── Layer A2: 心拍（0.15〜0.35 Hz）─────────────────────────────
        // 粒の密度（density）とリバーブを「心拍」のように緩やかに揺らす。
        a2_density_mod = LFNoise3.kr(0.25).range(
            1.0 - (0.25 * a2_depth),
            1.0 + (0.25 * a2_depth)
        );
        a2_room_mod = LFNoise3.kr(0.18).range(
            room - (0.08 * a2_depth),
            room + (0.08 * a2_depth)
        ).clip(0.0, 1.0);

        // ── Layer A3: 神経（2〜4 Hz）────────────────────────────────────
        // 粒の jitter をさらに微細に揺らして「霧のミクロ揺らぎ」を作る。
        a3_jitter_mod = jitter + LFNoise3.kr(3.0).range(0.0, 0.04 * a3_depth);

        // Layer A 計算済みの有機値
        density_live = density * a2_density_mod;
        room_live    = a2_room_mod;

        // ── spray: 規則的（Impulse）↔ ランダム（Dust）をブレンド ──────
        // SelectX.kr は 0〜1 の間でクロスフェードする。
        // spray=0.0 → Impulse のみ（機械的・グリッド的）
        // spray=0.5 → Impulse と Dust の中間（半有機的）
        // spray=1.0 → Dust のみ（完全ランダム・霧的）
        // 参照: norns_sc_patterns.md § 4. グレイン合成（Norns Siloパターン）
        trig_regular = Impulse.kr(density_live);
        trig_random  = Dust.kr(density_live);
        trig = SelectX.kr(spray, [trig_regular, trig_random]);

        // ── 再生位置 + Jitter ──────────────────────────────────
        // a3_jitter_mod (Layer A3 神経) を加えて「霧のミクロ揺らぎ」を生む
        grainPos = pos + LFNoise0.kr(6).bipolar(a3_jitter_mod);
        grainPos = grainPos.clip(0.0, 1.0);

        // ── GrainBuf: リングバッファから粒を生成 ─────────────────────
        // GrainBuf はバッファ録音した音を「粒」として再生する。
        // pan を LFNoise1 でゆっくりランダム化してステレオ空間に散らす。
        sig = GrainBuf.ar(
            numChannels: 2,
            trigger:     trig,
            dur:         size,
            sndbuf:      buf,
            rate:        1.0,
            pos:         grainPos,
            interp:      2,           // 線形補間
            pan:         LFNoise1.kr(3).range(-0.7, 0.7),
            envbufnum:   -1           // デフォルト Hanning 窓
        );

        // ── 個別 FreeVerb2 リバーブ ───────────────────────────────────
        // room_live (Layer A2 心拍) を使うことでリバーブ感が「呼吸」する
        wet = FreeVerb2.ar(
            sig[0], sig[1],
            mix:  room_live.linlin(0.0, 1.0, 0.25, 0.75),
            room: room_live.linlin(0.0, 1.0, 0.45, 0.85),
            damp: room_live.linlin(0.0, 1.0, 0.6, 0.2)
        );

        // ── エンベロープ ──────────────────────────────────────────────
        // 0.5秒でふわっと立ち上がり、stop時は2秒でフェードアウト
        env = EnvGen.ar(Env.adsr(0.5, 0.0, 1.0, 2.0), gate, doneAction: 2);

        // ── 安全制御: Limiter（多層防衛の最終ライン） ───────────────────
        // 高密度グレインが重なるとピークが出やすいため 0.9 で頭打ちにする
        Out.ar(outBus, Limiter.ar(wet * env * amp, 0.9));
    }).add;

    s.sync;
    "シンセ定義完了: \\matoma_granular_recorder, \\matoma_granular (v2 Drone素材粒分解型)".postln;

    // ── グローバル変数の初期化 ─────────────────────────────────────────
    ~currentGranular  = nil;
    ~granularRecorder = nil;

    // ── リングバッファ録音を開始する内部関数 ─────────────────────────
    // Drone が動いていれば ~droneBus の信号が継続的に録音される。
    // Drone が鳴っていなければ無音が録音されるだけ（害なし）。
    ~startGranularRecorder = {
        if (~granularRecorder.notNil) {
            ~granularRecorder.free;
        };
        ~granularRecorder = Synth(\matoma_granular_recorder, [
            \inBus, ~droneBus,
            \buf, ~granularRingBuf.bufnum
        ], addAction: \addToHead);
        "グラニュラー録音器: 開始 (droneBus: %, ringBuf: %)".format(
            ~droneBus, ~granularRingBuf.bufnum).postln;
    };

    // 録音器をすぐに起動する（常時録音）
    { ~startGranularRecorder.(); }.defer;

    // ── OSCdef: グラニュラー開始 ─────────────────────────────────────
    OSCdef(\matoma_granular_start, { |msg|
        {
            if (~currentGranular.notNil) {
                ~currentGranular.set(\gate, 0);
            };
            ~currentGranular = Synth(\matoma_granular, [
                \buf,    ~granularRingBuf.bufnum,
                \outBus, ~effectBus.index
            ], addAction: \addToTail);
            "グラニュラー開始 (ringBuf: %, outBus: %)".format(
                ~granularRingBuf.bufnum, ~effectBus.index).postln;
        }.defer;
    }, '/matoma/granular/start');

    // ── OSCdef: グラニュラー停止 ─────────────────────────────────────
    OSCdef(\matoma_granular_stop, { |msg|
        {
            if (~currentGranular.notNil) {
                ~currentGranular.set(\gate, 0);
                ~currentGranular = nil;
                "グラニュラー停止（2秒フェードアウト）".postln;
            };
        }.defer;
    }, '/matoma/granular/stop');

    // ── OSCdef: パラメーター更新 ─────────────────────────────────────
    // msg 形式: ['/matoma/granular/param', 'パラメーター名', 値]
    // 例:
    //   density → 粒の密度（5〜80）
    //   spray   → ランダム度（0.0=規則的、1.0=完全ランダム）
    //   pos     → 再生位置（0.0〜1.0）
    //   size    → 粒サイズ（秒）
    //   room    → リバーブ量（0.0〜1.0）
    //   amp     → 音量（0.0〜1.0）
    OSCdef(\matoma_granular_param, { |msg|
        var param = msg[1].asSymbol;
        var value = msg[2].asFloat;
        {
            if (~currentGranular.notNil) {
                ~currentGranular.set(param, value);
                "グラニュラー param: % = %".format(param, value.round(0.001)).postln;
            };
        }.defer;
    }, '/matoma/granular/param');

    "MaToMa グラニュラーモジュール起動完了 (v2 Drone素材粒分解型)".postln;
    "".postln;
    "── 動作確認コマンド ──────────────────────────────────────────".postln;
    "グラニュラー開始:   NetAddr('127.0.0.1', 57120).sendMsg('/matoma/granular/start')".postln;
    "密度を上げる:       NetAddr('127.0.0.1', 57120).sendMsg('/matoma/granular/param', 'density', 40)".postln;
    "ランダム化(spray):  NetAddr('127.0.0.1', 57120).sendMsg('/matoma/granular/param', 'spray', 0.8)".postln;
    "位置を動かす:       NetAddr('127.0.0.1', 57120).sendMsg('/matoma/granular/param', 'pos', 0.7)".postln;
    "粒を大きくする:     NetAddr('127.0.0.1', 57120).sendMsg('/matoma/granular/param', 'size', 0.25)".postln;
    "停止:               NetAddr('127.0.0.1', 57120).sendMsg('/matoma/granular/stop')".postln;
});
)

// ────────────────────────────────────────────────────────────────────
// 動作確認（このファイルを単独実行中のみ使用）
// ────────────────────────────────────────────────────────────────────

// グラニュラー開始（~droneBus に何かが流れていること前提）
// NetAddr("127.0.0.1", 57120).sendMsg('/matoma/granular/start');

// spray を上げてランダム化（霧的テクスチャ）
// NetAddr("127.0.0.1", 57120).sendMsg('/matoma/granular/param', 'spray', 0.9);

// 密度を上げる（密な霧）
// NetAddr("127.0.0.1", 57120).sendMsg('/matoma/granular/param', 'density', 50);

// 粒を大きくする（よりアンビエント的）
// NetAddr("127.0.0.1", 57120).sendMsg('/matoma/granular/param', 'size', 0.3);

// 停止
// NetAddr("127.0.0.1", 57120).sendMsg('/matoma/granular/stop');
