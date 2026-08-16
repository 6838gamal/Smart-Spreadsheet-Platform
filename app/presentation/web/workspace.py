"""
Unified workspace web router.
Serves the single-page workspace shell and HTMX panel partials.
"""
from __future__ import annotations

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.templates import templates
from app.infrastructure.database.models import User, File
from app.infrastructure.database.models_intelligence import DocumentAnalysis
from app.infrastructure.repositories.file_repository import FileRepository
from app.application.dashboard.service import DashboardService
from app.application.converter.service import EXPORT_FORMATS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workspace", tags=["workspace"])


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

async def _get_files(db: AsyncSession, user_id: int, limit: int = 50) -> List[File]:
    """
    Get files for a user.
    
    Returns a list of File objects, handling the tuple return from the repository.
    """
    repo = FileRepository(db)
    result = await repo.get_by_owner(user_id, limit=limit)
    
    # Handle the case where get_by_owner returns a tuple (files, total)
    if isinstance(result, tuple) and len(result) == 2:
        files = result[0]  # Extract the list of files
    else:
        files = result  # Already a list
    
    # Ensure we return a list
    if files is None:
        return []
    if not isinstance(files, list):
        return list(files) if files else []
    
    return files


async def _get_recent_files(db: AsyncSession, user_id: int, limit: int = 6) -> List[File]:
    """Get recent files for a user."""
    repo = FileRepository(db)
    files = await repo.get_recent(user_id, limit=limit)
    
    # Ensure we return a list
    if files is None:
        return []
    if not isinstance(files, list):
        return list(files) if files else []
    
    return files


async def _get_favorite_files(db: AsyncSession, user_id: int, limit: int = 4) -> List[File]:
    """Get favorite files for a user."""
    repo = FileRepository(db)
    files = await repo.get_favorites(user_id, limit=limit)
    
    # Ensure we return a list
    if files is None:
        return []
    if not isinstance(files, list):
        return list(files) if files else []
    
    return files


async def _get_latest_analysis(db: AsyncSession, file_id: int) -> Optional[DocumentAnalysis]:
    """Get the latest analysis for a file."""
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
    """Main workspace shell page."""
    files = await _get_files(db, current_user.id)
    recent_files = await _get_recent_files(db, current_user.id, limit=6)
    favorite_files = await _get_favorite_files(db, current_user.id, limit=4)
    
    svc = DashboardService(db)
    stats = await svc.get_stats(current_user.id)

    return templates.TemplateResponse(
        request,
        "workspace/index.html",
        {
            "user": current_user,
            "lang": current_user.default_lang,
            "files": files,
            "recent_files": recent_files,
            "favorite_files": favorite_files,
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
    """File list panel - refreshed after upload."""
    files = await _get_files(db, current_user.id)
    
    return templates.TemplateResponse(
        request,
        "workspace/_files_panel.html",
        {
            "user": current_user,
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
    """Home panel with statistics."""
    svc = DashboardService(db)
    stats = await svc.get_stats(current_user.id)
    
    recent_files = await _get_recent_files(db, current_user.id, limit=6)
    favorite_files = await _get_favorite_files(db, current_user.id, limit=4)
    
    return templates.TemplateResponse(
        request,
        "workspace/_panel_home.html",
        {
            "user": current_user,
            "lang": current_user.default_lang,
            "stats": stats,
            "recent_files": recent_files,
            "favorite_files": favorite_files,
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
    """View panel - file detail and preview."""
    from app.application.files.service import FileService

    repo = FileRepository(db)
    file = await repo.get_by_id(file_id)
    if file and file.owner_id != current_user.id:
        file = None

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
        request,
        "workspace/_panel_view.html",
        {
            "user": current_user,
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
    """Analyze panel - AI intelligence results."""
    from sqlalchemy import select
    
    # محاولة استيراد النماذج بشكل آمن
    ExtractedTable = None
    ExtractedEntity = None
    AISuggestion = None
    
    try:
        # المحاولة الأولى: الاستيراد من الموقع الرئيسي
        from app.infrastructure.database.models import ExtractedTable, ExtractedEntity, AISuggestion
        logger.debug("✅ ExtractedTable models imported from models.py")
    except ImportError:
        try:
            # المحاولة الثانية: الاستيراد من ملف intelligence
            from app.infrastructure.database.models_intelligence import ExtractedTable, ExtractedEntity, AISuggestion
            logger.debug("✅ ExtractedTable models imported from models_intelligence.py")
        except ImportError:
            # إذا لم توجد النماذج، استخدم تعريفات مؤقتة
            logger.warning("⚠️ ExtractedTable models not found, using fallback definitions")
            
            # تعريف فئات مؤقتة للتعامل مع الحالات التي لا توجد فيها بيانات
            class ExtractedTable:
                pass
            class ExtractedEntity:
                pass
            class AISuggestion:
                pass

    repo = FileRepository(db)
    file = await repo.get_by_id(file_id)
    if file and file.owner_id != current_user.id:
        file = None

    analysis = None
    tables = []
    entity_groups: dict = {}
    suggestions = []

    if file:
        analysis = await _get_latest_analysis(db, file_id)
        if analysis and analysis.status.value == "completed":
            # فقط حاول استرجاع البيانات إذا كانت النماذج موجودة
            try:
                # التحقق من أن النماذج ليست الفئات المؤقتة
                if ExtractedTable.__name__ != "ExtractedTable" or hasattr(ExtractedTable, '__table__'):
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
                else:
                    logger.info("ℹ️ Using fallback models, skipping data fetch")
            except Exception as e:
                logger.warning(f"Could not fetch analysis data: {e}")
                # الاستمرار بدون بيانات

    return templates.TemplateResponse(
        request,
        "workspace/_panel_analyze.html",
        {
            "user": current_user,
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
    """Convert panel."""
    files = await _get_files(db, current_user.id)
    
    return templates.TemplateResponse(
        request,
        "workspace/_panel_convert.html",
        {
            "user": current_user,
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
    """Clean panel."""
    files = await _get_files(db, current_user.id)
    
    return templates.TemplateResponse(
        request,
        "workspace/_panel_clean.html",
        {
            "user": current_user,
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
    """Merge panel."""
    files = await _get_files(db, current_user.id)
    
    return templates.TemplateResponse(
        request,
        "workspace/_panel_merge.html",
        {
            "user": current_user,
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
    """Analytics panel."""
    return templates.TemplateResponse(
        request,
        "workspace/_panel_analytics.html",
        {
            "user": current_user,
            "lang": current_user.default_lang,
        },
    )
