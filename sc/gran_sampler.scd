// ══════════════════════════════════════════════════════════════════
//  MaToMa gran_sampler.scd  — グラニュラーサンプラー（ファイル読み込み型）v1
//
//  【設計思想】
//    外部サウンドファイル（WAV/AIFF）をバッファに読み込み、
//    GrainBuf で粒状に分解するグラニュラーサンプラー。
//    「素材の原形が分からなくなるまで加工する」OPN的テクスチャ変換が目的。
//
//    【前回の失敗原因と対策】
//      - SC側に /matoma/granular/load の受信ハンドラが存在しなかった → 今回実装
//      - バッファ確認なしで Synth を起動していた → ロード完了後のみ起動可能に
//      - モノラル/ステレオ不整合 → Buffer.readChannel で1ch強制読み込み
//
//  【シグナルチェーン】
//    Buffer（WAV/AIFFファイル）
//      → GrainBuf（粒状分解: pos + posScatter, rate, grainSize）
//      → FreeVerb2（空間化）
//      → Env.adsr（attack:0.5s / release:2s）
//      → Limiter（安全制御 0.9）
//      → ~effectBus
//
//  【安全なロード手順】
//    1. /matoma/gran_sampler/browse → macOS ダイアログでファイル選択
//    2. /matoma/gran_sampler/load [path] → Buffer.readChannel で読み込み
//    3. SC が /matoma/gran_sampler/loaded [path, frames, sampleRate] を返す
//    4. /matoma/gran_sampler/start → バッファ確認後に Synth 起動
//
//  【パラメーター】
//    density    : グレイン/秒（5〜60）。大きいほど密で連続的
//    pos        : バッファ内の読み出し位置（0.0〜1.0）
//    posScatter : 位置のランダムゆらぎ（0.0〜0.3）
//    rate       : 再生速度・ピッチ倍率（0.25〜4.0、1.0=原音）
//    grainSize  : グレインの長さ（秒）（0.05〜0.5）
//    spray      : 0=Impulse(規則的) / 1=Dust(ランダム)
//    room       : リバーブ量（0.0〜1.0）
//    amp        : 音量（0.0〜1.0）
//
//  【OSCアドレス（port 57200）】
//    /matoma/gran_sampler/load  [path]        → バッファ読み込み
//    /matoma/gran_sampler/start               → 再生開始
//    /matoma/gran_sampler/stop                → フェードアウト停止
//    /matoma/gran_sampler/param [名前] [値]   → パラメーター更新
//    /matoma/gran_sampler/unload              → バッファ解放
//
//  【SC→Python 返信（port 9000）】
//    /matoma/gran_sampler/loaded  [path, numFrames, sampleRate]
//    /matoma/gran_sampler/load_error [path]
//    /matoma/gran_sampler/no_buffer
// ══════════════════════════════════════════════════════════════════

