"""
SC OSC 疎通テスト
=================
Tidal を介さず Python から直接 OSC を SC ポート 57200 に送る。

使い方:
  cd ~/dev/MaToMa/backend
  python test_osc.py

成功した場合:
  SC のターミナル（bridge のログ）に
  「リズムトリガー: matoma_rhythmic_klank freq:440.0 amp:0.6」が表示され、
  Klank の金属音が鳴る。

失敗した場合:
  何も鳴らず、SC 側のログにも何も出ない
  → SC が 57200 を受信できていない（OSCdef 未登録か Port 未開放）
"""

import time
from pythonosc.udp_client import SimpleUDPClient

SC_HOST = "127.0.0.1"
SC_PORT = 57200
PATH = "/matoma/rhythmic/trigger"

TESTS = [
    ("matoma_rhythmic_klank", 440.0, 0.6),
    ("matoma_rhythmic_fm",    220.0, 0.5),
    ("matoma_rhythmic_spring", 330.0, 0.4),
]

client = SimpleUDPClient(SC_HOST, SC_PORT)

print(f"OSC テスト送信先: {SC_HOST}:{SC_PORT}")
print("音が鳴れば SC 疎通 OK。鳴らなければ SC 側の問題。\n")

for synth, freq, amp in TESTS:
    print(f"送信: {PATH} [{synth}] freq={freq} amp={amp}")
    client.send_message(PATH, [synth, float(freq), float(amp)])
    time.sleep(1.5)

print("\nテスト完了。")
