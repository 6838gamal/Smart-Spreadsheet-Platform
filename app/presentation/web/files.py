"""File manager web routes."""

import json
import logging
from fastapi import APIRouter, Depends, Request, UploadFile, File, Form, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
from typing import Optional
import io

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.templates import templates
from app.core.config import settings
from app.infrastructure.database.models import User, File as FileModel
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
    store_locally: bool = Form(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload files to the server with support for images and thumbnails.
    """
    svc = FileService(db)
    uploaded = []
    errors = []
    
    for file in files:
        try:
            f = await svc.upload(file, current_user.id, store_locally=store_locally)
            # Auto-analyze for supported formats
            if f.format and f.format.lower() in ['xlsx', 'xls', 'csv', 'json', 'pdf', 'txt']:
                await _auto_analyze(f.id, f.path, f.format, db)
            uploaded.append(f)
        except Exception as e:
            logger.error(f"Upload error for {file.filename}: {e}")
            errors.append(f"{file.filename}: {str(e)}")

    # HTMX response
    if request.headers.get("HX-Request"):
        if not uploaded:
            msg = " | ".join(errors) or "فشل الرفع"
            return HTMLResponse(f'<div class="text-red-400 text-sm text-center">{msg}</div>')

        if len(uploaded) == 1 and not errors:
            # For single file, redirect to analysis
            redirect_url = f"/intelligence/analyze/{uploaded[0].id}"
            return HTMLResponse(
                f'<div class="text-emerald-400 text-sm text-center">'
                f'✅ تم رفع الملف — جارٍ التوجيه للتحليل…'
                f'</div>'
                f'<script>setTimeout(()=>window.location.href="{redirect_url}",600)</script>'
            )

        msg = f"✅ تم رفع {len(uploaded)} ملف وبدأ التحليل تلقائياً"
        if errors:
            msg += f" ⚠️ ({len(errors)} أخطاء)"
        
        storage_info = " (مخزن محلياً)" if store_locally else " (مخزن في السحابة)"
        
        return HTMLResponse(
            f'<div class="text-emerald-400 text-sm text-center">{msg}{storage_info}</div>'
            f'<script>setTimeout(()=>location.reload(),1500)</script>'
        )

    # Non-HTMX response
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
    Display file detail page with preview and analysis.
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

    # Check if file exists on server
    file_exists_on_server = False
    try:
        if hasattr(svc.storage, 'file_exists'):
            file_exists_on_server = svc.storage.file_exists(f.path)
        else:
            file_exists_on_server = Path(f.path).exists() if f.path else False
    except Exception:
        file_exists_on_server = False

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
    Download file from server with support for large files.
    """
    svc = FileService(db)
    f = await svc.get_file(file_id, current_user.id)
    
    # Try to get file content
    content = await svc.get_file_content(file_id, current_user.id)
    if content:
        return StreamingResponse(
            io.BytesIO(content),
            media_type=f.mime_type or "application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{f.original_name}"',
                "Content-Length": str(len(content))
            }
        )
    
    # Try to stream from storage
    try:
        return StreamingResponse(
            svc.stream_file(file_id, current_user.id),
            media_type=f.mime_type or "application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{f.original_name}"',
                "Content-Length": str(f.size_bytes)
            }
        )
    except Exception as e:
        logger.error(f"Download error: {e}")
        return RedirectResponse(url="/files", status_code=302)


@router.get("/files/{file_id}/thumbnail")
async def get_thumbnail(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get file thumbnail (for images).
    """
    from PIL import Image
    import io
    
    svc = FileService(db)
    f = await svc.get_file(file_id, current_user.id)
    
    # Check if file is an image
    if not f.meta or not f.meta.get('is_image'):
        raise HTTPException(status_code=404, detail="Not an image file")
    
    # Try to get thumbnail from meta
    thumbnail_url = f.meta.get('thumbnail_url')
    if thumbnail_url:
        try:
            # Try to extract object key from URL
            if '/thumbnails/' in thumbnail_url:
                # Extract the path after thumbnails/
                path_parts = thumbnail_url.split('/thumbnails/')
                if len(path_parts) > 1:
                    # Try different possible paths
                    possible_paths = [
                        f"thumbnails/{path_parts[1]}",
                        f"thumbnails/{current_user.id}/{path_parts[1].split('/')[-1]}",
                    ]
                    for thumb_path in possible_paths:
                        if hasattr(svc.storage, 'file_exists') and svc.storage.file_exists(thumb_path):
                            read_path = await svc.storage.get_read_path(thumb_path, current_user.id)
                            if Path(read_path).exists():
                                return FileResponse(
                                    read_path,
                                    media_type="image/webp",
                                    headers={"Cache-Control": "public, max-age=31536000"}
                                )
        except Exception as e:
            logger.warning(f"⚠️ Failed to get thumbnail: {e}")
    
    # Generate thumbnail on the fly
    try:
        content = await svc.get_file_content(file_id, current_user.id)
        if content:
            img = Image.open(io.BytesIO(content))
            # Convert to RGB if needed
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            img.thumbnail((200, 200), Image.Resampling.LANCZOS)
            thumbnail_buffer = io.BytesIO()
            img.save(thumbnail_buffer, format='WEBP', quality=80)
            thumbnail_buffer.seek(0)
            
            return StreamingResponse(
                thumbnail_buffer,
                media_type="image/webp",
                headers={"Cache-Control": "public, max-age=31536000"}
            )
    except Exception as e:
        logger.error(f"❌ Thumbnail generation failed: {e}")
    
    # Return a default placeholder if thumbnail generation fails
    raise HTTPException(status_code=404, detail="Thumbnail not found")


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


@router.post("/files/{file_id}/rename")
async def rename_file(
    file_id: int,
    new_name: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Rename a file.
    """
    from app.application.files.dto import RenameFileDTO
    
    svc = FileService(db)
    dto = RenameFileDTO(new_name=new_name)
    f = await svc.rename_file(file_id, current_user.id, dto)
    
    if request.headers.get("HX-Request"):
        return HTMLResponse(f'<span class="text-sm font-medium">{f.original_name}</span>')
    
    return RedirectResponse(url=f"/files/{file_id}", status_code=302)
