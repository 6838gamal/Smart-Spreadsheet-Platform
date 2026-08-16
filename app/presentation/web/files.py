"""File manager web routes."""

import json
import logging
from fastapi import APIRouter, Depends, Request, UploadFile, File, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
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
    """Create a DocumentAnalysis record and enqueue the analysis job."""
    try:
        from app.infrastructure.database.models_intelligence import DocumentAnalysis, AnalysisStatus
        from app.jobs.job_queue import job_queue

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
    except Exception as e:
        logger.error(f"Auto-analysis failed for file_id={file_id}: {e}")
        return None


@router.get("/files", response_class=HTMLResponse)
async def files_page(
    request: Request,
    search: str = "",
    fmt: str = "",
    only_local: bool = False,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = 1,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Display files page with filtering, sorting, and pagination.
    """
    svc = FileService(db)
    limit = 20
    offset = (page - 1) * limit
    
    files, total = await svc.list_files(
        user_id=current_user.id,
        search=search or None,
        format_filter=fmt or None,
        only_local=only_local,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    total_pages = max(1, (total + limit - 1) // limit)
    
    # Add safe attributes for template
    for f in files:
        f.storage_key = getattr(f, 'storage_key', None)
        f.is_locally_stored = getattr(f, 'is_locally_stored', False)
        f.is_cached_locally = getattr(f, 'is_cached_locally', False)
    
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
            "only_local": only_local,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "current_page": "files",
            "lang": current_user.default_lang,
        },
    )


@router.post("/files/upload")
async def upload_files(
    request: Request,
    files: list[UploadFile] = File(...),
    store_locally: bool = Form(True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload files to the server.
    """
    svc = FileService(db)
    uploaded = []
    errors = []
    
    for file in files:
        try:
            f = await svc.upload(file, current_user.id, store_locally=store_locally)
            await _auto_analyze(f.id, f.path, f.format, db)
            uploaded.append(f)
        except Exception as e:
            logger.error(f"Upload error for {file.filename}: {e}")
            errors.append(f"{file.filename}: {e}")

    # HTMX response
    if request.headers.get("HX-Request"):
        if not uploaded:
            msg = " | ".join(errors) or "فشل الرفع"
            return HTMLResponse(f'<div class="text-red-400 text-sm text-center">{msg}</div>')

        if len(uploaded) == 1 and not errors:
            redirect_url = f"/intelligence/analyze/{uploaded[0].id}"
            return HTMLResponse(
                f'<div class="text-emerald-400 text-sm text-center">'
                f'✓ تم رفع الملف — جارٍ التوجيه للتحليل…'
                f'</div>'
                f'<script>setTimeout(()=>window.location.href="{redirect_url}",600)</script>'
            )

        msg = f"✓ تم رفع {len(uploaded)} ملف وبدأ التحليل تلقائياً"
        if errors:
            msg += f" ({len(errors)} أخطاء)"
        
        storage_info = " (مخزن محلياً)" if store_locally else ""
        
        return HTMLResponse(
            f'<div class="text-emerald-400 text-sm text-center">{msg}{storage_info}</div>'
            f'<script>setTimeout(()=>location.reload(),1500)</script>'
        )

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
    """
    Display file detail page.
    """
    svc = FileService(db)
    f = await svc.get_file(file_id, current_user.id)
    
    # Safe attribute access
    f.storage_key = getattr(f, 'storage_key', None)
    f.is_locally_stored = getattr(f, 'is_locally_stored', False)
    
    preview = None
    try:
        preview = await svc.get_preview(file_id, current_user.id, rows=200)
    except Exception as e:
        logger.warning(f"Preview not available for file {file_id}: {e}")
        preview = {"error": str(e), "available": False}

    # Load latest analysis
    try:
        from app.infrastructure.database.models_intelligence import DocumentAnalysis
        analysis_res = await db.execute(
            select(DocumentAnalysis)
            .where(DocumentAnalysis.file_id == file_id)
            .order_by(DocumentAnalysis.created_at.desc())
            .limit(1)
        )
        analysis = analysis_res.scalar_one_or_none()
    except Exception:
        analysis = None

    file_exists_on_server = Path(f.path).exists() if f.path else False

    return templates.TemplateResponse(
        request,
        "files/detail.html",
        {
            "user": current_user,
            "file": f,
            "preview": preview,
            "analysis": analysis,
            "file_exists_on_server": file_exists_on_server,
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
    """
    Download file from server.
    """
    svc = FileService(db)
    f = await svc.get_file(file_id, current_user.id)
    
    if not f.path or not Path(f.path).exists():
        content = await svc.get_file_content(file_id, current_user.id)
        if content:
            return Response(
                content=content,
                media_type=f.mime_type or "application/octet-stream",
                headers={
                    "Content-Disposition": f'attachment; filename="{f.original_name}"',
                    "Content-Length": str(len(content))
                }
            )
        return RedirectResponse(url="/files", status_code=302)
    
    return FileResponse(f.path, filename=f.original_name)


@router.post("/files/{file_id}/delete")
async def delete_file(
    file_id: int,
    delete_local: bool = Form(True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete file from server and optionally local storage.
    """
    svc = FileService(db)
    await svc.delete_file(file_id, current_user.id, delete_local=delete_local)
    return RedirectResponse(url="/files", status_code=302)


@router.post("/files/{file_id}/favorite")
async def toggle_favorite(
    request: Request,
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Toggle favorite status of a file.
    """
    svc = FileService(db)
    f = await svc.toggle_favorite(file_id, current_user.id)
    
    if request.headers.get("HX-Request"):
        icon = "★" if f.is_favorite else "☆"
        cls = "text-yellow-400" if f.is_favorite else "text-slate-200 dark:text-slate-600 hover:text-yellow-300"
        return HTMLResponse(f'<span class="{cls}">{icon}</span>')
    
    return RedirectResponse(url=f"/files/{file_id}", status_code=302)


@router.post("/files/sync-local")
async def sync_local_files(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Sync local files status with server.
    """
    try:
        body = await request.json()
        local_files = body.get("files", [])
        
        svc = FileService(db)
        result = await svc.sync_local_files(current_user.id, local_files)
        
        return JSONResponse({
            "success": True,
            "result": result
        })
    except Exception as e:
        logger.error(f"Sync error: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@router.get("/files/storage-stats")
async def get_storage_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get storage statistics for current user.
    """
    svc = FileService(db)
    stats = await svc.get_storage_stats(current_user.id)
    return JSONResponse(stats)


@router.get("/files/{file_id}/preview")
async def preview_file(
    file_id: int,
    rows: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get file preview as JSON.
    """
    svc = FileService(db)
    preview = await svc.get_preview(file_id, current_user.id, rows=rows)
    return JSONResponse({
        "success": True,
        "data": preview
    })
