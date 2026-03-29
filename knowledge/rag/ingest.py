import contextlib
import glob
import hashlib
import os
import re
from pathlib import Path
from typing import Any

import chromadb
import yaml
from loguru import logger
from sentence_transformers import SentenceTransformer

from knowledge.rag import KnowledgeChunk

# パス設定
BASE_DIR = Path(__file__).parent
DOCS_DIR = BASE_DIR / "documents"  # gitignore済み
SOURCES_DIR = BASE_DIR / "sources"  # Git管理済み
DB_DIR = BASE_DIR / "chroma_db"
COLLECTION_NAME = "sonic_anatomy_knowledge"

# モデル設定 (Apple Silicon対応の軽量モデル)
MODEL_NAME = "all-MiniLM-L6-v2"


def _chunk_id(filename: str, counter: int, content: str) -> str:
    """ファイル名・連番・コンテンツハッシュを組み合わせた一意IDを返す。"""
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:8]
    return f"{filename}_{counter:03d}_{content_hash}"


def parse_markdown(filepath: str) -> tuple[dict[str, Any], str]:
    """フロントマターと本文を分離する"""
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    # --- で囲まれたYAMLフロントマターを抽出
    match = re.match(r"^---\n(.*?)\n---\n(.*)", content, re.DOTALL)
    if match:
        yaml_text = match.group(1)
        body = match.group(2)
        try:
            metadata = yaml.safe_load(yaml_text) or {}
        except Exception:
            metadata = {}
        return metadata, body
    return {}, content


def chunk_text(
    text: str, source_file: str, max_length: int = 1000
) -> list[KnowledgeChunk]:
    """テキストを段落や見出し単位で分割する簡易チャンカー"""
    chunks = []
    paragraphs = re.split(r"\n\n+", text)

    current_chunk = ""
    current_section = "General"
    chunk_id_counter = 0
    filename = Path(source_file).stem

    for para in paragraphs:
        para_stripped = para.strip()
        if not para_stripped:
            continue

        # 見出しの検出
        header_match = re.match(r"^(#{1,6})\s+(.*)", para_stripped)
        if header_match:
            current_section = header_match.group(2).strip()

        over_limit = (
            len(current_chunk) + len(para_stripped) > max_length
            and current_chunk
        )
        if over_limit:
            stripped = current_chunk.strip()
            chunks.append(
                KnowledgeChunk(
                    id=_chunk_id(filename, chunk_id_counter, stripped),
                    content=stripped,
                    source_file=source_file,
                    section=current_section,
                    category="sc_tc",
                )
            )
            chunk_id_counter += 1
            current_chunk = para + "\n\n"
        else:
            current_chunk += para + "\n\n"

    if current_chunk.strip():
        stripped = current_chunk.strip()
        chunks.append(
            KnowledgeChunk(
                id=_chunk_id(filename, chunk_id_counter, stripped),
                content=stripped,
                source_file=source_file,
                section=current_section,
                category="sc_tc",
            )
        )

    return chunks


def ingest_documents() -> None:
    """Markdownドキュメントを読み込み、ChromaDBにインデックス化する。

    2つのソースから取り込む:
    - DOCS_DIR (documents/): gitignore済みのSC公式ドキュメント変換キャッシュ
    - SOURCES_DIR (sources/): Git管理済みのキュレーション済み合成ナレッジ
    """
    logger.info(f"ドキュメントディレクトリ: {DOCS_DIR}")
    logger.info(f"ソースディレクトリ: {SOURCES_DIR}")
    logger.info(f"データベースディレクトリ: {DB_DIR}")

    os.makedirs(DB_DIR, exist_ok=True)

    # 両ディレクトリからMarkdownを収集
    md_files = glob.glob(str(DOCS_DIR / "*.md"))
    source_files = (
        glob.glob(str(SOURCES_DIR / "*.md")) if SOURCES_DIR.exists() else []
    )

    if not md_files and not source_files:
        logger.warning("Markdownファイルが見つかりません。")
        return

    logger.info(
        f"{len(md_files)} 件 (documents/)"
        f" + {len(source_files)} 件 (sources/) を処理します..."
    )

    # チャンク化（categoryはmetadataから取得し、新インスタンスで設定）
    all_chunks: list[KnowledgeChunk] = []
    for filepath in md_files + source_files:
        metadata, body = parse_markdown(filepath)
        category = metadata.get("category", "sc_tc")
        for c in chunk_text(body, filepath):
            all_chunks.append(
                KnowledgeChunk(
                    id=c.id,
                    content=c.content,
                    source_file=c.source_file,
                    section=c.section,
                    category=category,
                )
            )

    logger.info(f"合計 {len(all_chunks)} 個のチャンクが生成されました。")

    # ベクトルDBの初期化
    logger.info("ChromaDBを初期化しています...")
    client = chromadb.PersistentClient(path=str(DB_DIR))

    # モデルの準備
    logger.info(f"埋め込みモデル ({MODEL_NAME}) をロードしています...")
    model = SentenceTransformer(MODEL_NAME)

    # コレクションの取得・作成
    with contextlib.suppress(Exception):
        client.delete_collection(name=COLLECTION_NAME)
    collection = client.create_collection(name=COLLECTION_NAME)

    # バッチ処理でインデックス化
    batch_size = 100
    total = len(all_chunks)
    for i in range(0, total, batch_size):
        batch = all_chunks[i:i + batch_size]

        ids = [c.id for c in batch]
        documents = [c.content for c in batch]
        metadatas = [
            {
                "source_file": c.source_file,
                "section": c.section,
                "category": c.category,
            }
            for c in batch
        ]

        embeddings = model.encode(documents).tolist()
        collection.add(  # type: ignore[arg-type]
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        done = min(i + batch_size, total)
        logger.debug(f"インデックス進捗: {done}/{total} チャンク完了")

    logger.success("インデックス化が完了しました!")


if __name__ == "__main__":
    ingest_documents()