// ── SynthDef: グラニュラーサンプラー ──────────────────────────────────
// github_granular_synthesizers.md § Vasileios / Simple_Sc_Granulator_GUI
// norns_sc_patterns.md § 4. silo_grain パターンを基に実装
SynthDef(\matoma_gran_sampler, {
    arg buf        = 0,     // バッファ番号（loadで設定）
        density    = 20,    // グレイン/秒（5〜60）
        pos        = 0.5,   // バッファ内の読み出し位置（0.0〜1.0）
        posScatter = 0.08,  // 位置のランダムゆらぎ
        rate       = 1.0,   // 再生速度・ピッチ倍率（1.0=原音）
        grainSize  = 0.15,  // グレインの長さ（秒）
        spray      = 0.3,   // 0=Impulse（規則的）1=Dust（ランダム）
        room       = 0.4,   // リバーブ量
        amp        = 0.5,   // 音量
        gate       = 1,     // エンベロープゲート
        outBus     = 0;     // 出力バス

    // SCルール: var 宣言はすべて先頭にまとめる
    var trig, jitteredPos;
    var sig, wet, env;

    // ── spray: Impulse ↔ Dust をブレンド ─────────────────────────────
    // norns silo_grain / matoma_granular と同設計
    // spray=0: 規則的な発火（機械的・グリッド感）
    // spray=1: ランダム発火（有機的・霧感）
    trig = SelectX.kr(spray, [
        Impulse.kr(density),
        Dust.kr(density)
    ]);

    // ── 位置スキャッター ───────────────────────────────────────────────
    // LFNoise0 で density レートのランダムゆらぎを加える
    // 参照: norns_sc_patterns.md § silo_grain の jitter パターン
    jitteredPos = (pos + LFNoise0.kr(density).bipolar(posScatter)).clip(0, 1);

    // ── GrainBuf: バッファから粒を生成 ────────────────────────────────
    // 参照: synthesis_granular.md § GrainBuf / github_granular_synthesizers.md
    // pan を LFNoise1 でゆっくりランダム化してステレオ空間に散らす
    sig = GrainBuf.ar(
        numChannels: 2,
        trigger:     trig,
        dur:         grainSize,
        sndbuf:      buf,
        rate:        rate,
        pos:         jitteredPos,
        interp:      2,           // 線形補間（音質と負荷のバランス）
        pan:         LFNoise1.kr(3).range(-0.7, 0.7),
        envbufnum:   -1           // デフォルト Hanning 窓
    );

    // ── FreeVerb2: 空間化 ─────────────────────────────────────────────
    wet = FreeVerb2.ar(
        sig[0], sig[1],
        mix:  room.linlin(0.0, 1.0, 0.2, 0.7),
        room: room.linlin(0.0, 1.0, 0.4, 0.85),
        damp: room.linlin(0.0, 1.0, 0.6, 0.1)
    );

    // ── エンベロープ ─────────────────────────────────────────────────
    // attack 0.5秒（音が滑らかに立ち上がる）/ release 2秒（フェードアウト）
    env = EnvGen.ar(Env.adsr(0.5, 0.0, 1.0, 2.0), gate, doneAction: 2);

    // ── 安全制御: Limiter ─────────────────────────────────────────────
    Out.ar(outBus, Limiter.ar(wet * env * amp, 0.9));
}).add;

s.sync;
"SynthDef定義完了: \\matoma_gran_sampler (グラニュラーサンプラー v1)".postln;

// ── グローバル変数 ─────────────────────────────────────────────────
~granSamplerBuf     = nil;  // 読み込んだバッファ（nil=未ロード）
~currentGranSampler = nil;  // 現在鳴っている Synth

// ── OSCdef: バッファ読み込み ─────────────────────────────────────────
// 【安全設計】
//   1. 既存バッファを先に解放してメモリリークを防ぐ
//   2. Buffer.readChannel でモノラル強制読み込み（ステレオ不整合を防ぐ）
//   3. action コールバックでロード成功/失敗を Python へ通知
//   4. numFrames=0 はロード失敗として扱う
OSCdef(\matoma_gran_sampler_load, { |msg|
    var path = msg[1].asString;
    var pythonAddr = NetAddr("127.0.0.1", 9000);
    {
        // 既存バッファを解放（二重ロード防止）
        if (~granSamplerBuf.notNil) {
            ~granSamplerBuf.free;
            ~granSamplerBuf = nil;
            "グラニュラーサンプラー: 既存バッファを解放".postln;
        };

        "グラニュラーサンプラー: ロード開始 → %".format(path).postln;

        // Buffer.readChannel でモノラル1ch読み込み（channels: [0] = 左chのみ）
        // ステレオファイルでも右ch分の予期しない挙動を防ぐ
        ~granSamplerBuf = Buffer.readChannel(s, path, channels: [0],
            action: { |buf|
                if (buf.numFrames > 0) {
                    // 成功: バッファ情報を Python へ送信
                    pythonAddr.sendMsg(
                        '/matoma/gran_sampler/loaded',
                        path,
                        buf.numFrames,
                        buf.sampleRate
                    );
                    "グラニュラーサンプラー ロード完了: % (buf:% frames:% dur:%.2fs sr:%Hz)".format(
                        path.basename,
                        buf.bufnum,
                        buf.numFrames,
                        buf.duration,
                        buf.sampleRate.round(1)
                    ).postln;
                } {
                    // 失敗: numFrames=0 はファイル読み取り失敗
                    ~granSamplerBuf = nil;
                    pythonAddr.sendMsg('/matoma/gran_sampler/load_error', path);
                    "グラニュラーサンプラー ロードエラー: % (frames=0)".format(path).postln;
                };
            }
        );
    }.defer;
}, '/matoma/gran_sampler/load', nil, 57200);

