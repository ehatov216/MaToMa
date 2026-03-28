"""RAG Retriever: Query knowledge base using vector similarity (Spec 008 T013).

Performs vector similarity search using ChromaDB + sentence-transformers.
Returns ranked chunks with relevance scores.

**Layer 1 only**: No external API calls; all processing is local.
"""

import time
from pathlib import Path

from loguru import logger

try:
    import chromadb

    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

from knowledge.rag import KnowledgeChunk, RetrievalResult


class KnowledgeRetriever:
    """Query knowledge base using vector similarity search."""

    def __init__(
        self,
        db_path: Path | None = None,
        collection_name: str = "sonic_anatomy_knowledge",
        n_results: int = 5,
    ):
        """Initialize retriever.

        Args:
            db_path: ChromaDB dir (~/.cache/sonic_anatomy/chroma)
            collection_name: ChromaDB collection name
            n_results: Number of results to retrieve by default
        """
        if not CHROMADB_AVAILABLE:
            raise RuntimeError("ChromaDB not installed. Run: poetry add chromadb")

        if db_path is None:
            db_path = Path(__file__).parent / "chroma_db"

        self.db_path = Path(db_path)
        self.n_results = n_results

        if not self.db_path.exists():
            logger.warning(
                f"RAG database not found at {self.db_path}. "
                "Run: poetry run python -m "
                "sonic_anatomy.knowledge.rag.indexer build"
            )

        # Initialize ChromaDB client (new API)
        self.client = chromadb.PersistentClient(path=str(self.db_path))

        try:
            self.collection = self.client.get_collection(name=collection_name)
            count = self.collection.count()
            logger.info(f"RAG retriever initialized with {count} chunks")
        except Exception as e:
            logger.warning(f"Could not open RAG collection: {e}. " "Index may need to be rebuilt.")
            self.collection = None  # type: ignore[assignment]

    def query(
        self,
        text: str,
        n_results: int | None = None,
    ) -> RetrievalResult:
        """Query knowledge base.

        Args:
            text: Query text
            n_results: Override default result count

        Returns:
            RetrievalResult with top-K chunks
        """
        start_time = time.time()
        n_results = n_results or self.n_results

        result = RetrievalResult(query=text)

        if self.collection is None:
            logger.warning("RAG collection not loaded; returning empty result")
            result.query_time_ms = (time.time() - start_time) * 1000
            return result

        try:
            # Query ChromaDB (auto-embeds query)
            query_result = self.collection.query(
                query_texts=[text],
                n_results=n_results,
                include=["documents", "metadatas", "distances"],
            )

            # Convert ChromaDB results to RetrievalResult
            if query_result["ids"] and query_result["ids"][0]:
                doc_ids = query_result["ids"][0]
                documents = query_result["documents"][0]  # type: ignore[index]
                metadatas = query_result["metadatas"][0]  # type: ignore[index]
                distances = query_result["distances"][0]  # type: ignore[index]

                for doc_id, doc_text, metadata, distance in zip(
                    doc_ids, documents, metadatas, distances, strict=False
                ):
                    # Convert distance to similarity (cosine)
                    # Distance in range [0, 2]; Sim = 1 - (dist / 2)
                    similarity = 1.0 - (distance / 2.0)
                    similarity = max(0.0, min(1.0, similarity))

                    chunk = KnowledgeChunk(
                        id=doc_id,
                        content=doc_text,
                        source_file=metadata.get("source_file", "unknown"),
                        section=metadata.get("section", "unknown"),
                        category=metadata.get("category", "unknown"),
                        metadata=metadata,
                    )

                    result.chunks.append(chunk)
                    result.scores.append(similarity)

                # Count sources
                source_dist: dict[str, int] = {}
                for chunk in result.chunks:
                    src = chunk.source_file
                    source_dist[src] = source_dist.get(src, 0) + 1
                result.source_distribution = source_dist

            result.total_results = len(result.chunks)

        except Exception as e:
            logger.error(f"Query failed: {e}")

        result.query_time_ms = (time.time() - start_time) * 1000

        return result

    def search(
        self,
        text: str,
        top_k: int = 5,
    ) -> "RetrievalResult":
        """Alias for query() used by sc_llm_generator.

        Args:
            text: Query text
            top_k: Number of results to return

        Returns:
            RetrievalResult with top-K chunks
        """
        return self.query(text, n_results=top_k)

    def query_by_category(
        self,
        text: str,
        category: str,
        n_results: int | None = None,
    ) -> RetrievalResult:
        """Query filtered by category.

        Args:
            text: Query text
            category: Filter by category (synth, sc_ugen, tc_syntax)
            n_results: Number of results

        Returns:
            RetrievalResult filtered by category
        """
        # Full query first
        full_result = self.query(text, n_results=n_results or self.n_results)

        # Filter by category
        filtered_chunks = []
        filtered_scores = []

        for chunk, score in zip(full_result.chunks, full_result.scores, strict=False):
            if chunk.category == category:
                filtered_chunks.append(chunk)
                filtered_scores.append(score)

        full_result.chunks = filtered_chunks
        full_result.scores = filtered_scores
        full_result.total_results = len(filtered_chunks)

        return full_result


def query_rag(query_text: str, n_results: int = 3) -> RetrievalResult:
    """CLI entry point for querying RAG.

    Usage:
        poetry run python -m sonic_anatomy.knowledge.rag.retriever \\
            "LPF filter cutoff frequency"

    Args:
        query_text: Query string
        n_results: Number of results to return

    Returns:
        RetrievalResult
    """
    retriever = KnowledgeRetriever(n_results=n_results)
    result = retriever.query(query_text)

    logger.info(f"Query: {query_text}")
    logger.info(f"Results: {len(result.chunks)}")

    for i, (chunk, score) in enumerate(zip(result.chunks, result.scores, strict=False), 1):
        logger.info(f"  {i}. [{score:.2%}] {chunk.section} " f"({chunk.source_file})")
        logger.info(f"     {chunk.content[:100]}...")

    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        query_rag(sys.argv[1])
    else:
        print("Usage: python -m " "sonic_anatomy.knowledge.rag.retriever '<query>'")
