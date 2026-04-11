#!/usr/bin/env python3
"""
SA エクスポートツール
====================
Sonic Anatomy の SQLite DB を読み込み、TidalCycles パターンファイル（JSON）を
patterns/sa/ に書き出す。ライブ前の準備作業として使う。

使い方:
    cd /Users/yusuke.kawakami/dev/MaToMa
    python tools/sa_export.py                   # 全レコードをエクスポート
    python tools/sa_export.py <track_id>        # 指定 track_id のみ
    python tools/sa_export.py --list            # DB 内のレコード一覧を表示
    python tools/sa_export.py --name <id> my_name  # 出力ファイルに名前をつける

出力形式 (patterns/sa/<track_id>.json):
    {
      "id": "<track_id>",
      "name": "<表示名>",
      "bpm": 132.5,
      "key": "F#m",
      "density": 0.7,
      "notes": "...",
      "rhythm_lines": ["d1 $ ...", ...],
      "harmony_lines": ["d5 $ ...", ...]
    }
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# backend を Python パスに追加
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from sonic_anatomy_bridge import (  # noqa: E402
    load_record,
    list_records,
    generate_tidal_seed,
)

PATTERNS_DIR = REPO_ROOT / "patterns" / "sa"


def _key_str(record) -> str:
    root = record.key_root or "?"
    mode = "m" if record.key_mode == "minor" else ""
    return f"{root}{mode}"


def export_one(track_id: str, name: str | None = None) -> Path:
    record = load_record(track_id)
    if record is None:
        raise ValueError(f"track_id={track_id!r} が DB に見つかりません")

    seed = generate_tidal_seed(record)

    display_name = name or track_id
    payload = {
        "id": track_id,
        "name": display_name,
        "bpm": round(record.bpm, 2),
        "key": _key_str(record),
        "density": round(record.onset_density, 3),
        "notes": seed.notes_str,
        "rhythm_lines": seed.rhythm_lines,
        "harmony_lines": seed.harmony_lines,
    }

    out_path = PATTERNS_DIR / f"{track_id}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"  ✓ {out_path.name}  bpm={payload['bpm']} key={payload['key']}"
          f"  rhythm={len(seed.rhythm_lines)} harm={len(seed.harmony_lines)}")
    return out_path


def export_all() -> None:
    records = list_records(limit=200)
    if not records:
        print("DB にレコードがありません")
        return
    print(f"エクスポート開始: {len(records)} レコード → {PATTERNS_DIR}/")
    ok, ng = 0, 0
    for r in records:
        try:
            export_one(r["track_id"])
            ok += 1
        except Exception as e:
            print(f"  ✗ {r['track_id']}: {e}")
            ng += 1
    print(f"\n完了: {ok} 件成功 / {ng} 件失敗")


def list_db() -> None:
    records = list_records(limit=200)
    if not records:
        print("レコードなし")
        return
    print(f"{'track_id':<36}  {'bpm':>6}  {'key':<6}  {'density':>7}")
    print("-" * 62)
    for r in records:
        print(f"{r['track_id']:<36}  {r['bpm']:>6.1f}  {r['key']:<6}  {r['density']:>7.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="SA DB → patterns/sa/*.json エクスポート")
    parser.add_argument("track_id", nargs="?", help="対象 track_id（省略で全エクスポート）")
    parser.add_argument("--list", action="store_true", help="DB 内レコード一覧を表示して終了")
    parser.add_argument("--name", metavar="NAME", help="出力ファイルの表示名（track_id 指定時のみ有効）")
    args = parser.parse_args()

    PATTERNS_DIR.mkdir(parents=True, exist_ok=True)

    if args.list:
        list_db()
    elif args.track_id:
        try:
            export_one(args.track_id, args.name)
        except ValueError as e:
            print(f"エラー: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        export_all()


if __name__ == "__main__":
    main()