// ── OSCdef: 再生開始 ─────────────────────────────────────────────────
// バッファが未ロードの場合は起動せず Python に通知する（安全設計）
OSCdef(\matoma_gran_sampler_start, { |msg|
    var pythonAddr = NetAddr("127.0.0.1", 9000);
    {
        if (~granSamplerBuf.isNil) {
            // バッファ未ロード: Python へ通知してフロントエンドにエラー表示
            pythonAddr.sendMsg('/matoma/gran_sampler/no_buffer');
            "グラニュラーサンプラー: バッファ未ロード。先にファイルを選択してください".postln;
        } {
            // 既存 Synth をフェードアウト
            if (~currentGranSampler.notNil) {
                ~currentGranSampler.set(\gate, 0);
            };
            ~currentGranSampler = Synth(\matoma_gran_sampler, [
                \buf,    ~granSamplerBuf.bufnum,
                \outBus, ~effectBus.index
            ], addAction: \addToTail);
            "グラニュラーサンプラー開始 (buf:% frames:% dur:%.2fs)".format(
                ~granSamplerBuf.bufnum,
                ~granSamplerBuf.numFrames,
                ~granSamplerBuf.duration
            ).postln;
        };
    }.defer;
}, '/matoma/gran_sampler/start', nil, 57200);

// ── OSCdef: 停止 ─────────────────────────────────────────────────────
// gate=0 → Env.adsr の release（2秒フェードアウト）が走る
OSCdef(\matoma_gran_sampler_stop, { |msg|
    {
        if (~currentGranSampler.notNil) {
            ~currentGranSampler.set(\gate, 0);
            ~currentGranSampler = nil;
            "グラニュラーサンプラー停止（2秒フェードアウト）".postln;
        };
    }.defer;
}, '/matoma/gran_sampler/stop', nil, 57200);

// ── OSCdef: パラメーター更新 ─────────────────────────────────────────
// 許可リストで想定外パラメーターを弾く（セキュリティ）
OSCdef(\matoma_gran_sampler_param, { |msg|
    var param = msg[1].asSymbol;
    var value = msg[2].asFloat;
    var allowed = #[\density, \pos, \posScatter, \rate, \grainSize,
                    \spray, \room, \amp, \gate];
    {
        if (allowed.includes(param).not) {
            "gran_sampler/param: 許可されていないパラメーター '%' を無視".format(param).postln;
        } {
            if (~currentGranSampler.notNil) {
                ~currentGranSampler.set(param, value);
                "グラニュラーサンプラー param: % = %".format(param, value.round(0.001)).postln;
            };
        };
    }.defer;
}, '/matoma/gran_sampler/param', nil, 57200);

// ── OSCdef: バッファ解放 ─────────────────────────────────────────────
// ロードしたファイルを手動で解放する（メモリ管理）
OSCdef(\matoma_gran_sampler_unload, { |msg|
    {
        if (~currentGranSampler.notNil) {
            ~currentGranSampler.set(\gate, 0);
            ~currentGranSampler = nil;
        };
        if (~granSamplerBuf.notNil) {
            ~granSamplerBuf.free;
            ~granSamplerBuf = nil;
            "グラニュラーサンプラー: バッファ解放".postln;
        };
    }.defer;
}, '/matoma/gran_sampler/unload', nil, 57200);

"グラニュラーサンプラーモジュール ロード完了 (v1 ファイル読み込み型)".postln;
