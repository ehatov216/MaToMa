#!/usr/bin/env python3
"""
LLM Wiki 差分Ingestツール
=========================
UnifiedScraper DB と ingested_urls.txt を突き合わせ、
未取り込みの記事を抽出してClaudeのIngest作業に渡す。

使い方:
    python tools/ingest_diff.py                         # ソース別の未取り込み件数一覧
    python tools/ingest_diff.py --source sc_help_files  # 指定ソースの記事を出力
    python tools/ingest_diff.py --source sc_help_files --limit 5  # 5件だけ出力
    python tools/ingest_diff.py --mark <url>            # 指定URLをIngest済みとして登録
    python tools/ingest_diff.py --mark-batch <file>     # ファイル内の全URLを一括登録

出力形式:
    Claudeがそのまま読んでLLM Wikiに統合できるよう、
    1記事ずつ「URL / タイトル / 本文」を区切り付きで出力する。
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path("/Users/yusuke.kawakami/dev/UnifiedScraper/projects/sc_knowledge/db/sc_knowledge.db")
INGESTED_URLS_PATH = REPO_ROOT / "knowledge" / "rag" / "ingested_urls.txt"
MIN_CONTENT_LENGTH = 200  # これ未満は取得失敗とみなす


def load_ingested_urls() -> set[str]:
    """ingested_urls.txt から取り込み済みURLのセットを返す。"""
    if not INGESTED_URLS_PATH.exists():
        return set()
    lines = INGESTED_URLS_PATH.read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip() and not line.startswith("#")}


def mark_as_ingested(urls: list[str]) -> None:
    """URLをingested_urls.txtに追記する。"""
    existing = load_ingested_urls()
    new_urls = [u for u in urls if u not in existing]
    if not new_urls:
        print("すべて登録済みです。")
        return
    with INGESTED_URLS_PATH.open("a", encoding="utf-8") as f:
        for url in new_urls:
            f.write(f"{url}\n")
    print(f"{len(new_urls)} 件を ingested_urls.txt に追記しました。")


def list_summary(conn: sqlite3.Connection, ingested: set[str]) -> None:
    """ソース別の未取り込み件数を表示する。"""
    rows = conn.execute(
        "SELECT company_handler_id, url FROM articles WHERE length(content) >= ?",
        (MIN_CONTENT_LENGTH,),
    ).fetchall()

    counts: dict[str, int] = {}
    for handler_id, url in rows:
        if url not in ingested:
            counts[handler_id] = counts.get(handler_id, 0) + 1

    if not counts:
        print("未取り込み記事はありません。")
        return

    total = sum(counts.values())
    print(f"{'ソース':<40} {'未取り込み':>8}")
    print("-" * 50)
    for handler_id, cnt in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"{handler_id:<40} {cnt:>8}")
    print("-" * 50)
    print(f"{'合計':<40} {total:>8}")


def fetch_articles(
    conn: sqlite3.Connection,
    ingested: set[str],
    source: str,
    limit: int,
) -> list[dict]:
    """指定ソースの未取り込み記事を取得する。"""
    rows = conn.execute(
        """
        SELECT url, title, content, published_at
        FROM articles
        WHERE company_handler_id = ?
          AND length(content) >= ?
        ORDER BY scraped_at ASC
        """,
        (source, MIN_CONTENT_LENGTH),
    ).fetchall()

    articles = []
    for url, title, content, published_at in rows:
        if url in ingested:
            continue
        articles.append({
            "url": url,
            "title": title,
            "content": content,
            "published_at": published_at,
        })
        if len(articles) >= limit:
            break
    return articles


def print_articles(articles: list[dict]) -> None:
    """Claudeが読みやすい形式で記事を出力する。"""
    sep = "=" * 60

    print(f"\n{sep}")
    print(f"取り込み対象: {len(articles)} 件")
    print(sep)

    for i, article in enumerate(articles, 1):
        print(f"\n{'─' * 60}")
        print(f"[{i}/{len(articles)}] {article['title']}")
        print(f"URL: {article['url']}")
        if article["published_at"]:
            print(f"公開日: {article['published_at']}")
        print(f"{'─' * 60}")
        print(article["content"][:3000])  # 長すぎる記事は冒頭3000字
        if len(article["content"]) > 3000:
            print(f"\n... （残り {len(article['content']) - 3000} 文字省略）")

    print(f"\n{sep}")
    print("Ingest完了後、以下のコマンドでURLを登録してください:")
    print(f"python tools/ingest_diff.py --mark-batch <URLリストファイル>")
    print(sep)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LLM Wiki 差分Ingestツール"
    )
    parser.add_argument(
        "--source", metavar="HANDLER_ID",
        help="取り込むソースのhandler_id（省略で件数一覧を表示）",
    )
    parser.add_argument(
        "--limit", type=int, default=10,
        help="1回のIngestで出力する最大件数（デフォルト: 10）",
    )
    parser.add_argument(
        "--mark", metavar="URL",
        help="指定URLをIngest済みとして登録",
    )
    parser.add_argument(
        "--mark-batch", metavar="FILE",
        help="ファイル内の全URL（1行1URL）をIngest済みとして一括登録",
    )
    args = parser.parse_args()

    # --mark / --mark-batch はDB不要
    if args.mark:
        mark_as_ingested([args.mark])
        return
    if args.mark_batch:
        batch_file = Path(args.mark_batch)
        if not batch_file.exists():
            print(f"エラー: {batch_file} が見つかりません", file=sys.stderr)
            sys.exit(1)
        urls = [
            line.strip()
            for line in batch_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
        mark_as_ingested(urls)
        return

    if not DB_PATH.exists():
        print(f"エラー: DB が見つかりません: {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    ingested = load_ingested_urls()
    conn = sqlite3.connect(DB_PATH)

    try:
        if args.source:
            articles = fetch_articles(conn, ingested, args.source, args.limit)
            if not articles:
                print(f"'{args.source}' に未取り込みの記事はありません。")
            else:
                print_articles(articles)
        else:
            list_summary(conn, ingested)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
