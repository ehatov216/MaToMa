/*
MaToMa: アンビエント・ドローンモジュール（v2 — 共鳴育成型）
================================================================
【設計思想】
  「発振器から描く」ではなく「共鳴から育てる」。
  PinkNoise（自然界の背景雑音）を Klank（倍音フィルターバンク）に通すことで、
  楽器の胴体が共鳴するような「自然に育つ音」を生成する。

【シグナルチェーンのイメージ】
  PinkNoise（雑音の種）
    → Klank（倍音バンク：胴鳴り）    … 音色と質感を同時に形成
    → LocalIn/LocalOut フィードバック … 倍音が自己生成・増幅する
    → tanh サチュレーション           … 温かみと倍音の密度
    → Shimmer Reverb（PitchShift）   … リバーブ尾部をオクターブ上に戻す→浮遊感
    → ~droneBus（ウェット信号バス）   … Granularがここから素材を読む
    → FreeVerb2 / GVerb              … 最終空間演出
    → Out

【パラメーター】
  freq         : 共鳴の基本周波数（Hz）。40=超低域、60=低域、110=中低域
  feedback_amt : 内部フィードバック量（0.0〜0.5）。大きいほど倍音が自己生成する
  shimmer      : シマーリバーブのミックス量（0.0〜1.0）。浮遊感の強さ
  room         : 個別リバーブのroom size（0.0〜1.0）
  amp          : 音量（0.0〜1.0）
  gate         : エンベロープゲート（1=持続、0=フェードアウト）

【OSCアドレス】
  /matoma/drone/start              → ドローン開始
  /matoma/drone/stop               → フェードアウト停止
  /matoma/drone/param [名前] [値]  → パラメーター更新
    例: /matoma/drone/param shimmer 0.7

【run_headless.scd への組み込み方】
  s.waitForBoot({ ... }) の中、既存の OSCdef の後（"MaToMa 起動完了" の前）に
  ▼▼▼ ここから ▼▼▼ と ▲▲▲ ここまで ▲▲▲ の間をコピーする。
  なお ~droneBus の確保は run_headless.scd の s.waitForBoot 直後に行うこと。
*/

