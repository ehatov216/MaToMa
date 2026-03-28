/*
MaToMa: グラニューラサンプラー
================================
音声ファイルを「グレイン」と呼ばれる米粒ほどの短い音片に分割して、
大量に重ねて再生するモジュール。

「グレイン（grain）」とは：
  ふつうのサンプラーが音声をそのまま再生するのと違い、
  音声を数十〜数百ミリ秒の断片に刻んで、霧や雲のように重ね合わせる。
  これにより：
    - 音の質感を保ちながら時間を引き伸ばす・圧縮できる
    - 位置（pos）をゆっくり動かすとスクラブ感や時間が滲む感覚になる
    - density・size で密度や粒の粗さをコントロールできる

使い方:
  1. sc/samples/ に WAV/AIFF ファイルを置く
  2. このファイルを SuperCollider で開く
  3. Cmd+A → Cmd+Enter で全体を実行
  4. OSC '/matoma/granular/load' でバッファをロード
  5. OSC '/matoma/granular/start' で再生開始

パラメーター:
  buf       : バッファ番号。GrainBuf が読み込む音声データを指定する
  rate      : 再生速度・ピッチの倍率（0.5=1オクターブ下、1.0=元の音程、2.0=1オクターブ上）
  pos       : バッファ内の再生位置（0.0〜1.0）。「音のどのあたりを使うか」
  posrand   : 位置のランダム幅（0.0=完全固定、0.5=大きくばらける）
  pitchrand : ピッチのランダム幅（0.0=固定、0.1=大きく揺れる）
  size      : グレインの長さ（秒、0.01〜0.5）。小さい=ざらざら、大きい=滑らか
  density   : 1秒あたりのグレイン数（1〜100）。多いほど音が密に重なる
  trig_mode : トリガーの種類
              0 = Dust（ランダム間隔）→ 有機的・カオス的なテクスチャ
              1 = Impulse（等間隔）  → リズミカル・機械的なテクスチャ
  amp       : 音量（0.0〜1.0）

OSC アドレス:
  /matoma/granular/load  → バッファロード [ファイルパス文字列]
  /matoma/granular/start → 再生開始
  /matoma/granular/stop  → フェードアウトして停止
  /matoma/granular/param → パラメーター更新 [名前, 値]
                           例: ['/matoma/granular/param', 'density', 30]

── run_headless.scd への組み込み方 ──────────────────────────────────
s.waitForBoot({ の中に以下を追加し、s.sync; の前に置く:

  // ① このファイルの SynthDef 定義ブロックをそのままコピーして貼り付ける
  //    （SynthDef(\matoma_granular, { ... }).add; の部分）

  // ② s.sync; の後、デモバッファ生成とOSCdef定義ブロックをコピーして貼り付ける

  // ③ サンプルを使う場合は、run_headless.scd の起動前に
  //    '/matoma/granular/load' OSCを送ってバッファをロードする
────────────────────────────────────────────────────────────────────
*/

