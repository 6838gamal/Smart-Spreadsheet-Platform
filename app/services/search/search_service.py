"""
Search & Q&A service — Phase 1 (BM25 + Extractive).

Upgrade path:
    Phase 1  — BM25 keyword search, extractive answer (this file, no changes needed to callers)
    Phase 2  — swap `BM25Backend()` for `EmbeddingBackend()` in __init__
    Phase 3  — add a local LLM call in `_generate_answer()` for generative responses

The public API (index_document / query) stays identical across phases.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.search.text_chunker import chunk_text
from app.services.search.backends import BM25Backend, SearchBackend, ChunkResult
from app.infrastructure.database.models_intelligence import DocumentChunk

logger = logging.getLogger(__name__)


# ── Result shapes ─────────────────────────────────────────────────────────────

@dataclass
class SearchSource:
    file_id: int
    file_name: str
    doc_type: str | None
    chunk_text: str
    chunk_index: int
    score: float


@dataclass
class QAResult:
    question: str
    answer: str            # best extractive answer
    answer_source: SearchSource | None
    sources: list[SearchSource]
    total_chunks_searched: int
    backend: str
    has_results: bool


# ── Service ───────────────────────────────────────────────────────────────────

class SearchService:
    """
    Orchestrates document indexing and Q&A queries.

    Constructor injection allows swapping backends without touching callers:
        SearchService()                        # BM25 (Phase 1)
        SearchService(backend=EmbeddingBackend())  # dense (Phase 2)
    """

    def __init__(self, backend: SearchBackend | None = None) -> None:
        self._backend: SearchBackend = backend or BM25Backend()

    # ── Indexing ──────────────────────────────────────────────────────────────

    async def index_document(
        self,
        db: AsyncSession,
        *,
        file_id: int,
        analysis_id: int | None,
        user_id: int,
        text: str,
        doc_type: str | None = None,
        language: str | None = None,
        filename: str = "",
    ) -> int:
        """
        Chunk *text* and store chunks in the DB.
        Existing chunks for *file_id* are replaced.
        Returns the number of chunks stored.
        """
        if not text or not text.strip():
            return 0

        # Remove old chunks for this file
        await db.execute(
            delete(DocumentChunk).where(DocumentChunk.file_id == file_id)
        )

        chunks = chunk_text(text)
        for ch in chunks:
            db.add(DocumentChunk(
                file_id=file_id,
                analysis_id=analysis_id,
                user_id=user_id,
                chunk_index=ch["chunk_index"],
                chunk_text=ch["chunk_text"],
                doc_type=doc_type,
                language=language,
                filename=filename,
            ))

        await db.commit()
        logger.info("Indexed %d chunks for file_id=%d (backend=%s)", len(chunks), file_id, self._backend.name)
        return len(chunks)

    # ── Querying ──────────────────────────────────────────────────────────────

    async def query(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        question: str,
        file_ids: list[int] | None = None,
        top_k: int = 5,
    ) -> QAResult:
        """
        Find the best matching passages for *question* across the user's documents.

        Phase 1: BM25 keyword search + extractive answer (top chunk returned as-is).
        Phase 2: swap backend → dense retrieval + re-ranking.
        Phase 3: pass top chunks to a local LLM for generative answer.
        """
        # Load all indexed chunks for this user (optionally filtered by file_ids)
        stmt = select(DocumentChunk).where(DocumentChunk.user_id == user_id)
        if file_ids:
            stmt = stmt.where(DocumentChunk.file_id.in_(file_ids))
        rows = (await db.execute(stmt)).scalars().all()

        if not rows:
            return QAResult(
                question=question,
                answer="",
                answer_source=None,
                sources=[],
                total_chunks_searched=0,
                backend=self._backend.name,
                has_results=False,
            )

        # Convert ORM rows to plain dicts for the backend
        chunk_dicts = [
            {
                "id": r.id,
                "file_id": r.file_id,
                "file_name": r.filename or f"ملف #{r.file_id}",
                "chunk_text": r.chunk_text,
                "chunk_index": r.chunk_index,
                "doc_type": r.doc_type,
                "language": r.language,
            }
            for r in rows
        ]

        results: list[ChunkResult] = self._backend.search(question, chunk_dicts, top_k=top_k)

        if not results:
            return QAResult(
                question=question,
                answer="",
                answer_source=None,
                sources=[],
                total_chunks_searched=len(chunk_dicts),
                backend=self._backend.name,
                has_results=False,
            )

        sources = [
            SearchSource(
                file_id=r.file_id,
                file_name=r.file_name,
                doc_type=r.doc_type,
                chunk_text=r.chunk_text,
                chunk_index=r.chunk_index,
                score=r.score,
            )
            for r in results
        ]

        best = sources[0]
        answer = self._extract_answer(question, best.chunk_text)

        return QAResult(
            question=question,
            answer=answer,
            answer_source=best,
            sources=sources,
            total_chunks_searched=len(chunk_dicts),
            backend=self._backend.name,
            has_results=True,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _extract_answer(self, question: str, passage: str) -> str:
        """
        Phase 1: return the passage itself (extractive).
        Phase 2: highlight the specific sentence that answers the question.
        Phase 3: call a local LLM with question + passage as context.
        """
        # Find the sentence most similar to the question (simple heuristic)
        q_words = set(re.findall(r"[\u0600-\u06FF\w]+", question.lower()))
        sentences = re.split(r"(?<=[.!?؟\n])\s*", passage)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

        if not sentences:
            return passage.strip()

        best_sent = max(
            sentences,
            key=lambda s: len(q_words & set(re.findall(r"[\u0600-\u06FF\w]+", s.lower()))),
        )

        # Return best sentence + surrounding context (up to 400 chars)
        idx = sentences.index(best_sent)
        context_sents = sentences[max(0, idx - 1): idx + 3]
        return " ".join(context_sents).strip() or passage[:400].strip()

    async def delete_chunks(self, db: AsyncSession, *, file_id: int) -> None:
        """Remove all indexed chunks for a file (e.g. on file deletion)."""
        await db.execute(delete(DocumentChunk).where(DocumentChunk.file_id == file_id))
        await db.commit()

    async def get_stats(self, db: AsyncSession, *, user_id: int) -> dict:
        """Return indexing stats for the user."""
        from sqlalchemy import func
        row = (await db.execute(
            select(
                func.count(DocumentChunk.id).label("total_chunks"),
                func.count(DocumentChunk.file_id.distinct()).label("indexed_files"),
            ).where(DocumentChunk.user_id == user_id)
        )).one()
        return {
            "total_chunks": row.total_chunks or 0,
            "indexed_files": row.indexed_files or 0,
            "backend": self._backend.name,
        }


# Singleton — import this everywhere
search_service = SearchService()