(
s.waitForBoot({

    // ── Wet Drone Bus: Granular が読む共有バス ──────────────────────────
    // GranularがDroneのウェット信号を素材として読み取るための2chバス。
    // run_headless.scd では s.waitForBoot の冒頭（SynthDef定義の前）に置く。
    ~droneBus = Bus.audio(s, 2);
    "~droneBus 確保: %".format(~droneBus).postln;

    // ▼▼▼ ここから run_headless.scd にコピー ▼▼▼

    // ── SynthDef: 共鳴育成型 アンビエント・ドローン ─────────────────────
    SynthDef(\matoma_drone, {
        arg freq         = 60,
            feedback_amt = 0.25,
            shimmer      = 0.4,
            room         = 0.7,
            amp          = 0.35,
            gate         = 1;

        // SCルール: var宣言はすべて先頭にまとめる
        var noise, fb, klanked, saturated;
        var shifted, shimmered;
        var env, wetL, wetR, sig;

        // ── PinkNoise: 共鳴の「種」 ──────────────────────────────────────
        // PinkNoiseは自然界に近いスペクトル分布を持つ雑音。
        // これを倍音バンクに通すことで「自然に育つ音」になる。
        noise = PinkNoise.ar(0.12);

        // ── LocalIn: フィードバックループの入口 ─────────────────────────
        // 前の出力信号を少量だけ入力に混ぜることで、倍音が自己増幅する。
        // 参照: synthesis_ambient_drone.md / sa_feedback_drone
        fb = LocalIn.ar(2);

        // ── Klank: 倍音フィルターバンク（胴鳴り） ───────────────────────
        // Klank は「共鳴周波数・振幅・減衰時間」の配列で楽器の胴体を模倣する。
        // 非整数倍音（2.756, 5.404 ...）を使うと「金属板」でなく「空気の塊」のような質感になる。
        // 参照: synthesis_physical_modeling.md / sa_modal_bar
        klanked = Klank.ar(`[
            [freq,            freq * 1.501,  freq * 2.756,  freq * 3.999,  freq * 5.404],
            [1.0,             0.7,           0.5,           0.3,           0.15],
            [4.0,             3.0,           2.0,           1.5,           1.0]
        ], noise + (fb[0] * feedback_amt));

        // ステレオ感のため、わずかに異なる倍音比率でLチャンネルを追加生成
        klanked = [
            klanked,
            Klank.ar(`[
                [freq * 1.002, freq * 1.503,  freq * 2.759,  freq * 4.003,  freq * 5.407],
                [0.9,          0.65,          0.45,          0.27,          0.13],
                [4.1,          3.1,           2.1,           1.55,          1.05]
            ], noise + (fb[1] * feedback_amt))
        ];

        // ── Limiter + AllpassC: クリッピング防止と空間拡散 ───────────────
        // AllpassC は位相をランダムに拡散させてリバーブ感を薄く付与する（前処理）。
        klanked = Limiter.ar(klanked, 0.65);
        klanked = AllpassC.ar(
            LPF.ar(klanked, freq * 8.0),
            0.08,
            [LFNoise1.kr(0.11).range(0.03, 0.07),
             LFNoise1.kr(0.09).range(0.04, 0.08)],
            2.0
        );

        // ── LocalOut: フィードバックループの出口 ────────────────────────
        LocalOut.ar(klanked);

        // ── tanh サチュレーション: 温かみと倍音密度 ─────────────────────
        // 軽いオーバードライブにより高次倍音が加わり、音が「息づく」ようになる。
        saturated = LeakDC.ar((klanked * 2.0).tanh) * 0.55;

        // ── Shimmer Reverb: リバーブ尾部をオクターブ上にピッチシフト ─────
        // 残響がオクターブ上に戻ることで「空に溶けていく」浮遊感が生まれる。
        // 参照: synthesis_ambient_drone.md / sa_shimmer
        shifted  = PitchShift.ar(saturated, 0.1, 2.0, 0.01, 0.005);
        shimmered = [
            saturated[0] + (shifted[0] * shimmer),
            saturated[1] + (shifted[1] * shimmer)
        ];

        // ── エンベロープ ─────────────────────────────────────────────────
        // attack 4秒 / release 8秒 の非常に緩やかな立ち上がり・終わり
        env = EnvGen.ar(Env.adsr(4.0, 0.3, 0.88, 8.0), gate, doneAction: 2);
        shimmered = shimmered * env;

        // ── ~droneBus への書き出し（Granular 用ウェット素材） ────────────
        // FreeVerb2 を通す前の「シマーかかった信号」をバスに流す。
        // これによりGranularが「まだ乾いていない、気体のような素材」を拾える。
        Out.ar(~droneBus, shimmered);

        // ── FreeVerb2: 最終空間演出 ──────────────────────────────────────
        // feedback/knowledge.md の「ドローン > 効いた操作」に基づき、
        // 残響が必要なときは GVerb への切り替えも選択肢に残しておく。
        sig = FreeVerb2.ar(
            shimmered[0], shimmered[1],
            mix:  room.linlin(0.0, 1.0, 0.45, 0.92),
            room: room.linlin(0.0, 1.0, 0.60, 0.95),
            damp: room.linlin(0.0, 1.0, 0.55, 0.12)
        );

        Out.ar(0, sig * amp);
    }).add;

    s.sync;  // SynthDef がサーバーに届くまで待つ

    "シンセ定義完了: \\matoma_drone (v2 共鳴育成型)".postln;

    // ── グローバル変数: 現在鳴っているドローンを記憶 ─────────────────
    ~currentDrone = nil;

    // ── OSCdef: ドローンを開始する ──────────────────────────────────────
    OSCdef(\matoma_drone_start, { |msg|
        {
            if (~currentDrone.notNil) {
                ~currentDrone.set(\gate, 0);  // 既存をフェードアウト
            };
            ~currentDrone = Synth(\matoma_drone);
            "ドローン開始 (v2)".postln;
        }.defer;
    }, '/matoma/drone/start');

    // ── OSCdef: ドローンを停止する ──────────────────────────────────────
    // gate=0 を渡すと Env.adsr の release（8秒フェードアウト）が起動する
    OSCdef(\matoma_drone_stop, { |msg|
        {
            if (~currentDrone.notNil) {
                ~currentDrone.set(\gate, 0);
                ~currentDrone = nil;
                "ドローン停止（8秒でフェードアウト）".postln;
            };
        }.defer;
    }, '/matoma/drone/stop');

    // ── OSCdef: パラメーターをリアルタイム更新 ──────────────────────────
    // 受信形式: ['/matoma/drone/param', 'パラメーター名', 値]
    // 例: ['/matoma/drone/param', 'shimmer', 0.7]
    OSCdef(\matoma_drone_param, { |msg|
        var param = msg[1].asSymbol;
        var value = msg[2].asFloat;
        {
            if (~currentDrone.notNil) {
                ~currentDrone.set(param, value);
                "ドローン param: % = %".format(param, value.round(0.001)).postln;
            };
        }.defer;
    }, '/matoma/drone/param');

    // ▲▲▲ ここまで run_headless.scd にコピー ▲▲▲

    "MaToMa ドローンモジュール起動完了 (v2 共鳴育成型)。".postln;
    "".postln;
    "── 動作確認コマンド ──────────────────────────────────────────".postln;
    "ドローン開始:     NetAddr('127.0.0.1', 57120).sendMsg('/matoma/drone/start')".postln;
    "周波数変更:       NetAddr('127.0.0.1', 57120).sendMsg('/matoma/drone/param', 'freq', 55)".postln;
    "フィードバック強: NetAddr('127.0.0.1', 57120).sendMsg('/matoma/drone/param', 'feedback_amt', 0.4)".postln;
    "シマー強:         NetAddr('127.0.0.1', 57120).sendMsg('/matoma/drone/param', 'shimmer', 0.7)".postln;
    "停止:             NetAddr('127.0.0.1', 57120).sendMsg('/matoma/drone/stop')".postln;
});
)

// ────────────────────────────────────────────────────────────────────
// 動作確認（このファイルを単独実行中のみ使用）
// 各ブロックを選択して Cmd+Enter で個別に実行できる
// ────────────────────────────────────────────────────────────────────

// ドローンを開始する
// NetAddr("127.0.0.1", 57120).sendMsg('/matoma/drone/start');

// フィードバック量を上げて倍音を育てる
// NetAddr("127.0.0.1", 57120).sendMsg('/matoma/drone/param', 'feedback_amt', 0.4);

// シマーを強くして浮遊感を出す
// NetAddr("127.0.0.1", 57120).sendMsg('/matoma/drone/param', 'shimmer', 0.7);

// 根音を低くする（重いドローン）
// NetAddr("127.0.0.1", 57120).sendMsg('/matoma/drone/param', 'freq', 40);

// 停止する（8秒でフェードアウト）
// NetAddr("127.0.0.1", 57120).sendMsg('/matoma/drone/stop');
