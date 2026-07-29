"""
Document Intelligence API — v1 endpoints.
Handles: trigger analysis, fetch results, entities, tables, suggestions, feedback.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.infrastructure.database.models import User, File
from app.infrastructure.database.models_intelligence import (
    DocumentAnalysis, AnalysisStatus, LayoutElement, ExtractedTable,
    ExtractedEntity, AISuggestion, UserFeedback, ProcessingJob,
)
from app.jobs.job_queue import job_queue

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    feedback_type: str
    original_value: str | None = None
    corrected_value: str | None = None
    field_name: str | None = None
    rating: int | None = None
    comment: str | None = None


class EntityCorrection(BaseModel):
    corrected_value: str


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _get_file_or_404(file_id: int, user_id: int, db: AsyncSession) -> File:
    result = await db.execute(
        select(File).where(File.id == file_id, File.owner_id == user_id)
    )
    f = result.scalar_one_or_none()
    if not f:
        raise HTTPException(404, "File not found")
    return f


async def _get_analysis_or_404(analysis_id: int, db: AsyncSession) -> DocumentAnalysis:
    a = await db.get(DocumentAnalysis, analysis_id)
    if not a:
        raise HTTPException(404, "Analysis not found")
    return a


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/analyze/{file_id}")
async def start_analysis(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger full document intelligence analysis."""
    file = await _get_file_or_404(file_id, current_user.id, db)

    # Check for existing pending/running analysis
    result = await db.execute(
        select(DocumentAnalysis).where(
            DocumentAnalysis.file_id == file_id,
            DocumentAnalysis.status.in_([AnalysisStatus.PENDING, AnalysisStatus.RUNNING])
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return {"analysis_id": existing.id, "job_status": existing.status.value, "message": "Analysis already in progress"}

    # Create analysis record
    analysis = DocumentAnalysis(
        file_id=file_id,
        status=AnalysisStatus.PENDING,
    )
    db.add(analysis)
    await db.flush()  # get ID

    # Enqueue job
    job_id = await job_queue.enqueue(
        job_type="analysis",
        payload={
            "file_id": file_id,
            "file_path": file.path,
            "file_format": file.format,
            "analysis_id": analysis.id,
        },
        priority=3,
    )

    await db.commit()
    return {
        "analysis_id": analysis.id,
        "job_id": job_id,
        "job_status": "queued",
        "message": "Analysis started",
    }


@router.get("/analysis/{analysis_id}")
async def get_analysis(
    analysis_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get full analysis result."""
    analysis = await _get_analysis_or_404(analysis_id, db)

    # Load related counts
    tables_r = await db.execute(select(ExtractedTable).where(ExtractedTable.analysis_id == analysis_id))
    entities_r = await db.execute(select(ExtractedEntity).where(ExtractedEntity.analysis_id == analysis_id))

    tables = tables_r.scalars().all()
    entities = entities_r.scalars().all()

    return {
        "id": analysis.id,
        "file_id": analysis.file_id,
        "status": analysis.status.value,
        "doc_type": analysis.doc_type,
        "doc_type_confidence": analysis.doc_type_confidence,
        "language": analysis.language,
        "page_count": analysis.page_count,
        "has_tables": analysis.has_tables,
        "has_images": analysis.has_images,
        "processing_ms": analysis.processing_ms,
        "pipeline_used": analysis.pipeline_used,
        "error_message": analysis.error_message,
        "table_count": len(tables),
        "entity_count": len(entities),
        "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
        "updated_at": analysis.updated_at.isoformat() if analysis.updated_at else None,
    }


@router.get("/analysis/{analysis_id}/layout")
async def get_layout(
    analysis_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get layout elements with bounding boxes."""
    await _get_analysis_or_404(analysis_id, db)
    result = await db.execute(
        select(LayoutElement)
        .where(LayoutElement.analysis_id == analysis_id)
        .order_by(LayoutElement.page_number, LayoutElement.y1)
    )
    elements = result.scalars().all()
    return {
        "analysis_id": analysis_id,
        "count": len(elements),
        "elements": [
            {
                "id": e.id,
                "type": e.element_type,
                "page": e.page_number,
                "bbox": {"x1": e.x1, "y1": e.y1, "x2": e.x2, "y2": e.y2},
                "confidence": e.confidence,
                "content": e.content,
            }
            for e in elements
        ],
    }


@router.get("/analysis/{analysis_id}/tables")
async def get_tables(
    analysis_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get extracted tables."""
    await _get_analysis_or_404(analysis_id, db)
    result = await db.execute(
        select(ExtractedTable).where(ExtractedTable.analysis_id == analysis_id)
    )
    tables = result.scalars().all()
    return {
        "analysis_id": analysis_id,
        "count": len(tables),
        "tables": [
            {
                "id": t.id,
                "page": t.page_number,
                "rows": t.row_count,
                "cols": t.col_count,
                "headers": t.headers,
                "has_merged_cells": t.has_merged_cells,
                "confidence": t.confidence,
                "data": t.table_data[:5] if t.table_data else [],  # preview: first 5 rows
            }
            for t in tables
        ],
    }


@router.get("/analysis/{analysis_id}/entities")
async def get_entities(
    analysis_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get extracted entities."""
    await _get_analysis_or_404(analysis_id, db)
    result = await db.execute(
        select(ExtractedEntity)
        .where(ExtractedEntity.analysis_id == analysis_id)
        .order_by(ExtractedEntity.entity_type)
    )
    entities = result.scalars().all()
    return {
        "analysis_id": analysis_id,
        "count": len(entities),
        "entities": [
            {
                "id": e.id,
                "type": e.entity_type,
                "value": e.value,
                "normalized_value": e.normalized_value,
                "confidence": e.confidence,
                "page": e.page_number,
                "verified": e.verified,
                "corrected_value": e.corrected_value,
            }
            for e in entities
        ],
    }


@router.post("/analysis/{analysis_id}/entities/{entity_id}/correct")
async def correct_entity(
    analysis_id: int,
    entity_id: int,
    body: EntityCorrection,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """User corrects an extracted entity — saved as feedback."""
    entity = await db.get(ExtractedEntity, entity_id)
    if not entity or entity.analysis_id != analysis_id:
        raise HTTPException(404, "Entity not found")

    # Save feedback
    fb = UserFeedback(
        user_id=current_user.id,
        analysis_id=analysis_id,
        entity_id=entity_id,
        feedback_type="entity_correction",
        original_value=entity.value,
        corrected_value=body.corrected_value,
        field_name=entity.entity_type,
    )
    db.add(fb)

    # Update entity
    entity.corrected_value = body.corrected_value
    entity.verified = True
    await db.commit()
    return {"message": "Correction saved", "entity_id": entity_id}


@router.get("/suggestions/{file_id}")
async def get_suggestions(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get AI suggestions for a file."""
    await _get_file_or_404(file_id, current_user.id, db)
    result = await db.execute(
        select(AISuggestion)
        .where(AISuggestion.file_id == file_id)
        .order_by(AISuggestion.priority)
    )
    suggestions = result.scalars().all()
    return {
        "file_id": file_id,
        "suggestions": [
            {
                "id": s.id,
                "type": s.suggestion_type,
                "title": s.title,
                "description": s.description,
                "action_params": s.action_params,
                "priority": s.priority,
                "accepted": s.accepted,
            }
            for s in suggestions
        ],
    }


@router.post("/suggestions/{suggestion_id}/accept")
async def accept_suggestion(
    suggestion_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a suggestion as accepted."""
    s = await db.get(AISuggestion, suggestion_id)
    if not s:
        raise HTTPException(404, "Suggestion not found")
    s.accepted = True
    await db.commit()
    return {"message": "Suggestion accepted", "action_params": s.action_params}


@router.post("/feedback")
async def submit_feedback(
    file_id: int,
    body: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit user feedback."""
    fb = UserFeedback(
        user_id=current_user.id,
        file_id=file_id,
        feedback_type=body.feedback_type,
        original_value=body.original_value,
        corrected_value=body.corrected_value,
        field_name=body.field_name,
        rating=body.rating,
        comment=body.comment,
    )
    db.add(fb)
    await db.commit()
    return {"message": "Feedback saved", "id": fb.id}


@router.get("/jobs/{job_id}/status")
async def job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    """Poll job status."""
    status = job_queue.get_status(job_id)
    result = job_queue.get_result(job_id)
    return {
        "job_id": job_id,
        "status": status,
        "result": result.data if result and result.success else None,
        "error": result.error if result and not result.success else None,
    }
