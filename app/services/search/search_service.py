"""
Search & Q&A service — Phase 1 (BM25 + Extractive) with optional GPT streaming.

Upgrade path:
    Phase 1  — BM25 keyword search, extractive answer (default, no API key needed)
    Phase 1b — same BM25 retrieval, but LLM synthesises a real answer if OPENAI_API_KEY is set
    Phase 2  — swap `BM25Backend()` for `EmbeddingBackend()` in __init__
    Phase 3  — full RAG with re-ranking

The public API (index_document / query / stream_answer) stays identical across phases.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import AsyncIterator

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
    mode: str = "extractive"   # "extractive" | "llm"


# ── Service ───────────────────────────────────────────────────────────────────

class SearchService:
    """
    Orchestrates document indexing and Q&A queries.

    Constructor injection allows swapping backends without touching callers:
        SearchService()                            # BM25 (Phase 1)
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
        Returns an improved extractive answer (no LLM key required).
        Use stream_answer() for the LLM-powered real-time version.
        """
        sources, total = await self._retrieve(db, user_id=user_id, question=question,
                                               file_ids=file_ids, top_k=top_k)

        if not sources:
            return QAResult(
                question=question,
                answer="",
                answer_source=None,
                sources=[],
                total_chunks_searched=total,
                backend=self._backend.name,
                has_results=False,
            )

        answer = self._synthesize_extractive(question, sources)
        return QAResult(
            question=question,
            answer=answer,
            answer_source=sources[0],
            sources=sources,
            total_chunks_searched=total,
            backend=self._backend.name,
            has_results=True,
            mode="extractive",
        )

    async def stream_answer(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        question: str,
        file_ids: list[int] | None = None,
        top_k: int = 6,
    ) -> AsyncIterator[str]:
        """
        Async generator that yields Server-Sent Events (SSE) strings.

        Event format (each item is a complete SSE frame):
            data: {"type": "sources", "sources": [...]}\\n\\n
            data: {"type": "token",   "text": "..."}\\n\\n   (0-n times)
            data: {"type": "done",    "mode": "llm"|"extractive"}\\n\\n
            data: {"type": "error",   "msg": "..."}\\n\\n
        """
        from app.core.config import settings

        sources, total = await self._retrieve(db, user_id=user_id, question=question,
                                               file_ids=file_ids, top_k=top_k)

        # ── 1. Emit sources first so the UI can show citations immediately ──
        sources_payload = [
            {
                "file_id": s.file_id,
                "file_name": s.file_name,
                "chunk_index": s.chunk_index,
                "chunk_text": s.chunk_text[:300],
                "score": round(s.score, 4),
                "doc_type": s.doc_type,
            }
            for s in sources
        ]
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources_payload, 'total': total}, ensure_ascii=False)}\n\n"

        if not sources:
            yield f"data: {json.dumps({'type': 'done', 'mode': 'no_results'}, ensure_ascii=False)}\n\n"
            return

        # ── 2. Try LLM streaming if key is set ──────────────────────────────
        api_key = settings.OPENAI_API_KEY
        if api_key:
            try:
                async for chunk in self._stream_llm(question, sources, api_key, settings.OPENAI_MODEL):
                    yield chunk
                yield f"data: {json.dumps({'type': 'done', 'mode': 'llm'}, ensure_ascii=False)}\n\n"
                return
            except Exception as exc:
                logger.warning("LLM streaming failed, falling back to extractive: %s", exc)

        # ── 3. Fallback: improved extractive (emit as a single token) ────────
        answer = self._synthesize_extractive(question, sources)
        yield f"data: {json.dumps({'type': 'token', 'text': answer}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'mode': 'extractive'}, ensure_ascii=False)}\n\n"

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _retrieve(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        question: str,
        file_ids: list[int] | None,
        top_k: int,
    ) -> tuple[list[SearchSource], int]:
        """Load chunks from DB and rank them. Returns (ranked_sources, total_chunks)."""
        stmt = select(DocumentChunk).where(DocumentChunk.user_id == user_id)
        if file_ids:
            stmt = stmt.where(DocumentChunk.file_id.in_(file_ids))
        rows = (await db.execute(stmt)).scalars().all()

        if not rows:
            return [], 0

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

        return sources, len(chunk_dicts)

    def _synthesize_extractive(self, question: str, sources: list[SearchSource]) -> str:
        """
        Improved extractive answer — picks the most relevant sentences from the
        top-scoring chunks and combines them into a coherent response.
        """
        if not sources:
            return ""

        q_words = set(re.findall(r"[\u0600-\u06FF\w]+", question.lower()))

        # Build a scored sentence pool from the top chunks
        candidates: list[tuple[float, str, str]] = []  # (score, file_name, sentence)

        for src_rank, src in enumerate(sources[:3]):
            sentences = re.split(r"(?<=[.!?؟\n])\s*", src.chunk_text)
            sentences = [s.strip() for s in sentences if len(s.strip()) > 15]
            for pos, sent in enumerate(sentences):
                s_words = set(re.findall(r"[\u0600-\u06FF\w]+", sent.lower()))
                overlap = len(q_words & s_words)
                # Discount by source rank and sentence position within chunk
                score = overlap / max(len(q_words), 1) - src_rank * 0.1 - pos * 0.01
                candidates.append((score, src.file_name, sent))

        if not candidates:
            return sources[0].chunk_text[:600].strip()

        candidates.sort(reverse=True)
        best_score, best_file, best_sent = candidates[0]

        # If no word overlap at all, just return the top chunk verbatim
        if best_score <= 0:
            return sources[0].chunk_text[:600].strip()

        # Gather the top 2-3 distinct sentences (from potentially different files)
        seen: set[str] = set()
        parts: list[str] = []
        for score, fname, sent in candidates:
            if sent in seen or len(parts) >= 3:
                break
            if score > 0:
                seen.add(sent)
                parts.append(sent)

        answer = " ".join(parts).strip()

        # Append source attribution if multi-file
        file_names = list(dict.fromkeys(fname for _, fname, _ in candidates[:3] if fname))
        if len(file_names) > 1:
            answer += f"\n\n(مصدر: {' · '.join(file_names[:2])})"

        return answer[:800] if len(answer) > 800 else answer

    async def _stream_llm(
        self,
        question: str,
        sources: list[SearchSource],
        api_key: str,
        model: str,
    ) -> AsyncIterator[str]:
        """Stream tokens from OpenAI Chat API."""
        import httpx

        # Build context block (up to 4000 chars total)
        context_parts: list[str] = []
        total_len = 0
        for src in sources:
            block = f"[{src.file_name}، مقطع {src.chunk_index + 1}]\n{src.chunk_text}"
            if total_len + len(block) > 4000:
                block = block[:4000 - total_len]
            context_parts.append(block)
            total_len += len(block)
            if total_len >= 4000:
                break

        context = "\n\n---\n\n".join(context_parts)

        messages = [
            {
                "role": "system",
                "content": (
                    "أنت مساعد ذكي متخصص في تحليل المستندات. "
                    "أجب على سؤال المستخدم بناءً على المحتوى المقدم فقط. "
                    "أجب بنفس لغة السؤال (عربي أو إنجليزي). "
                    "إذا لم يكن الجواب في المحتوى، قل ذلك بصراحة. "
                    "لا تخترع معلومات."
                ),
            },
            {
                "role": "user",
                "content": f"المحتوى:\n\n{context}\n\n---\n\nالسؤال: {question}",
            },
        ]

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": messages, "stream": True, "max_tokens": 1200},
            ) as resp:
                resp.raise_for_status()
                async for raw_line in resp.aiter_lines():
                    if not raw_line.startswith("data: "):
                        continue
                    payload = raw_line[6:]
                    if payload.strip() == "[DONE]":
                        break
                    try:
                        obj = json.loads(payload)
                        delta = obj["choices"][0]["delta"].get("content", "")
                        if delta:
                            yield f"data: {json.dumps({'type': 'token', 'text': delta}, ensure_ascii=False)}\n\n"
                    except Exception:
                        pass

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
