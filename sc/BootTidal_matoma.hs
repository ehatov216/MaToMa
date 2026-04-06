-- MaToMa BootTidal.hs
-- TidalCycles → MaToMa SuperCollider 直接OSC接続
--
-- 【設計】
--   SuperDirt を使わず、MaToMa 専用ポート 57200 に直接OSCを送る。
--   SC の rhythmic.scd が /matoma/rhythmic/trigger を受け取って音を鳴らす。
--
-- 【OSCメッセージ形式】
--   /matoma/rhythmic/trigger <s:string> <freq:float> <amp:float>
--   msg[1] = synth name (s)   → 例: "matoma_rhythmic_klank"
--   msg[2] = freq (Hz)        → 例: 440.0
--   msg[3] = amp (0.0〜1.0)  → 例: 0.5
--
-- 【Tidalでの使い方】
--   d1 $ s "matoma_rhythmic_klank" # amp 0.6
--   d1 $ s "matoma_rhythmic_fm" # n "0 3 5 7" # amp 0.5
--   d1 $ euclid 3 8 $ s "matoma_rhythmic_klank" # freq 440 # amp 0.7
--   hush   -- 全停止

:set -fno-warn-orphans -Wno-type-defaults -XMultiParamTypeClasses -XOverloadedStrings
:set prompt ""

import Sound.Tidal.Boot

-- MaToMa OSCターゲット（1行で記述 — GHCiスクリプトの複数行let制限を回避）
-- superdirtTarget を基に、MaToMa 専用ポート 57200 に向ける
-- oHandshake = False: SC側にハンドシェイク応答が不要なため
:{
let matomaTarget = superdirtTarget { oName = "MaToMa", oAddress = "127.0.0.1", oPort = 57200, oHandshake = False, oBusPort = Nothing }
:}

-- OSCメッセージのシェイプ定義
-- ArgList: Tidalが送るパラメーターを位置引数で定義する
--   ("s",    Nothing)        → synth名（必須、デフォルトなし）
--   ("freq", Just $ VF 440) → 周波数（デフォルト: 440Hz）
--   ("amp",  Just $ VF 0.5) → 音量（デフォルト: 0.5）
:{
let matomaShape = OSC "/matoma/rhythmic/trigger" $ ArgList [("s", Nothing), ("freq", Just $ VF 440.0), ("amp", Just $ VF 0.5)]
:}

default (Rational, Integer, Double, Pattern String)

-- Tidal を MaToMa ターゲットで起動
-- cCtrlListen = True : Python から /ctrl OSC を受け取り cF/cI で参照できるようにする
-- cCtrlPort = 6010   : Tidal Control Channel のポート（SC の 57200 とは別）
tidalInst <- mkTidalWith [(matomaTarget, [matomaShape])] (defaultConfig { cCtrlListen = True, cCtrlPort = 6010 })

instance Tidally where tidal = tidalInst

:set prompt "tidal> "
:set prompt-cont ""
