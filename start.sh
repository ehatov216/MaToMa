#!/usr/bin/env bash
# MaToMa 起動スクリプト
# 既存の競合プロセスをすべて停止してからクリーンスタートする

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/backend/.bridge.pid"

echo "=== MaToMa 起動 ==="

# ── 既存プロセスの停止 ──────────────────────────────────────────
echo "[1/3] 既存プロセスを停止中..."

# PIDファイルがあれば、そのプロセスを先にkill
if [[ -f "$PID_FILE" ]]; then
    OLD_PID=$(cat "$PID_FILE" 2>/dev/null || true)
    if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "  bridge.py (PID=$OLD_PID) を停止"
        kill "$OLD_PID" 2>/dev/null || true
        sleep 0.5
    fi
    rm -f "$PID_FILE"
fi

# 名前でも念のちkill（PIDファイルが残っていない場合を考慮）
pkill -f "python.*bridge\.py" 2>/dev/null || true
pkill -f "sclang"              2>/dev/null || true
pkill -f "scsynth"             2>/dev/null || true

echo "  待機中..."
sleep 1.5

# ── CoreAudio プリウォーム ──────────────────────────────────────
# scsynthを一瞬起動して停止することでCoreAudioを先にリセットさせる。
# 本番起動時にはCoreAudioがすでに安定しており、他アプリのストリームが
# 切断されなくなる。
echo "[2/4] CoreAudioプリウォーム中..."
SCSYNTH="/Applications/SuperCollider.app/Contents/Resources/scsynth"
if [[ -x "$SCSYNTH" ]]; then
    "$SCSYNTH" -u 57111 -o 2 -i 0 > /dev/null 2>&1 &
    PREWARM_PID=$!
    sleep 2
    kill "$PREWARM_PID" 2>/dev/null || true
    sleep 1
fi

# ── 起動 ────────────────────────────────────────────────────────
echo "[3/4] bridge.py を起動中..."
cd "$SCRIPT_DIR/backend"

echo "[4/4] 起動完了。Ctrl+C で停止します。"
echo ""
exec python bridge.py
