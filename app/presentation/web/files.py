"""File manager web routes."""

import json
import logging
from fastapi import APIRouter, Depends, Request, UploadFile, File, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.templates import templates
from app.infrastructure.database.models import User
from app.application.files.service import FileService

logger = logging.getLogger(__name__)
router = APIRouter()


async def _auto_analyze(file_id: int, file_path: str, file_format: str, db: AsyncSession) -> int | None:
    """Create a DocumentAnalysis record and enqueue the analysis job.
    Returns the analysis_id, or None if analysis already queued."""
    from app.infrastructure.database.models_intelligence import DocumentAnalysis, AnalysisStatus
    from app.jobs.job_queue import job_queue

    # Don't create duplicate pending/running analyses
    existing = await db.execute(
        select(DocumentAnalysis).where(
            DocumentAnalysis.file_id == file_id,
            DocumentAnalysis.status.in_([AnalysisStatus.PENDING, AnalysisStatus.RUNNING]),
        )
    )
    if existing.scalar_one_or_none():
        return None

    analysis = DocumentAnalysis(file_id=file_id, status=AnalysisStatus.PENDING)
    db.add(analysis)
    await db.flush()

    await job_queue.enqueue(
        job_type="analysis",
        payload={
            "file_id": file_id,
            "file_path": file_path,
            "file_format": file_format,
            "analysis_id": analysis.id,
        },
        priority=3,
    )
    await db.commit()
    logger.info(f"Auto-triggered analysis for file_id={file_id} (analysis_id={analysis.id})")
    return analysis.id


@router.get("/files", response_class=HTMLResponse)
async def files_page(
    request: Request,
    search: str = "",
    fmt: str = "",
    page: int = 1,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = FileService(db)
    limit = 20
    offset = (page - 1) * limit
    files, total = await svc.list_files(
        current_user.id,
        search=search or None,
        format_filter=fmt or None,
        limit=limit,
        offset=offset,
    )
    total_pages = max(1, (total + limit - 1) // limit)
    return templates.TemplateResponse(
        request,
        "files/index.html",
        {
            "user": current_user,
            "files": files,
            "total": total,
            "page": page,
            "total_pages": total_pages,
            "search": search,
            "fmt": fmt,
            "current_page": "files",
            "lang": current_user.default_lang,
        },
    )


@router.post("/files/upload")
async def upload_files(
    request: Request,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = FileService(db)
    uploaded = []   # list of File ORM objects
    errors = []
    for file in files:
        try:
            f = await svc.upload(file, current_user.id)
            # Auto-trigger analysis immediately after upload
            await _auto_analyze(f.id, f.path, f.format, db)
            uploaded.append(f)
        except Exception as e:
            errors.append(f"{file.filename}: {e}")

    if request.headers.get("HX-Request"):
        if not uploaded:
            msg = " | ".join(errors) or "فشل الرفع"
            return HTMLResponse(f'<div class="text-red-400 text-sm text-center">{msg}</div>')

        if len(uploaded) == 1 and not errors:
            # Single file: redirect straight to the analysis page
            redirect_url = f"/intelligence/analyze/{uploaded[0].id}"
            return HTMLResponse(
                f'<div class="text-emerald-400 text-sm text-center">'
                f'✓ تم رفع الملف — جارٍ التوجيه للتحليل…'
                f'</div>'
                f'<script>setTimeout(()=>window.location.href="{redirect_url}",600)</script>'
            )

        # Multiple files: stay on page and show count
        msg = f"✓ تم رفع {len(uploaded)} ملف وبدأ التحليل تلقائياً"
        if errors:
            msg += f" ({len(errors)} أخطاء)"
        return HTMLResponse(
            f'<div class="text-emerald-400 text-sm text-center">{msg}</div>'
            f'<script>setTimeout(()=>location.reload(),1500)</script>'
        )

    # Non-HTMX fallback
    if len(uploaded) == 1:
        return RedirectResponse(url=f"/intelligence/analyze/{uploaded[0].id}", status_code=302)
    return RedirectResponse(url="/files", status_code=302)


@router.get("/files/{file_id}", response_class=HTMLResponse)
async def file_detail(
    request: Request,
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = FileService(db)
    f = await svc.get_file(file_id, current_user.id)
    preview = await svc.get_preview(file_id, current_user.id, rows=200)

    # Load latest analysis record (if any)
    from app.infrastructure.database.models_intelligence import DocumentAnalysis
    analysis_res = await db.execute(
        select(DocumentAnalysis)
        .where(DocumentAnalysis.file_id == file_id)
        .order_by(DocumentAnalysis.created_at.desc())
        .limit(1)
    )
    analysis = analysis_res.scalar_one_or_none()

    return templates.TemplateResponse(
        request,
        "files/detail.html",
        {
            "user": current_user,
            "file": f,
            "preview": preview,
            "analysis": analysis,
            "current_page": "files",
            "lang": current_user.default_lang,
        },
    )


@router.get("/files/{file_id}/download")
async def download_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = FileService(db)
    f = await svc.get_file(file_id, current_user.id)
    if not Path(f.path).exists():
        return RedirectResponse(url="/files", status_code=302)
    return FileResponse(f.path, filename=f.original_name)


@router.post("/files/{file_id}/delete")
async def delete_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = FileService(db)
    await svc.delete_file(file_id, current_user.id)
    return RedirectResponse(url="/files", status_code=302)


@router.post("/files/{file_id}/favorite")
async def toggle_favorite(
    request: Request,
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = FileService(db)
    f = await svc.toggle_favorite(file_id, current_user.id)
    if request.headers.get("HX-Request"):
        icon = "★" if f.is_favorite else "☆"
        cls = "text-yellow-400" if f.is_favorite else "text-slate-200 dark:text-slate-600"
        return HTMLResponse(f'<span class="{cls}">{icon}</span>')
    return RedirectResponse(url=f"/files/{file_id}", status_code=302)
