"""Web routes for Document Intelligence UI pages."""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.infrastructure.database.models import User, File
from app.infrastructure.database.models_intelligence import (
    DocumentAnalysis, ExtractedTable, ExtractedEntity, AISuggestion,
)

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/intelligence", response_class=HTMLResponse)
async def intelligence_home(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Document Intelligence landing page."""
    # Recent files for the user
    result = await db.execute(
        select(File)
        .where(File.owner_id == current_user.id)
        .order_by(File.created_at.desc())
        .limit(20)
    )
    files = result.scalars().all()

    # Recent analyses
    result2 = await db.execute(
        select(DocumentAnalysis)
        .join(File, DocumentAnalysis.file_id == File.id)
        .where(File.owner_id == current_user.id)
        .order_by(DocumentAnalysis.created_at.desc())
        .limit(5)
    )
    recent_analyses = result2.scalars().all()

    return templates.TemplateResponse("intelligence/index.html", {
        "request": request,
        "user": current_user,
        "files": files,
        "recent_analyses": recent_analyses,
        "page_title": "ذكاء المستندات",
    })


@router.get("/intelligence/analyze/{file_id}", response_class=HTMLResponse)
async def analyze_file(
    file_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Analysis page for a specific file."""
    result = await db.execute(
        select(File).where(File.id == file_id, File.owner_id == current_user.id)
    )
    file = result.scalar_one_or_none()
    if not file:
        raise HTTPException(404, "File not found")

    # Get latest analysis if any
    result2 = await db.execute(
        select(DocumentAnalysis)
        .where(DocumentAnalysis.file_id == file_id)
        .order_by(DocumentAnalysis.created_at.desc())
        .limit(1)
    )
    analysis = result2.scalar_one_or_none()

    tables, entities, suggestions = [], [], []
    if analysis:
        t_r = await db.execute(select(ExtractedTable).where(ExtractedTable.analysis_id == analysis.id))
        e_r = await db.execute(select(ExtractedEntity).where(ExtractedEntity.analysis_id == analysis.id))
        s_r = await db.execute(
            select(AISuggestion)
            .where(AISuggestion.analysis_id == analysis.id)
            .order_by(AISuggestion.priority)
        )
        tables = t_r.scalars().all()
        entities = e_r.scalars().all()
        suggestions = s_r.scalars().all()

    # Group entities by type
    entity_groups: dict[str, list] = {}
    for e in entities:
        entity_groups.setdefault(e.entity_type, []).append(e)

    return templates.TemplateResponse("intelligence/analyze.html", {
        "request": request,
        "user": current_user,
        "file": file,
        "analysis": analysis,
        "tables": tables,
        "entity_groups": entity_groups,
        "suggestions": suggestions,
        "page_title": f"تحليل: {file.original_name}",
    })


@router.get("/intelligence/analysis/{analysis_id}/result", response_class=HTMLResponse)
async def analysis_result(
    analysis_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full analysis result page."""
    analysis = await db.get(DocumentAnalysis, analysis_id)
    if not analysis:
        raise HTTPException(404)

    file = await db.get(File, analysis.file_id)
    if not file or file.owner_id != current_user.id:
        raise HTTPException(403)

    t_r = await db.execute(select(ExtractedTable).where(ExtractedTable.analysis_id == analysis_id))
    e_r = await db.execute(select(ExtractedEntity).where(ExtractedEntity.analysis_id == analysis_id).order_by(ExtractedEntity.entity_type))
    s_r = await db.execute(select(AISuggestion).where(AISuggestion.analysis_id == analysis_id).order_by(AISuggestion.priority))

    tables = t_r.scalars().all()
    entities = e_r.scalars().all()
    suggestions = s_r.scalars().all()

    entity_groups: dict[str, list] = {}
    for e in entities:
        entity_groups.setdefault(e.entity_type, []).append(e)

    return templates.TemplateResponse("intelligence/result.html", {
        "request": request,
        "user": current_user,
        "file": file,
        "analysis": analysis,
        "tables": tables,
        "entity_groups": entity_groups,
        "suggestions": suggestions,
        "page_title": f"نتائج التحليل — {file.original_name}",
    })
