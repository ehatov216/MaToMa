/*
MaToMa: エフェクト層（Effect Layer）
======================================
【設計思想】
  全音源（Drone / Granular / Rhythmic）が送り込む共有バス ~effectBus に
  グローバルエフェクトをかけ、最終出力へ届ける。
  ユーザーがライブ中にブラウザUIからリアルタイムに操作する場所。

  参照: system_design.md § エフェクト層（Effect Layer）
  参照: norns_sc_patterns.md § 7. エフェクトバス構成（Anvilパターン）

【シグナルチェーンの位置】
  [Drone/Granular/Rhythmic]
    → ~effectBus（共有バス）
      → Global Delay（奥行き）
      → Spectral Freeze / Blur（凍結・拡散）
      → Wavefolder（倍音追加）
      → Feedback Loop（自律的なエコー）
      → Glitch（デジタルアーティファクト・信号の欠陥）
    → スピーカー

【エフェクトの種類】
  1. Global Delay     : /matoma/effect/delay/param [time] [feedback] [mix]
  2. Spectral Freeze  : /matoma/effect/spectral/param [freeze] [blur]
  3. Wavefolder       : /matoma/effect/wavefolder/param [drive] [mix]
  4. Feedback Loop    : /matoma/effect/feedback/param [amount] [rate]
  5. Glitch           : /matoma/effect/glitch/param [intensity] [density] [mode] [mix]

【OSCアドレス（共通形式）】
  /matoma/effect/[エフェクト名]/start   → エフェクト起動
  /matoma/effect/[エフェクト名]/stop    → エフェクト停止（バイパス）
  /matoma/effect/[エフェクト名]/param [key] [val] → パラメーター更新

【実装上の注意】
  - エフェクトシンセは必ず addAction: \addToTail で追加する
    （音源シンセより後に処理されるよう順序を保証する）
  - ~effectBus を読む前に必ず In.ar(~effectBus, 2) で2ch読み込み
  - Spectral系はLocalBufを使う（FFTバッファはSynthDef内で完結）
*/

