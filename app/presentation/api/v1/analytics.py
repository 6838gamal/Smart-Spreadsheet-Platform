"""Analytics API — overview stats, file trends, operation usage."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.infrastructure.database.models import User, File, OperationLog
from app.infrastructure.database.models_intelligence import (
    DocumentAnalysis, AnalysisStatus, ExtractedTable, ExtractedEntity,
    UserFeedback, AISuggestion,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _utc_days_ago(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


@router.get("/overview")
async def analytics_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """High-level platform statistics."""
    # Total files
    total_files = (await db.execute(
        select(func.count(File.id)).where(File.owner_id == current_user.id)
    )).scalar_one() or 0

    # Files this week
    week_ago = _utc_days_ago(7)
    files_this_week = (await db.execute(
        select(func.count(File.id)).where(
            File.owner_id == current_user.id,
            File.created_at >= week_ago,
        )
    )).scalar_one() or 0

    # Completed analyses
    completed_analyses = (await db.execute(
        select(func.count(DocumentAnalysis.id))
        .join(File, DocumentAnalysis.file_id == File.id)
        .where(
            File.owner_id == current_user.id,
            DocumentAnalysis.status == AnalysisStatus.COMPLETED,
        )
    )).scalar_one() or 0

    # Average processing time (ms → seconds)
    avg_ms = (await db.execute(
        select(func.avg(DocumentAnalysis.processing_ms))
        .join(File, DocumentAnalysis.file_id == File.id)
        .where(
            File.owner_id == current_user.id,
            DocumentAnalysis.status == AnalysisStatus.COMPLETED,
            DocumentAnalysis.processing_ms.isnot(None),
        )
    )).scalar_one()
    avg_processing_sec = round((avg_ms or 0) / 1000, 1)

    # Total entities extracted
    total_entities = (await db.execute(
        select(func.count(ExtractedEntity.id))
        .join(DocumentAnalysis, ExtractedEntity.analysis_id == DocumentAnalysis.id)
        .join(File, DocumentAnalysis.file_id == File.id)
        .where(File.owner_id == current_user.id)
    )).scalar_one() or 0

    # Total tables extracted
    total_tables = (await db.execute(
        select(func.count(ExtractedTable.id))
        .join(DocumentAnalysis, ExtractedTable.analysis_id == DocumentAnalysis.id)
        .join(File, DocumentAnalysis.file_id == File.id)
        .where(File.owner_id == current_user.id)
    )).scalar_one() or 0

    # User feedback count
    total_feedback = (await db.execute(
        select(func.count(UserFeedback.id)).where(UserFeedback.user_id == current_user.id)
    )).scalar_one() or 0

    # Suggestion acceptance rate
    total_sugg = (await db.execute(
        select(func.count(AISuggestion.id))
        .join(File, AISuggestion.file_id == File.id)
        .where(File.owner_id == current_user.id, AISuggestion.accepted.isnot(None))
    )).scalar_one() or 0
    accepted_sugg = (await db.execute(
        select(func.count(AISuggestion.id))
        .join(File, AISuggestion.file_id == File.id)
        .where(File.owner_id == current_user.id, AISuggestion.accepted == True)
    )).scalar_one() or 0
    acceptance_rate = round(accepted_sugg / total_sugg * 100, 1) if total_sugg else 0

    return {
        "total_files": total_files,
        "files_this_week": files_this_week,
        "completed_analyses": completed_analyses,
        "avg_processing_sec": avg_processing_sec,
        "total_entities": total_entities,
        "total_tables": total_tables,
        "total_feedback": total_feedback,
        "suggestion_acceptance_rate": acceptance_rate,
    }


@router.get("/files")
async def analytics_files(
    period: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Daily file upload counts for the last `period` days."""
    since = _utc_days_ago(period)
    rows = (await db.execute(
        select(
            func.date(File.created_at).label("day"),
            func.count(File.id).label("count"),
        )
        .where(File.owner_id == current_user.id, File.created_at >= since)
        .group_by(func.date(File.created_at))
        .order_by(func.date(File.created_at))
    )).all()
    return {"period_days": period, "data": [{"day": str(r.day), "count": r.count} for r in rows]}


@router.get("/doc-types")
async def analytics_doc_types(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Distribution of detected document types."""
    rows = (await db.execute(
        select(
            DocumentAnalysis.doc_type,
            func.count(DocumentAnalysis.id).label("count"),
        )
        .join(File, DocumentAnalysis.file_id == File.id)
        .where(
            File.owner_id == current_user.id,
            DocumentAnalysis.status == AnalysisStatus.COMPLETED,
            DocumentAnalysis.doc_type.isnot(None),
        )
        .group_by(DocumentAnalysis.doc_type)
        .order_by(func.count(DocumentAnalysis.id).desc())
    )).all()
    return {"data": [{"doc_type": r.doc_type, "count": r.count} for r in rows]}


@router.get("/entities")
async def analytics_entities(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Top extracted entity types."""
    rows = (await db.execute(
        select(
            ExtractedEntity.entity_type,
            func.count(ExtractedEntity.id).label("count"),
        )
        .join(DocumentAnalysis, ExtractedEntity.analysis_id == DocumentAnalysis.id)
        .join(File, DocumentAnalysis.file_id == File.id)
        .where(File.owner_id == current_user.id)
        .group_by(ExtractedEntity.entity_type)
        .order_by(func.count(ExtractedEntity.id).desc())
        .limit(15)
    )).all()
    return {"data": [{"entity_type": r.entity_type, "count": r.count} for r in rows]}
