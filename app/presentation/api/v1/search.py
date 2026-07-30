"""
Search & Q&A API endpoints.

POST /api/v1/search/query      — ask a question, get an answer + sources
GET  /api/v1/search/stats      — indexing stats for the current user
POST /api/v1/search/index/{file_id} — manually (re-)index a specific file
"""
from __future__ import annotations
import logging

from fastapi import APIRouter, Depends, HTTPException, status
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


# ── Request / Response schemas ────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    file_ids: list[int] | None = Field(default=None, description="Scope search to these file IDs. Null = all files.")
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


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/query", response_model=QueryResponse)
async def query_documents(
    body: QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Ask a question and get an answer extracted from your processed documents.

    Phase 1: BM25 keyword search → extractive answer (the best matching passage).
    Phase 2 (future): dense embeddings + optional local LLM for generative answer.
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
    """
    Manually trigger (re-)indexing of a file.
    The file must belong to the current user and have a completed analysis.
    """
    # Verify ownership
    file = (await db.execute(
        select(File).where(File.id == file_id, File.owner_id == current_user.id)
    )).scalar_one_or_none()
    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    # Find latest completed analysis
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
        # Fall back to quick text extraction
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