(
s.waitForBoot({

    // ── SynthDef: グラニューラサンプラー ──────────────────────────
    //
    // GrainBuf: SuperCollider 標準のグレイン合成 UGen
    //   trigger  → グレインを発生させるタイミング（ここでは Dust でランダム）
    //   dur      → 1グレインの長さ（秒）= size
    //   sndbuf   → 読み込むバッファ
    //   rate     → 再生速度（ピッチも変わる）
    //   pos      → バッファ内の位置（0.0〜1.0）
    //   pan      → ステレオの左右位置（-1.0〜+1.0）
    //
    SynthDef(\matoma_granular, {
        arg buf = 0,
            rate = 1.0,
            pos = 0.0,
            posrand = 0.05,    // 位置のランダム幅（0.0=固定、0.5=大きくばらける）
            pitchrand = 0.01,  // ピッチのランダム幅（0.0=固定、0.1=大きく揺れる）
            size = 0.1,        // グレインの長さ（秒）
            density = 20,      // 1秒あたりのグレイン数
            trig_mode = 0,     // 0=Dust（ランダム）、1=Impulse（等間隔）
            amp = 0.5,
            gate = 1;

        // ── トリガー: Dust（ランダム）か Impulse（等間隔）を選択 ──
        //
        // Dust.kr   → バラバラなタイミングで発火 → 霧・有機的な質感
        // Impulse.kr → 等間隔で発火              → リズミカル・機械的な質感
        //
        // Select.kr(trig_mode, [A, B]):
        //   trig_mode=0 → A（Dust）を使う
        //   trig_mode=1 → B（Impulse）を使う
        // 両方とも常に動いているが、Select が出力を切り替えるだけなので問題ない
        var trig_random  = Dust.kr(density);
        var trig_regular = Impulse.kr(density);
        var trigger = Select.kr(trig_mode, [trig_random, trig_regular]);

        // ── 再生位置のランダム揺らぎ ─────────────────────────────
        // pos を中心に ±posrand の範囲でグレインごとにランダムにばらける
        // posrand=0.0 → 全グレインが pos の真上に固定（ピンポイント再生）
        // posrand=0.5 → バッファ全体に広くばらける
        var grainPos = (pos + TRand.kr(posrand.neg, posrand, trigger)).clip(0.0, 1.0);

        // ── ピッチのランダム揺らぎ ───────────────────────────────
        // pitchrand=0.0 → 全グレインが同じピッチ（クリア）
        // pitchrand=0.1 → グレインごとに ±10% ピッチが揺れる（霞感）
        var grainRate = rate * (1.0 + TRand.kr(pitchrand.neg, pitchrand, trigger));

        // ── ステレオの広がり ─────────────────────────────────────
        // グレインごとに左右の位置をランダムに変える（±0.8 の範囲で固定）
        var pan = TRand.kr(-0.8, 0.8, trigger);

        // ── グラニューラ合成 ──────────────────────────────────────
        var sig = GrainBuf.ar(
            numChannels: 2,      // ステレオ出力
            trigger: trigger,
            dur: size,
            sndbuf: buf,
            rate: grainRate,
            pos: grainPos,
            interp: 2,           // 線形補間（音の繋ぎ目を滑らかに）
            pan: pan,
            envbufnum: -1        // デフォルトのベル型エンベロープ（Hanning窓）
        );

        // ── エンベロープ: フェードイン・アウト ───────────────────
        // attack=0.5秒でふわっと立ち上がり、stop時は2秒でフェードアウト
        sig = sig * Linen.kr(gate, 0.5, 1.0, 2.0, 2);

        sig = sig * amp;

        Out.ar(0, sig);
    }).add;

    "シンセ定義完了: \\matoma_granular".postln;

    s.sync;

    // ── デモ用バッファ: ファイルがなくても試せるようにサイン波を生成 ──
    // Buffer.alloc: 空のバッファを確保する（2秒分）
    // sine1: 倍音成分をバッファに書き込む（1倍音・2倍音・3倍音・4倍音の重ね合わせ）
    ~granularBuf = Buffer.alloc(s, (s.sampleRate * 2).round.asInteger, 1, { |buf|
        buf.sine1([1.0, 0.5, 0.25, 0.125], asWavetable: false, normalize: true);
        ~granularBufNum = buf.bufnum;
        "デモ用バッファ生成完了（サイン波 2秒）。実際の音声ファイルを使う場合は".postln;
        "'/matoma/granular/load' でファイルパスを送ってください。".postln;
    });

    ~currentGranular = nil;

    // ── OSC: バッファをファイルからロード ────────────────────────
    // msg の形式: ['/matoma/granular/load', '/path/to/file.wav']
    OSCdef(\matoma_granular_load, { |msg|
        var path = msg[1].asString;
        {
            if (~granularBuf.notNil) { ~granularBuf.free };
            ~granularBuf = Buffer.read(s, path, action: { |buf|
                ~granularBufNum = buf.bufnum;
                if (~currentGranular.notNil) {
                    ~currentGranular.set(\buf, ~granularBufNum);
                };
                "バッファロード完了: % (% frames, % ch)".format(
                    path, buf.numFrames, buf.numChannels).postln;
            });
        }.defer;
    }, '/matoma/granular/load');

    // ── OSC: 再生開始 ────────────────────────────────────────────
    OSCdef(\matoma_granular_start, { |msg|
        {
            if (~currentGranular.notNil) {
                ~currentGranular.set(\gate, 0);  // 既存をフェードアウト
            };
            ~currentGranular = Synth(\matoma_granular, [
                \buf, ~granularBufNum ?? { 0 }
            ]);
            "グラニューラ開始".postln;
        }.defer;
    }, '/matoma/granular/start');

    // ── OSC: 停止 ────────────────────────────────────────────────
    OSCdef(\matoma_granular_stop, { |msg|
        {
            if (~currentGranular.notNil) {
                ~currentGranular.set(\gate, 0);  // gate=0 でフェードアウト開始
                ~currentGranular = nil;
                "グラニューラ停止（フェードアウト中）".postln;
            };
        }.defer;
    }, '/matoma/granular/stop');

    // ── OSC: パラメーター更新 ─────────────────────────────────────
    // msg の形式: ['/matoma/granular/param', 'パラメーター名', 値]
    // 例: ['/matoma/granular/param', 'density', 40]
    OSCdef(\matoma_granular_param, { |msg|
        var param = msg[1].asSymbol;
        var value = msg[2].asFloat;
        {
            if (~currentGranular.notNil) {
                ~currentGranular.set(param, value);
                "グラニューラ パラメーター更新: % = %".format(param, value.round(0.001)).postln;
            };
        }.defer;
    }, '/matoma/granular/param');

    "MaToMa グラニューラサンプラー起動完了。".postln;
    "コマンド例:".postln;
    "  ファイルロード → NetAddr('127.0.0.1', 57120).sendMsg('/matoma/granular/load', '/path/to/sample.wav')".postln;
    "  再生開始      → NetAddr('127.0.0.1', 57120).sendMsg('/matoma/granular/start')".postln;
    "  密度を上げる  → NetAddr('127.0.0.1', 57120).sendMsg('/matoma/granular/param', 'density', 50)".postln;
    "  位置を動かす  → NetAddr('127.0.0.1', 57120).sendMsg('/matoma/granular/param', 'pos', 0.5)".postln;
    "  停止          → NetAddr('127.0.0.1', 57120).sendMsg('/matoma/granular/stop')".postln;
});
)
