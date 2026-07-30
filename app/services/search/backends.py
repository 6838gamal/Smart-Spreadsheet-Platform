"""
Search backend abstraction — upgrade-ready design.

Phase 1  →  BM25Backend   (pure Python, rank-bm25, zero ML models)
Phase 2  →  EmbeddingBackend (sentence-transformers + FAISS, drop-in replacement)
Phase 3  →  HybridBackend (BM25 + dense retrieval re-ranked)

Switch backends by changing SearchService(backend=...) in search_service.py.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class ChunkResult:
    chunk_id: int          # PK in document_chunks table
    file_id: int
    file_name: str
    chunk_text: str
    chunk_index: int
    score: float
    doc_type: str | None = None
    language: str | None = None


# ── Abstract backend ──────────────────────────────────────────────────────────

class SearchBackend(ABC):
    """
    A search backend receives a list of chunk dicts (already loaded from DB)
    and a query string, and returns ranked ChunkResult objects.

    Implementations must be stateless — all state lives in the DB or in
    an external index that the backend manages.
    """

    @abstractmethod
    def search(
        self,
        query: str,
        chunks: list[dict],
        top_k: int = 5,
    ) -> list[ChunkResult]:
        """
        Args:
            query:  The user's question / search string.
            chunks: List of dicts with keys:
                        id, file_id, file_name, chunk_text,
                        chunk_index, doc_type, language
            top_k:  Maximum results to return.
        Returns:
            Ranked list of ChunkResult (best first).
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier shown in API responses ('bm25', 'embedding', …)."""
        ...


# ── BM25 backend (Phase 1) ────────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokeniser supporting Arabic & Latin."""
    text = text.lower()
    # Keep Arabic letters, Latin letters, digits; strip the rest
    tokens = re.findall(r"[\u0600-\u06FF\w]+", text)
    return [t for t in tokens if len(t) > 1]


class BM25Backend(SearchBackend):
    """
    Exact keyword search using BM25Okapi (rank-bm25).

    No model weights, no GPU, instant startup.
    Works well for Arabic and English because BM25 is language-agnostic.

    Upgrade path: replace with EmbeddingBackend when you want semantic matching.
    The interface is identical — only the constructor changes.
    """

    @property
    def name(self) -> str:
        return "bm25"

    def search(
        self,
        query: str,
        chunks: list[dict],
        top_k: int = 5,
    ) -> list[ChunkResult]:
        if not chunks or not query.strip():
            return []

        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            raise RuntimeError(
                "rank-bm25 is not installed. Run: uv add rank-bm25"
            )

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        corpus_tokens = [_tokenize(c["chunk_text"]) for c in chunks]
        # Filter empty documents (BM25 requires at least 1 token per doc)
        non_empty = [(i, t) for i, t in enumerate(corpus_tokens) if t]
        if not non_empty:
            return []

        indices, filtered_tokens = zip(*non_empty)
        bm25 = BM25Okapi(list(filtered_tokens))
        scores = bm25.get_scores(query_tokens)

        # Pair scores with original chunk dicts
        scored = sorted(
            zip(scores, [chunks[i] for i in indices]),
            key=lambda x: x[0],
            reverse=True,
        )

        results: list[ChunkResult] = []
        for score, chunk in scored[:top_k]:
            if score <= 0:
                continue
            results.append(ChunkResult(
                chunk_id=chunk["id"],
                file_id=chunk["file_id"],
                file_name=chunk.get("file_name", ""),
                chunk_text=chunk["chunk_text"],
                chunk_index=chunk["chunk_index"],
                score=float(score),
                doc_type=chunk.get("doc_type"),
                language=chunk.get("language"),
            ))

        return results