(
s.waitForBoot({

    // ── Effect Bus の確保 ─────────────────────────────────────────────
    // 全音源がここに送り込む。エフェクトシンセがここから読む。
    // run_headless.scd では s.waitForBoot 冒頭で確保する。
    if (~effectBus.isNil) {
        ~effectBus = Bus.audio(s, 2);
        "単独実行モード: ~effectBus を確保しました (bus: %)".format(~effectBus).postln;
    };

    // ▼▼▼ ここから run_headless.scd にコピー ▼▼▼

    // ── SynthDef 1: Global Delay ──────────────────────────────────────
    // ~effectBus から読んでディレイをかけて出力する。
    // AllpassC（アーリーリフレクション感）+ CombC（長いディレイ）の組み合わせ。
    // time: ディレイタイム（秒）、feedback: フィードバック量（0〜0.9）、mix: ドライ/ウェット
    SynthDef(\matoma_delay, {
        arg inBus,
            out     = 0,
            time     = 0.25,   // ディレイタイム（秒）
            feedback = 0.4,    // フィードバック量（0.0〜0.9）
            mix      = 0.35;   // ウェット量（0.0=ドライのみ、1.0=ウェットのみ）

        var sig, delayed, fb_sig, wet;

        sig = In.ar(inBus, 2);

        // LocalIn でフィードバックループを作る
        fb_sig = LocalIn.ar(2);

        // CombC でディレイ（最大2秒、L/R を少しずらして広がりを作る）
        delayed = [
            CombC.ar(sig[0] + (fb_sig[0] * feedback), 2.0, time,        time * 4.0),
            CombC.ar(sig[1] + (fb_sig[1] * feedback), 2.0, time * 1.03, time * 4.0)
        ];

        LocalOut.ar(delayed);

        // ドライ/ウェットミックス
        wet = XFade2.ar(sig, delayed, mix * 2 - 1);

        Out.ar(out, wet);
    }).add;

    s.sync;
    "エフェクト定義完了: \\matoma_delay".postln;

    // ── SynthDef 2: Spectral Freeze + Blur ───────────────────────────
    // FFT/PV_MagFreeze で音の瞬間を凍結する。
    // freeze=1.0 のとき現在のスペクトルを保持し続け、音が「永遠に鳴り続ける」。
    // blur が大きいほど周波数が隣のビンに滲んで「霞む」。
    // 参照: synthesis_spectral.md の PV_MagFreeze / PV_MagSmear
    SynthDef(\matoma_spectral_freeze, {
        arg inBus,
            out    = 0,
            freeze = 0.0,   // 0=通常、1=凍結
            blur   = 0;     // PV_MagSmear のスミア量（0〜8、整数）

        var sig, chain, frozen;
        var fftBuf = LocalBuf(2048);

        sig   = In.ar(inBus, 2);

        // FFT → PV処理 → IFFT
        // モノに落としてFFT（PV系UGenはモノのみ）→ IFFT でステレオに戻す
        chain  = FFT(fftBuf, sig[0] + sig[1] * 0.5);
        chain  = PV_MagFreeze(chain, freeze);
        chain  = PV_MagSmear(chain, blur.clip(0, 32).round.asInteger);
        frozen = IFFT(chain);

        // freeze=0 のときはドライ信号をそのまま通す
        // freeze=1 のとき凍結したスペクトルを出す
        Out.ar(out, XFade2.ar(sig, (frozen ! 2), freeze * 2 - 1));
    }).add;

    s.sync;
    "エフェクト定義完了: \\matoma_spectral_freeze".postln;

    // ── SynthDef 3: Wavefolder ────────────────────────────────────────
    // 波形を折り返して倍音を追加する。
    // drive が大きいほど高次倍音が増え、金属的・攻撃的なサウンドになる。
    // 参照: plugins_sc_quarks.md § 1-3. WaveFolding
    SynthDef(\matoma_wavefolder, {
        arg inBus,
            out   = 0,
            drive = 0.0,   // フォールド強度（0.0=バイパス、1.0=最大フォールド）
            mix   = 0.0;   // ドライ/ウェットミックス

        var sig, folded;

        sig = In.ar(inBus, 2);

        // drive に応じて信号を増幅してから fold(-1, 1) で折り返す
        // drive=0.0 → 1倍 → ほぼ変化なし
        // drive=1.0 → 6倍 → 積極的に折り返して倍音追加
        // 参照: plugins_sc_quarks.md の (sig * MouseX.kr(1, 8)).fold(-1, 1)
        folded = (sig * drive.linlin(0.0, 1.0, 1.0, 6.0)).fold(-1, 1);
        folded = LeakDC.ar(folded);

        // ウェットミックス（mix=0のときはドライのみ）
        Out.ar(out, XFade2.ar(sig, folded, mix * 2 - 1));
    }).add;

    s.sync;
    "エフェクト定義完了: \\matoma_wavefolder".postln;

    // ── SynthDef 4: Feedback Loop ─────────────────────────────────────
    // AllpassC + CombC で音が自律的にエコーし、予測不能な変化が生まれる。
    // amount が大きいほどフィードバックが増え、音が「育って」いく。
    // rate はエコーのリズム感（遅いと残響的、速いとトレモロ的）。
    SynthDef(\matoma_feedback_loop, {
        arg inBus,
            out    = 0,
            amount = 0.0,   // フィードバック量（0.0〜0.85。0.9以上は発散リスク）
            rate   = 0.5;   // ディレイ時間（秒）の基準値

        var sig, fb, fed;

        sig = In.ar(inBus, 2);

        // LocalIn/LocalOut でフィードバックループを構成
        fb = LocalIn.ar(2);

        // AllpassC: 拡散しながら遅延させる
        fed = AllpassC.ar(
            sig + (fb * amount.clip(0, 0.85)),
            2.0,
            [rate, rate * 1.07],   // L/R をわずかにずらしてフランジャー感
            rate * 3.0             // 残響時間
        );

        LocalOut.ar(fed);

        // amount=0 のときはドライのみ。増えるほど自律的なエコーが増える
        Out.ar(out, sig + (fed * amount));
    }).add;

    s.sync;
    "エフェクト定義完了: \\matoma_feedback_loop".postln;

    // ── SynthDef: パススルー（~effectBus → Out） ───────────────────────
    // effectBus の信号をそのまま出力するシンプルなルーター。
    // 最終防衛線: LeakDC で DC 除去 → Limiter で音量を 0.9 以下に制限
    SynthDef(\matoma_effect_out, {
        arg inBus, out = 0, amp = 1.0;
        var sig = In.ar(inBus, 2);
        sig = LeakDC.ar(sig);
        sig = Limiter.ar(sig * amp, 0.9, 0.01);
        Out.ar(out, sig);
    }).add;

    s.sync;
    "エフェクト定義完了: \\matoma_effect_out".postln;

    // ▲▲▲ ここまで run_headless.scd にコピー ▲▲▲

    // ── SynthDef 5: Glitch ────────────────────────────────────────────
    // 「エラーを音楽的素材として使う」ポスト・デジタル美学。
    // Kim Cascone: failure/malfunction を作曲素材として扱う哲学的転換。
    // 4モードを SelectX.ar で連続的にクロスフェード可能。
    //
    // mode 0: Latch + CoinGate スタッター（Alva Noto 的クリック）
    //   CoinGate で確率的タイミング → Latch でサンプルホールド
    //   Ringz で短い金属的共鳴を追加 → デジタルの粒
    //
    // mode 1: Gendy 確率合成 ミックス（池田良二・カオス的ノイズ）
    //   Xenakis の動的確率合成。波形の制御点がランダムウォーク。
    //   intensity で確率分布の型を切り替え → カオス素材を原音にブレンド
    //
    // mode 2: ビットクラッシュ + ダウンサンプリング（デジタル劣化）
    //   量子化 (round) + Latch + Impulse のコンボ
    //   intensity 高 → ビット数低 → 矩形波に近い激しい歪み
    //
    // mode 3: FFT スペクトルグリッチ（周波数破壊）
    //   PV_RandComb でランダムにビンを間引く（中空な質感）
    //   + PV_BinScramble でビンをシャッフル（調波構造破壊）
    //
    // 参照: sc_glitch_techniques.md
    // 参照: synthesis_spectral.md § PV_RandComb / PV_BinScramble
    SynthDef(\matoma_glitch, {
        arg inBus,
            out       = 0,
            density   = 0.3,   // グリッチ頻度（CoinGateの確率: 0.0〜1.0）
            intensity = 0.5,   // グリッチ強度（0.0〜1.0）
            mode      = 0,     // グリッチタイプ（0〜3の連続値）
            mix       = 0.5;   // ドライ/ウェット比（0.0〜1.0）

        var sig, mono;
        var m0, m1, m2, m3;
        var glitched;

        sig  = In.ar(inBus, 2);
        mono = (sig[0] + sig[1]) * 0.5;

        // ── mode 0: Latch + CoinGate スタッター（Alva Noto 的クリック） ──
        // CoinGate: density の確率で Impulse を通過させる（確率的リズム生成）
        // Latch: トリガーが来た瞬間のサンプル値をホールド → デジタルな「詰まり」
        // Ringz: ゲートが開いた瞬間に短い金属共鳴を付加 → デジタルの粒
        {
            var coinRate = density.linexp(0.0, 1.0, 2.0, 500.0);
            var gateTrig = CoinGate.ar(density, Impulse.ar(coinRate));
            var latchSig = Latch.ar(mono, gateTrig);
            var ring = Ringz.ar(gateTrig,
                Demand.ar(gateTrig, 0, Dwhite(500, 8000, inf)),
                0.01) * intensity * 0.3;
            m0 = latchSig + ring;
        }.value;

        // ── mode 1: Gendy 確率合成 ミックス（カオス的ノイズ） ─────────────
        // Gendy1: ヤニス・クセナキスの動的確率合成。
        // ampdist/durdist=5(EXPON) → 鋭い立ち上がりのパーカッシブなグリッチ（池田良二的）
        // intensity 高 → maxfreq ↑、initCPs/knum ↓ → よりカオス的
        {
            var gendySig = Gendy1.ar(
                ampdist:  intensity.linlin(0.0, 1.0, 0, 5).round,
                durdist:  intensity.linlin(0.0, 1.0, 0, 1).round,
                adparam:  intensity,
                ddparam:  intensity,
                minfreq:  20,
                maxfreq:  intensity.linexp(0.0, 1.0, 200.0, 8000.0),
                ampscale: intensity * 0.5,
                initCPs:  intensity.linlin(0.0, 1.0, 12.0, 1.0).round.max(1),
                knum:     intensity.linlin(0.0, 1.0, 12.0, 1.0).round.max(1)
            ) * 0.5;
            m1 = (mono * (1.0 - intensity * 0.7)) + (gendySig * intensity * 0.5);
        }.value;

        // ── mode 2: ビットクラッシュ + ダウンサンプリング（デジタル劣化） ──
        // 量子化: sig.round(2 ** (1 - bits)) → 低ビット → 矩形波に近い激しい歪み
        // ダウンサンプリング: Latch + Impulse → ナイキスト超の成分が可聴帯域に折り返す
        // density が高いほど resampleRate → 44100Hz（原音に近い）
        {
            var bits         = intensity.linlin(0.0, 1.0, 16.0, 1.0);
            var quantized    = mono.round(2 ** (1 - bits));
            var resampleRate = density.linexp(0.0, 1.0, 200.0, 44100.0);
            m2 = Latch.ar(quantized, Impulse.ar(resampleRate));
        }.value;

        // ── mode 3: FFT スペクトルグリッチ（周波数破壊） ─────────────────
        // PV_RandComb: ランダムにビンを間引く → 信号の密度を削ぎ落とす
        // PV_BinScramble: ビンをシャッフル → 調波構造を破壊 → 金属的ノイズ
        {
            var chain = FFT(LocalBuf(2048), mono);
            chain = PV_RandComb(chain, intensity * 0.9,
                Impulse.kr(density * 10));
            chain = PV_BinScramble(chain, intensity * 0.5, density * 0.3,
                Impulse.kr(density * 5));
            m3 = IFFT(chain);
        }.value;

        // ── SelectX.ar: 4モードをクロスフェードで連続切り替え ─────────────
        // mode は 0.0〜3.0 の連続値。整数境界でクロスフェード。
        glitched = SelectX.ar(mode.clip(0.0, 3.0), [m0, m1, m2, m3]);

        // ── Limiter: 出力保護（Gendy や FFT が発散しないよう intensity 分増幅してから制限）
        glitched = Limiter.ar(glitched * (1.0 + intensity), 0.95, 0.01);

        // ── LeakDC: DC オフセット除去 ─────────────────────────────────
        glitched = LeakDC.ar(glitched);

        // ── ドライ/ウェットミックス → ステレオ ─────────────────────────
        // mix=0 でドライのみ、mix=1 でグリッチのみ
        Out.ar(out, XFade2.ar(mono, glitched, mix * 2 - 1) ! 2);
    }).add;

    s.sync;
    "エフェクト定義完了: \\matoma_glitch".postln;

    // ── グローバル変数の初期化 ────────────────────────────────────────
    ~currentDelay       = nil;
    ~currentSpectralFrz = nil;
    ~currentWavefolder  = nil;
    ~currentFeedback    = nil;
    ~currentGlitch      = nil;
    ~currentEffectOut   = nil;

    // ── パススルーを起動（effectBus → ハード出力への出口を確保） ─────
    // エフェクトが何も起動していなくても ~effectBus の音が聞こえるようにする
    {
        ~currentEffectOut = Synth(\matoma_effect_out, [
            \inBus, ~effectBus,
            \out, 0
        ], addAction: \addToTail);
        "パススルー起動: ~effectBus → Out(0)".postln;
    }.defer;

    // ══════════════════════════════════════════════════════════════════
    // OSCdef: Global Delay
    // ══════════════════════════════════════════════════════════════════
    OSCdef(\matoma_delay_start, { |msg|
        {
            if (~currentDelay.notNil) { ~currentDelay.free; };
            ~currentDelay = Synth(\matoma_delay, [
                \inBus, ~effectBus,
                \out, 0
            ], addAction: \addToTail);
            "ディレイ エフェクト開始".postln;
        }.defer;
    }, '/matoma/effect/delay/start');

    OSCdef(\matoma_delay_stop, { |msg|
        {
            if (~currentDelay.notNil) {
                ~currentDelay.free;
                ~currentDelay = nil;
                "ディレイ エフェクト停止".postln;
            };
        }.defer;
    }, '/matoma/effect/delay/stop');

    OSCdef(\matoma_delay_param, { |msg|
        var param = msg[1].asSymbol;
        var value = msg[2].asFloat;
        {
            if (~currentDelay.notNil) {
                ~currentDelay.set(param, value);
                "ディレイ param: % = %".format(param, value.round(0.001)).postln;
            };
        }.defer;
    }, '/matoma/effect/delay/param');

    // ══════════════════════════════════════════════════════════════════
    // OSCdef: Spectral Freeze
    // ══════════════════════════════════════════════════════════════════
    OSCdef(\matoma_spectral_freeze_start, { |msg|
        {
            if (~currentSpectralFrz.notNil) { ~currentSpectralFrz.free; };
            ~currentSpectralFrz = Synth(\matoma_spectral_freeze, [
                \inBus, ~effectBus,
                \out, 0
            ], addAction: \addToTail);
            "スペクトラルフリーズ エフェクト開始".postln;
        }.defer;
    }, '/matoma/effect/spectral/start');

    OSCdef(\matoma_spectral_freeze_stop, { |msg|
        {
            if (~currentSpectralFrz.notNil) {
                ~currentSpectralFrz.free;
                ~currentSpectralFrz = nil;
                "スペクトラルフリーズ エフェクト停止".postln;
            };
        }.defer;
    }, '/matoma/effect/spectral/stop');

    OSCdef(\matoma_spectral_freeze_param, { |msg|
        var param = msg[1].asSymbol;
        var value = msg[2].asFloat;
        {
            if (~currentSpectralFrz.notNil) {
                ~currentSpectralFrz.set(param, value);
                "スペクトラルフリーズ param: % = %".format(param, value.round(0.001)).postln;
            };
        }.defer;
    }, '/matoma/effect/spectral/param');

    // ══════════════════════════════════════════════════════════════════
    // OSCdef: Wavefolder
    // ══════════════════════════════════════════════════════════════════
    OSCdef(\matoma_wavefolder_start, { |msg|
        {
            if (~currentWavefolder.notNil) { ~currentWavefolder.free; };
            ~currentWavefolder = Synth(\matoma_wavefolder, [
                \inBus, ~effectBus,
                \out, 0
            ], addAction: \addToTail);
            "ウェーブフォルダー エフェクト開始".postln;
        }.defer;
    }, '/matoma/effect/wavefolder/start');

    OSCdef(\matoma_wavefolder_stop, { |msg|
        {
            if (~currentWavefolder.notNil) {
                ~currentWavefolder.free;
                ~currentWavefolder = nil;
                "ウェーブフォルダー エフェクト停止".postln;
            };
        }.defer;
    }, '/matoma/effect/wavefolder/stop');

    OSCdef(\matoma_wavefolder_param, { |msg|
        var param = msg[1].asSymbol;
        var value = msg[2].asFloat;
        {
            if (~currentWavefolder.notNil) {
                ~currentWavefolder.set(param, value);
                "ウェーブフォルダー param: % = %".format(param, value.round(0.001)).postln;
            };
        }.defer;
    }, '/matoma/effect/wavefolder/param');

    // ══════════════════════════════════════════════════════════════════
    // OSCdef: Feedback Loop
    // ══════════════════════════════════════════════════════════════════
    OSCdef(\matoma_feedback_loop_start, { |msg|
        {
            if (~currentFeedback.notNil) { ~currentFeedback.free; };
            ~currentFeedback = Synth(\matoma_feedback_loop, [
                \inBus, ~effectBus,
                \out, 0
            ], addAction: \addToTail);
            "フィードバックループ エフェクト開始".postln;
        }.defer;
    }, '/matoma/effect/feedback/start');

    OSCdef(\matoma_feedback_loop_stop, { |msg|
        {
            if (~currentFeedback.notNil) {
                ~currentFeedback.free;
                ~currentFeedback = nil;
                "フィードバックループ エフェクト停止".postln;
            };
        }.defer;
    }, '/matoma/effect/feedback/stop');

    OSCdef(\matoma_feedback_loop_param, { |msg|
        var param = msg[1].asSymbol;
        var value = msg[2].asFloat;
        {
            if (~currentFeedback.notNil) {
                ~currentFeedback.set(param, value);
                "フィードバックループ param: % = %".format(param, value.round(0.001)).postln;
            };
        }.defer;
    }, '/matoma/effect/feedback/param');

    // ══════════════════════════════════════════════════════════════════
    // OSCdef: Glitch
    // ══════════════════════════════════════════════════════════════════
    OSCdef(\matoma_glitch_start, { |msg|
        {
            if (~currentGlitch.notNil) { ~currentGlitch.free; };
            ~currentGlitch = Synth(\matoma_glitch, [
                \inBus, ~effectBus,
                \out, 0
            ], target: ~currentEffectOut, addAction: \addBefore);
            "グリッチ エフェクト開始".postln;
        }.defer;
    }, '/matoma/effect/glitch/start');

    OSCdef(\matoma_glitch_stop, { |msg|
        {
            if (~currentGlitch.notNil) {
                ~currentGlitch.free;
                ~currentGlitch = nil;
                "グリッチ エフェクト停止".postln;
            };
        }.defer;
    }, '/matoma/effect/glitch/stop');

    OSCdef(\matoma_glitch_param, { |msg|
        var param = msg[1].asSymbol;
        var value = msg[2].asFloat;
        var allowed = #[\intensity, \density, \mode, \mix];
        {
            if (allowed.includes(param).not) {
                "グリッチ param: 許可されていないパラメーター '%' を無視".format(param).postln;
            } {
                if (~currentGlitch.notNil) {
                    ~currentGlitch.set(param, value);
                    "グリッチ param: % = %".format(param, value.round(0.001)).postln;
                };
            };
        }.defer;
    }, '/matoma/effect/glitch/param');

    "MaToMa エフェクト層起動完了".postln;
    "".postln;
    "── 動作確認コマンド ──────────────────────────────────────────".postln;
    "ディレイ起動:           NetAddr('127.0.0.1', 57120).sendMsg('/matoma/effect/delay/start')".postln;
    "ディレイタイム変更:     NetAddr('127.0.0.1', 57120).sendMsg('/matoma/effect/delay/param', 'time', 0.375)".postln;
    "フィードバック量:       NetAddr('127.0.0.1', 57120).sendMsg('/matoma/effect/delay/param', 'feedback', 0.6)".postln;
    "スペクトラル凍結:       NetAddr('127.0.0.1', 57120).sendMsg('/matoma/effect/spectral/start')".postln;
    "フリーズON:             NetAddr('127.0.0.1', 57120).sendMsg('/matoma/effect/spectral/param', 'freeze', 1.0)".postln;
    "フリーズOFF:            NetAddr('127.0.0.1', 57120).sendMsg('/matoma/effect/spectral/param', 'freeze', 0.0)".postln;
    "ウェーブフォルダー:     NetAddr('127.0.0.1', 57120).sendMsg('/matoma/effect/wavefolder/start')".postln;
    "フォールドON:           NetAddr('127.0.0.1', 57120).sendMsg('/matoma/effect/wavefolder/param', 'drive', 0.7)".postln;
    "フィードバックループ:   NetAddr('127.0.0.1', 57120).sendMsg('/matoma/effect/feedback/start')".postln;
    "フィードバック増加:     NetAddr('127.0.0.1', 57120).sendMsg('/matoma/effect/feedback/param', 'amount', 0.6)".postln;
    "グリッチ起動:           NetAddr('127.0.0.1', 57120).sendMsg('/matoma/effect/glitch/start')".postln;
    "グリッチmode0(CoinGate+Latch):NetAddr('127.0.0.1', 57120).sendMsg('/matoma/effect/glitch/param', 'mode', 0.0)".postln;
    "グリッチmode1(Gendy):   NetAddr('127.0.0.1', 57120).sendMsg('/matoma/effect/glitch/param', 'mode', 1.0)".postln;
    "グリッチmode2(ビットクラッシュ):NetAddr('127.0.0.1', 57120).sendMsg('/matoma/effect/glitch/param', 'mode', 2.0)".postln;
    "グリッチmode3(FFTスペクトル):NetAddr('127.0.0.1', 57120).sendMsg('/matoma/effect/glitch/param', 'mode', 3.0)".postln;
    "グリッチ強度:           NetAddr('127.0.0.1', 57120).sendMsg('/matoma/effect/glitch/param', 'intensity', 0.8)".postln;
    "グリッチ頻度:           NetAddr('127.0.0.1', 57120).sendMsg('/matoma/effect/glitch/param', 'density', 0.5)".postln;
    "グリッチ停止:           NetAddr('127.0.0.1', 57120).sendMsg('/matoma/effect/glitch/stop')".postln;
});
)
