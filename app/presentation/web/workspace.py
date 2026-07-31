"""
Unified workspace web router.
Serves the single-page workspace shell and HTMX panel partials.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.templates import templates
from app.infrastructure.database.models import User
from app.infrastructure.database.models_intelligence import DocumentAnalysis
from app.infrastructure.repositories.file_repository import FileRepository
from app.application.dashboard.service import DashboardService
from app.application.converter.service import EXPORT_FORMATS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workspace", tags=["workspace"])


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

async def _get_files(db: AsyncSession, user_id: int):
    repo = FileRepository(db)
    return await repo.get_user_files(user_id)


async def _get_latest_analysis(db: AsyncSession, file_id: int) -> Optional[DocumentAnalysis]:
    result = await db.execute(
        select(DocumentAnalysis)
        .where(DocumentAnalysis.file_id == file_id)
        .order_by(DocumentAnalysis.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


# ──────────────────────────────────────────────────────────────────────────────
# Main shell
# ──────────────────────────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def workspace_shell(
    request: Request,
    open_panel: str = Query(default="home"),
    file_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    files = await _get_files(db, current_user.id)
    svc = DashboardService(db)
    stats = await svc.get_stats(current_user.id)

    return templates.TemplateResponse(
        "workspace/index.html",
        {
            "request": request,
            "current_user": current_user,
            "lang": current_user.default_lang,
            "files": files,
            "stats": stats,
            "open_panel": open_panel,
            "open_file_id": file_id,
            "active_page": "workspace",
        },
    )


# ──────────────────────────────────────────────────────────────────────────────
# Panel: file list (refreshed after upload)
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/panel/files", response_class=HTMLResponse)
async def panel_files(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    files = await _get_files(db, current_user.id)
    return templates.TemplateResponse(
        "workspace/_files_panel.html",
        {
            "request": request,
            "current_user": current_user,
            "lang": current_user.default_lang,
            "files": files,
        },
    )


# ──────────────────────────────────────────────────────────────────────────────
# Panel: home / stats
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/panel/home", response_class=HTMLResponse)
async def panel_home(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = DashboardService(db)
    stats = await svc.get_stats(current_user.id)
    return templates.TemplateResponse(
        "workspace/_panel_home.html",
        {
            "request": request,
            "current_user": current_user,
            "lang": current_user.default_lang,
            "stats": stats,
        },
    )


# ──────────────────────────────────────────────────────────────────────────────
# Panel: view (file detail + preview)
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/panel/view/{file_id}", response_class=HTMLResponse)
async def panel_view(
    file_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.application.files.service import FileService

    repo = FileRepository(db)
    file = await repo.get_by_id(file_id, current_user.id)

    preview = None
    analysis = None
    if file:
        try:
            svc = FileService(db)
            preview = await svc.get_preview(file_id, current_user.id, rows=200)
        except Exception as exc:
            logger.warning("Preview failed for file %s: %s", file_id, exc)
            preview = {"error": "تعذّرت المعاينة"}
        analysis = await _get_latest_analysis(db, file_id)

    return templates.TemplateResponse(
        "workspace/_panel_view.html",
        {
            "request": request,
            "current_user": current_user,
            "lang": current_user.default_lang,
            "file": file,
            "preview": preview,
            "analysis": analysis,
        },
    )


# ──────────────────────────────────────────────────────────────────────────────
# Panel: analyze (AI intelligence results)
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/panel/analyze/{file_id}", response_class=HTMLResponse)
async def panel_analyze(
    file_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import select
    from app.infrastructure.database.models import ExtractedTable, ExtractedEntity, AISuggestion

    repo = FileRepository(db)
    file = await repo.get_by_id(file_id, current_user.id)

    analysis = None
    tables = []
    entity_groups: dict = {}
    suggestions = []

    if file:
        analysis = await _get_latest_analysis(db, file_id)
        if analysis and analysis.status.value == "completed":
            # Tables
            tbl_result = await db.execute(
                select(ExtractedTable)
                .where(ExtractedTable.analysis_id == analysis.id)
                .order_by(ExtractedTable.table_index)
            )
            tables = tbl_result.scalars().all()

            # Entities
            ent_result = await db.execute(
                select(ExtractedEntity)
                .where(ExtractedEntity.analysis_id == analysis.id)
            )
            entities = ent_result.scalars().all()
            for e in entities:
                entity_groups.setdefault(e.entity_type, []).append(e)

            # Suggestions
            sug_result = await db.execute(
                select(AISuggestion)
                .where(AISuggestion.analysis_id == analysis.id)
                .order_by(AISuggestion.priority)
            )
            suggestions = sug_result.scalars().all()

    return templates.TemplateResponse(
        "workspace/_panel_analyze.html",
        {
            "request": request,
            "current_user": current_user,
            "lang": current_user.default_lang,
            "file": file,
            "analysis": analysis,
            "tables": tables,
            "entity_groups": entity_groups,
            "suggestions": suggestions,
        },
    )


# ──────────────────────────────────────────────────────────────────────────────
# Panel: convert
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/panel/convert", response_class=HTMLResponse)
async def panel_convert(
    request: Request,
    file_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    files = await _get_files(db, current_user.id)
    return templates.TemplateResponse(
        "workspace/_panel_convert.html",
        {
            "request": request,
            "current_user": current_user,
            "lang": current_user.default_lang,
            "files": files,
            "selected_file_id": file_id,
            "export_formats": EXPORT_FORMATS,
        },
    )


# ──────────────────────────────────────────────────────────────────────────────
# Panel: clean
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/panel/clean", response_class=HTMLResponse)
async def panel_clean(
    request: Request,
    file_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    files = await _get_files(db, current_user.id)
    return templates.TemplateResponse(
        "workspace/_panel_clean.html",
        {
            "request": request,
            "current_user": current_user,
            "lang": current_user.default_lang,
            "files": files,
            "selected_file_id": file_id,
        },
    )


# ──────────────────────────────────────────────────────────────────────────────
# Panel: merge
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/panel/merge", response_class=HTMLResponse)
async def panel_merge(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    files = await _get_files(db, current_user.id)
    return templates.TemplateResponse(
        "workspace/_panel_merge.html",
        {
            "request": request,
            "current_user": current_user,
            "lang": current_user.default_lang,
            "files": files,
        },
    )


# ──────────────────────────────────────────────────────────────────────────────
# Panel: analytics
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/panel/analytics", response_class=HTMLResponse)
async def panel_analytics(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return templates.TemplateResponse(
        "workspace/_panel_analytics.html",
        {
            "request": request,
            "current_user": current_user,
            "lang": current_user.default_lang,
        },
    )
