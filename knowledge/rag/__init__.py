"""RAG (Retrieval-Augmented Generation) system for knowledge base queries.

This module provides local RAG using ChromaDB and sentence-transformers.
Enables AI agents to retrieve relevant SC/Tidal documents for code generation.

Constitution Principle VII: Local-First Execution
All RAG dependencies are local; no external API calls are made.

Design:
- KnowledgeChunk: Atomic document unit with embedding metadata
- RetrievalResult: Query result with relevance scores
- KnowledgeIndexer: Build embeddings from Markdown documents
- KnowledgeRetriever: Vector similarity search
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class KnowledgeChunk:
    """Atomic unit of knowledge stored and retrieved from the vector database.

    Attributes:
        id: Unique identifier (format: source_doc_{hash}_{idx})
        content: Chunk text content (what gets embedded)
        source_file: Path to source doc (e.g., sa_synths.md)
        section: Section heading (e.g., sa_bass Parameters)
        category: Doc category (synth|sc_ugen|tc_syntax|ng_pattern)
        metadata: Additional context for filtering
        created_at: Timestamp when chunk was created/indexed
    """

    id: str
    content: str
    source_file: str
    section: str
    category: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "content": self.content,
            "source_file": self.source_file,
            "section": self.section,
            "category": self.category,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class RetrievalResult:
    """Result of a knowledge base query.

    Attributes:
        chunks: Retrieved KnowledgeChunk objects, ranked by relevance
        scores: Similarity scores (0.0 - 1.0) for each chunk
        query: Original query text
        total_results: Total matching chunks in database
        query_time_ms: Execution time in milliseconds
        source_distribution: Count by source (e.g., sa_synths.md: 2)
    """

    chunks: list[KnowledgeChunk] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)
    query: str = ""
    total_results: int = 0
    query_time_ms: float = 0.0
    source_distribution: dict[str, int] = field(default_factory=dict)

    def top_k(self, k: int = 3) -> list[tuple[str, float, str, str]]:
        """Get top K results as tuples."""
        results = []
        for i, chunk in enumerate(self.chunks[:k]):
            score = self.scores[i] if i < len(self.scores) else 0.0
            results.append((chunk.content, score, chunk.source_file, chunk.category))
        return results

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "query": self.query,
            "num_results": len(self.chunks),
            "total_results": self.total_results,
            "query_time_ms": self.query_time_ms,
            "source_distribution": self.source_distribution,
            "top_results": [
                {
                    "content": chunk.content[:150],
                    "score": score,
                    "source": chunk.source_file,
                    "category": chunk.category,
                }
                for chunk, score in zip(self.chunks[:3], self.scores[:3], strict=False)
            ],
        }


__all__ = ["KnowledgeChunk", "RetrievalResult"]
