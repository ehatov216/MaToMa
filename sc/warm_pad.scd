// ══════════════════════════════════════════════════════════════════
//  MaToMa warm_pad.scd  — 温かみのあるアンビエントパッド v1
//
//  【美学的立脚点】
//    Aphex Twin SAW 85-92期（SH-101ドローン・水没感）×
//    OPN（Juno-60コーラスパッド・生物的呼吸）
//
//  【設計原則】
//    - LFTri: Pulseより丸く温かい波形（倍音が少ない = 刺さらない）
//    - tanh サチュレーション: アナログ的な偶数倍音 → warmth の核
//    - cutoff 1000Hz: knowledge.md「温かい」= 800-1200Hz
//    - GVerb (revtime:12, roomsize:100): drone session 5で確認済みの長残響
//    - 呼吸レート 0.06Hz（約16秒周期）: OPN的「生物的呼吸」
//    - デチューンユニゾン ±0.5Hz: 浮遊感・コーラス感
//    - Attack 5秒 / Release 8秒: アンビエントらしい滑らかな包み込み
//
//  【OSCアドレス】
//    /matoma/pad/start  → パッドを開始（引数なし）
//    /matoma/pad/stop   → フェードアウトして停止
//    /matoma/pad/param  → ['/matoma/pad/param', 'パラメーター名', 値]
//      対応パラメーター: freq, amp, breath_rate, cutoff, warmth, room_size
// ══════════════════════════════════════════════════════════════════

SynthDef(\matoma_warm_pad, {
    arg freq        = 220,    // 根音 (Hz)
        amp         = 0.22,   // 音量
        gate        = 1,      // 1=鳴る、0=フェードアウト
        breath_rate = 0.06,   // 呼吸の速さ (Hz)。0.06=約16秒周期
        cutoff      = 1000,   // フィルター閾値 (Hz)。800-1200=温かい帯域
        warmth      = 1.3,    // tanh サチュレーション強度。大=より倍音豊か
        room_size   = 100;    // GVerb の部屋サイズ (m²)

    // ── var 宣言（SC: すべての var は関数先頭に置く必要あり）──────────
    var breath, breathSlow, sigs, sig, wet, env;

    // ── 呼吸変調 LFO ──────────────────────────────────────────────
    // 16秒かけてゆっくり膨らみ収縮する。生物の呼吸に近いSinOsc形状。
    breath     = SinOsc.kr(breath_rate).range(0.62, 1.0);
    // フィルター用には少し遅い位相で揺らす（呼吸とフィルターのずれが自然さを生む）
    breathSlow = SinOsc.kr(breath_rate * 0.5, 0.25pi).range(0.85, 1.15);

    // ── オシレーター: LFTri デチューンユニゾン ───────────────────────
    // LFTri = 三角波。SawよりもPulseよりも丸く、Sinよりも倍音がある。
    // 3本 ± 小さなずれ + サブオクターブ + ハーモニクスで体積を作る。
    sigs = [
        LFTri.ar(freq * 1.0023),          // わずか上にずれた根音
        LFTri.ar(freq * 0.9977),          // わずか下にずれた根音
        LFTri.ar(freq * 0.5013, 0, 0.45), // サブオクターブ（音の土台）
        SinOsc.ar(freq * 2.0031, 0, 0.22) // 2オクターブ上のサイン（空気感）
    ];

    // Splay でステレオに展開し、呼吸で振幅を揺らす
    sig = Splay.ar(sigs) * breath;

    // ── RLPF フィルター ────────────────────────────────────────────
    // cutoff=1000Hz × breathSlow で呼吸に連動して音の明るさが変わる
    sig = RLPF.ar(sig,
        (cutoff * breathSlow).clip(200, 4000),
        0.55  // rq: 0.55 = 柔らかいレゾナンス（尖らせない）
    );

    // ── tanh サチュレーション ──────────────────────────────────────
    // アナログ回路の飽和を模倣。偶数倍音が加わり「温かみ」の核になる。
    // warmth=1.3: 強すぎず弱すぎない。2.0以上は歪み感が強くなる。
    sig = tanh(sig * warmth) * (1.0 / warmth.tanh);  // 正規化して音量を保持

    // ── GVerb: 長残響による「天井の高い空間」──────────────────────
    // roomsize=100 (m²), revtime=12s は drone session 5 で確認済みの値。
    // damping=0.18: 高域の残響を少し抑えて暖かみを維持。
    // inputbw=0.8: 入力の高域をわずかにカットしてリバーブを柔らかく。
    wet = GVerb.ar(
        sig.sum,
        roomsize: room_size,
        revtime:  12,
        damping:  0.18,
        inputbw:  0.8,
        mul:      0.38
    );

    // ドライ + ウェット（モノ sum → ステレオへ展開）
    sig = sig + wet.dup(2) * 0.5;

    // ── エンベロープ ────────────────────────────────────────────────
    // attack=5.0秒: アンビエントらしいゆっくりした立ち上がり
    // release=8.0秒: gate=0でゆっくりフェードアウト
    env = EnvGen.ar(
        Env.adsr(5.0, 0.5, 0.85, 8.0),
        gate,
        doneAction: 2
    );

    Out.ar(0, sig * env * amp);
}).add;

// ── 状態変数 ────────────────────────────────────────────────────────
~currentPad = nil;

// ── OSCdef: パッド開始 ──────────────────────────────────────────────
OSCdef(\matoma_pad_start, { |msg|
    {
        if (~currentPad.notNil) {
            ~currentPad.set(\gate, 0);  // 旧パッドをフェードアウト
        };
        ~currentPad = Synth(\matoma_warm_pad, addAction: \addToTail);
        "温かみパッド 開始".postln;
    }.defer;
}, '/matoma/pad/start', nil, 57200);

// ── OSCdef: パッド停止 ──────────────────────────────────────────────
OSCdef(\matoma_pad_stop, { |msg|
    {
        if (~currentPad.notNil) {
            ~currentPad.set(\gate, 0);  // gate=0 → 8秒かけてフェードアウト
            ~currentPad = nil;
            "温かみパッド フェードアウト開始（8秒）".postln;
        };
    }.defer;
}, '/matoma/pad/stop', nil, 57200);

// ── OSCdef: パラメーター更新 ────────────────────────────────────────
OSCdef(\matoma_pad_param, { |msg|
    var param = msg[1].asSymbol;
    var value = msg[2].asFloat;
    var allowed = #[\freq, \amp, \breath_rate, \cutoff, \warmth, \room_size];
    {
        if (allowed.includes(param) && ~currentPad.notNil) {
            ~currentPad.set(param, value);
            "温かみパッド パラメーター更新: % = %".format(param, value.round(0.001)).postln;
        };
    }.defer;
}, '/matoma/pad/param', nil, 57200);

"温かみパッド (\\matoma_warm_pad) ロード完了".postln;
