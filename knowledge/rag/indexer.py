"""
RAG Indexer: Build embeddings from Markdown (Spec 008 T012).

Processes Markdown files, chunks by section, generates embeddings,
and stores in ChromaDB for similarity search.

Layer 1 only: No external API calls; all processing is local.
"""

import hashlib
import re
from pathlib import Path

from loguru import logger

try:
    import chromadb

    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logger.warning("ChromaDB not installed; RAG indexing disabled")

from sonic_anatomy.knowledge.rag import KnowledgeChunk


class KnowledgeIndexer:
    """Index Markdown documents into ChromaDB for RAG retrieval."""

    def __init__(
        self,
        db_path: Path | None = None,
        collection_name: str = "sonic_anatomy_knowledge",
    ):
        """Initialize indexer.

        Args:
            db_path: ChromaDB dir (~/.cache/sonic_anatomy/chroma)
            collection_name: ChromaDB collection name
        """
        if not CHROMADB_AVAILABLE:
            raise RuntimeError("ChromaDB not installed. Run: poetry add chromadb")

        if db_path is None:
            db_path = Path.home() / ".cache" / "sonic_anatomy" / "chroma"

        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client (new API)
        self.client = chromadb.PersistentClient(path=str(self.db_path))
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        logger.info(f"RAG indexer initialized at {self.db_path}")

    def build(self, documents_dir: Path) -> int:
        """Index all Markdown files in directory.

        Args:
            documents_dir: Path to directory containing .md files

        Returns:
            Number of chunks indexed
        """
        documents_dir = Path(documents_dir)

        if not documents_dir.exists():
            logger.error(f"Documents directory not found: {documents_dir}")
            return 0

        md_files = sorted(documents_dir.glob("*.md"))
        logger.info(f"Found {len(md_files)} markdown files")

        total_chunks = 0

        for md_file in md_files:
            logger.info(f"Indexing {md_file.name}...")
            chunks = self._parse_markdown(md_file)
            total_chunks += len(chunks)

            # Store chunks in ChromaDB
            for chunk in chunks:
                self._store_chunk(chunk)

        logger.info(f"Indexed {total_chunks} chunks total")
        # NOTE: client.persist() was removed in ChromaDB ≥ 0.4;
        # PersistentClient auto-persists on every write.

        return total_chunks

    def _parse_markdown(self, md_file: Path) -> list[KnowledgeChunk]:
        """Parse Markdown file into chunks by section.

        Each level-2 heading (##) starts a new chunk.

        Args:
            md_file: Path to .md file

        Returns:
            List of KnowledgeChunk objects
        """
        content = md_file.read_text(encoding="utf-8")
        sections = re.split(r"^## ", content, flags=re.MULTILINE)

        chunks = []
        chunk_index = 0

        for section in sections:
            if not section.strip():
                continue

            # Extract section title (first line)
            lines = section.split("\n")
            section_title = lines[0].strip() if lines else "unknown"

            # Section content (everything after title)
            section_content = "\n".join(lines[1:]).strip()

            if not section_content:
                continue

            # Create chunk ID (deterministic — immune to PYTHONHASHSEED)
            chunk_hash = hashlib.sha256(section_title.encode()).hexdigest()[:4]
            chunk_id = f"{md_file.stem}_{chunk_index:03d}_{chunk_hash}"
            chunk_index += 1

            # Determine category from filename
            category = self._get_category(md_file.stem)

            chunk = KnowledgeChunk(
                id=chunk_id,
                content=section_content,
                source_file=md_file.name,
                section=section_title,
                category=category,
                metadata={
                    "docfile": md_file.stem,
                    "section_index": chunk_index,
                },
            )

            chunks.append(chunk)

        logger.info(f"Parsed {md_file.name}: {len(chunks)} sections")
        return chunks

    def _get_category(self, filename: str) -> str:
        """Infer document category from filename.

        Args:
            filename: Markdown filename (without .md)

        Returns:
            Category string (synth, sc_ugen, tc_syntax, ng_pattern, unknown)
        """
        if "synth" in filename:
            return "synth"
        elif "sc_ugen" in filename or "ugen" in filename:
            return "sc_ugen"
        elif "tc_syntax" in filename or "tidal" in filename:
            return "tc_syntax"
        elif "ng_pattern" in filename:
            return "ng_pattern"
        else:
            return "unknown"

    def _store_chunk(self, chunk: KnowledgeChunk) -> None:
        """Store chunk in ChromaDB.

        Args:
            chunk: KnowledgeChunk to store
        """
        # ChromaDB expects: ids, documents, embeddings (optional), metadatas
        # Embeddings are auto-generated if not provided

        self.collection.add(
            ids=[chunk.id],
            documents=[chunk.content],
            metadatas=[
                {
                    "source_file": chunk.source_file,
                    "section": chunk.section,
                    "category": chunk.category,
                    "created_at": chunk.created_at.isoformat(),
                }
            ],
        )

    def clear(self) -> None:
        """Delete all documents from collection."""
        # Delete by getting all IDs and deleting them
        results = self.collection.get()
        if results["ids"]:
            self.collection.delete(ids=results["ids"])
            logger.info(f"Cleared {len(results['ids'])} chunks")
            # NOTE: client.persist() was removed in ChromaDB ≥ 0.4;
            # PersistentClient auto-persists on every write.


def build_rag_index(documents_dir: Path | None = None) -> int:
    """CLI entry point for building RAG index.

    Usage:
        poetry run python -m sonic_anatomy.knowledge.rag.indexer build

    Args:
        documents_dir: Override default documents directory

    Returns:
        Number of chunks indexed
    """
    if documents_dir is None:
        documents_dir = Path(__file__).parent / "documents"

    try:
        indexer = KnowledgeIndexer()
        total = indexer.build(documents_dir)
        logger.info(f"✅ RAG index built: {total} chunks")
        return total
    except Exception as e:
        logger.error(f"❌ RAG indexing failed: {e}")
        raise


if __name__ == "__main__":
    build_rag_index()
