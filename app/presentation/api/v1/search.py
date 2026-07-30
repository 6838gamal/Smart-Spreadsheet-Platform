"""
Search & Q&A API endpoints.

POST /api/v1/search/query        — extractive Q&A (sync JSON)
GET  /api/v1/search/stream       — generative Q&A via SSE (streams tokens)
GET  /api/v1/search/stats        — indexing stats for the current user
POST /api/v1/search/index/{id}   — manually (re-)index a specific file
"""
from __future__ import annotations
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.infrastructure.database.models import User, File
from app.infrastructure.database.models_intelligence import DocumentAnalysis, AnalysisStatus
from app.services.search.search_service import search_service

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    file_ids: list[int] | None = Field(default=None)
    top_k: int = Field(default=5, ge=1, le=20)


class SourceSchema(BaseModel):
    file_id: int
    file_name: str
    doc_type: str | None
    chunk_text: str
    chunk_index: int
    score: float


class QueryResponse(BaseModel):
    question: str
    answer: str
    answer_source: SourceSchema | None
    sources: list[SourceSchema]
    total_chunks_searched: int
    backend: str
    has_results: bool
    mode: str = "extractive"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/query", response_model=QueryResponse)
async def query_documents(
    body: QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Sync extractive Q&A. Returns the best matching passage as JSON.
    For real-time LLM answers, use GET /stream instead.
    """
    result = await search_service.query(
        db,
        user_id=current_user.id,
        question=body.question,
        file_ids=body.file_ids,
        top_k=body.top_k,
    )

    return QueryResponse(
        question=result.question,
        answer=result.answer,
        answer_source=SourceSchema(**vars(result.answer_source)) if result.answer_source else None,
        sources=[SourceSchema(**vars(s)) for s in result.sources],
        total_chunks_searched=result.total_chunks_searched,
        backend=result.backend,
        has_results=result.has_results,
        mode=result.mode,
    )


@router.get("/stream")
async def stream_answer(
    request: Request,
    question: str,
    file_ids: str | None = None,          # comma-separated IDs, e.g. "1,2,3"
    top_k: int = 6,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Server-Sent Events endpoint for real-time generative answers.

    Event types emitted:
      {"type":"sources", "sources":[...], "total": N}
      {"type":"token",   "text": "..."}          — 0-N times
      {"type":"done",    "mode": "llm"|"extractive"|"no_results"}
      {"type":"error",   "msg": "..."}
    """
    parsed_ids: list[int] | None = None
    if file_ids:
        try:
            parsed_ids = [int(x.strip()) for x in file_ids.split(",") if x.strip()]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid file_ids format")

    if not question.strip():
        raise HTTPException(status_code=400, detail="question must not be empty")

    async def event_generator():
        try:
            async for chunk in search_service.stream_answer(
                db,
                user_id=current_user.id,
                question=question,
                file_ids=parsed_ids,
                top_k=min(max(top_k, 1), 20),
            ):
                # Respect client disconnect
                if await request.is_disconnected():
                    break
                yield chunk
        except Exception as exc:
            logger.error("SSE stream error: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'msg': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
        },
    )


@router.get("/stats")
async def search_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return indexing statistics for the current user."""
    return await search_service.get_stats(db, user_id=current_user.id)


@router.post("/index/{file_id}")
async def index_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger (re-)indexing of a file."""
    file = (await db.execute(
        select(File).where(File.id == file_id, File.owner_id == current_user.id)
    )).scalar_one_or_none()
    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    analysis = (await db.execute(
        select(DocumentAnalysis)
        .where(
            DocumentAnalysis.file_id == file_id,
            DocumentAnalysis.status == AnalysisStatus.COMPLETED,
        )
        .order_by(DocumentAnalysis.id.desc())
    )).scalar_one_or_none()

    text = ""
    doc_type = None
    analysis_id = None

    if analysis and analysis.raw_text:
        text = analysis.raw_text
        doc_type = analysis.doc_type
        analysis_id = analysis.id
    else:
        from app.services.pipeline.pipeline_manager import _quick_text
        text = _quick_text(file.path, file.file_format)

    if not text.strip():
        return {"indexed": False, "reason": "No text found in this file. Run analysis first."}

    chunk_count = await search_service.index_document(
        db,
        file_id=file_id,
        analysis_id=analysis_id,
        user_id=current_user.id,
        text=text,
        doc_type=doc_type,
        language=analysis.language if analysis else None,
        filename=file.original_name,
    )

    return {
        "indexed": True,
        "file_id": file_id,
        "chunks": chunk_count,
        "source": "analysis" if analysis else "quick_extract",
    }
