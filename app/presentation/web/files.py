"""File manager web routes."""

import json
import logging
from fastapi import APIRouter, Depends, Request, UploadFile, File, Form, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
from typing import Optional, List
import io

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_user_optional
from app.core.templates import templates
from app.core.config import settings
from app.infrastructure.database.models import User, File as FileModel
from app.application.files.service import FileService

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def file_to_dict(file: FileModel) -> dict:
    """Convert a File object to a dictionary for JSON serialization."""
    if not file:
        return None
    
    return {
        "id": file.id,
        "name": file.name,
        "original_name": file.original_name,
        "path": file.path,
        "size_bytes": file.size_bytes,
        "format": file.format,
        "mime_type": file.mime_type,
        "status": file.status,
        "is_favorite": file.is_favorite,
        "tags": file.tags or [],
        "meta": file.meta or {},
        "owner_id": file.owner_id,
        "storage_key": getattr(file, 'storage_key', None),
        "is_locally_stored": getattr(file, 'is_locally_stored', False),
        "storage_backend": getattr(file, 'storage_backend', None),
        "storage_bucket": getattr(file, 'storage_bucket', None),
        "storage_object_key": getattr(file, 'storage_object_key', None),
        "created_at": file.created_at.isoformat() if file.created_at else None,
        "updated_at": file.updated_at.isoformat() if file.updated_at else None,
        "thumbnail_url": file.meta.get('thumbnail_url') if file.meta else None,
        "is_image": file.meta.get('is_image', False) if file.meta else False,
        "image_width": file.meta.get('image_width') if file.meta else None,
        "image_height": file.meta.get('image_height') if file.meta else None,
        "size_human": file.size_human if hasattr(file, 'size_human') else f"{file.size_bytes} B" if file.size_bytes else "0 B",
    }


def files_to_dict_list(files: List[FileModel]) -> List[dict]:
    """Convert a list of File objects to a list of dictionaries."""
    if not files:
        return []
    return [file_to_dict(file) for file in files]


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


# ============================================================
# ROUTES
# ============================================================

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
    """Display files page with filtering, sorting, and pagination."""
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
    files_dict = files_to_dict_list(files)
    
    return templates.TemplateResponse(
        request,
        "files/index.html",
        {
            "user": current_user,
            "files": files_dict,
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
    """Upload files to the server with support for images and thumbnails."""
    svc = FileService(db)
    uploaded_files = []
    errors = []
    
    for file in files:
        try:
            f = await svc.upload(file, current_user.id, store_locally=store_locally)
            if f.format and f.format.lower() in ['xlsx', 'xls', 'csv', 'json', 'pdf', 'txt', 'docx', 'doc']:
                await _auto_analyze(f.id, f.path, f.format, db)
            uploaded_files.append(f)
        except Exception as e:
            logger.error(f"Upload error for {file.filename}: {e}")
            errors.append(f"{file.filename}: {str(e)}")

    # HTMX response
    if request.headers.get("HX-Request"):
        if not uploaded_files:
            msg = " | ".join(errors) or "فشل الرفع"
            return HTMLResponse(f'<div class="text-red-400 text-sm text-center">{msg}</div>')

        # ✅ تحديث القائمة فقط بدون توجيه
        all_files, total = await svc.list_files(
            user_id=current_user.id,
            limit=100,
            offset=0,
            sort_by="created_at",
            sort_order="desc"
        )
        all_files_dict = files_to_dict_list(all_files)
        
        # ✅ تحديد الملف المرفوع إذا كان ملف واحد
        selected_file_id = uploaded_files[0].id if len(uploaded_files) == 1 else None
        
        html_content = templates.TemplateResponse(
            request,
            "workspace/_files_panel.html",
            {
                "files": all_files_dict,
                "total": total,
                "lang": current_user.default_lang,
                "uploaded_count": len(uploaded_files),
                "has_errors": len(errors) > 0,
                "selected_file_id": selected_file_id,
            }
        )
        
        msg = f"✅ تم رفع {len(uploaded_files)} ملف بنجاح"
        if errors:
            msg += f" ⚠️ ({len(errors)} أخطاء)"
        
        # ✅ إرسال حدث لتحديث لوحة التحويل
        if selected_file_id:
            return HTMLResponse(
                f'<div class="mb-2 text-sm text-emerald-400 text-center">{msg}</div>'
                f'<script>'
                f'  window.dispatchEvent(new CustomEvent("file-uploaded", {{ detail: {{ fileId: {selected_file_id} }} }}));'
                f'</script>'
                + html_content.body.decode('utf-8')
            )
        
        return HTMLResponse(
            f'<div class="mb-2 text-sm text-emerald-400 text-center">{msg}</div>'
            + html_content.body.decode('utf-8')
        )

    # Non-HTMX response
    return RedirectResponse(url="/files", status_code=302)


@router.get("/files/{file_id}", response_class=HTMLResponse)
async def file_detail(
    request: Request,
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Display file detail page with preview and analysis."""
    svc = FileService(db)
    f = await svc.get_file(file_id, current_user.id)
    
    f.storage_key = getattr(f, 'storage_key', None)
    f.is_locally_stored = getattr(f, 'is_locally_stored', False)
    
    preview = None
    try:
        preview = await svc.get_preview(file_id, current_user.id, rows=200)
    except Exception as e:
        logger.warning(f"Preview not available for file {file_id}: {e}")
        preview = {"error": str(e), "available": False}

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

    file_exists_on_server = False
    try:
        if hasattr(svc.storage, 'file_exists'):
            file_exists_on_server = svc.storage.file_exists(f.path)
        else:
            file_exists_on_server = Path(f.path).exists() if f.path else False
    except Exception:
        file_exists_on_server = False

    file_dict = file_to_dict(f)

    return templates.TemplateResponse(
        request,
        "files/detail.html",
        {
            "user": current_user,
            "file": file_dict,
            "file_obj": f,
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
    """Download file from server with support for large files."""
    svc = FileService(db)
    f = await svc.get_file(file_id, current_user.id)
    
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
    """Get file thumbnail (for images)."""
    from PIL import Image
    import io
    
    svc = FileService(db)
    f = await svc.get_file(file_id, current_user.id)
    
    if not f.meta or not f.meta.get('is_image'):
        raise HTTPException(status_code=404, detail="Not an image file")
    
    thumbnail_url = f.meta.get('thumbnail_url')
    if thumbnail_url:
        try:
            if '/thumbnails/' in thumbnail_url:
                path_parts = thumbnail_url.split('/thumbnails/')
                if len(path_parts) > 1:
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
            logger.warning(f"Failed to get thumbnail: {e}")
    
    try:
        content = await svc.get_file_content(file_id, current_user.id)
        if content:
            img = Image.open(io.BytesIO(content))
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
        logger.error(f"Thumbnail generation failed: {e}")
    
    raise HTTPException(status_code=404, detail="Thumbnail not found")


@router.delete("/files/{file_id}")
async def delete_file_api(
    request: Request,
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete file from server - API endpoint."""
    svc = FileService(db)
    
    try:
        await svc.delete_file(file_id, current_user.id)
        return JSONResponse({
            "success": True,
            "message": "File deleted successfully"
        })
    except Exception as e:
        logger.error(f"Delete error: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@router.post("/files/{file_id}/delete")
async def delete_file_web(
    request: Request,
    file_id: int,
    delete_local: bool = Form(True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete file from server - Web endpoint."""
    svc = FileService(db)
    await svc.delete_file(file_id, current_user.id, delete_local=delete_local)
    
    if request.headers.get("HX-Request"):
        all_files, total = await svc.list_files(
            user_id=current_user.id,
            limit=50,
            offset=0,
            sort_by="created_at",
            sort_order="desc"
        )
        all_files_dict = files_to_dict_list(all_files)
        
        return templates.TemplateResponse(
            request,
            "workspace/_files_panel.html",
            {
                "files": all_files_dict,
                "total": total,
                "lang": current_user.default_lang,
            }
        )
    
    return RedirectResponse(url="/files", status_code=302)


@router.post("/files/{file_id}/favorite")
async def toggle_favorite(
    request: Request,
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toggle favorite status of a file."""
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
    """Sync local files status with server."""
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
    """Get storage statistics for current user."""
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
    """Get file preview as JSON."""
    svc = FileService(db)
    preview = await svc.get_preview(file_id, current_user.id, rows=rows)
    return JSONResponse({
        "success": True,
        "data": preview
    })


@router.post("/files/{file_id}/rename")
async def rename_file(
    request: Request,
    file_id: int,
    new_name: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rename a file."""
    from app.application.files.dto import RenameFileDTO
    
    svc = FileService(db)
    dto = RenameFileDTO(new_name=new_name)
    f = await svc.rename_file(file_id, current_user.id, dto)
    
    if request.headers.get("HX-Request"):
        return HTMLResponse(f'<span class="text-sm font-medium">{f.original_name}</span>')
    
    return RedirectResponse(url=f"/files/{file_id}", status_code=302)


# ============================================================
# API ENDPOINTS FOR ALPINE.JS
# ============================================================

@router.get("/api/files/list")
async def api_list_files(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
):
    """API endpoint for Alpine.js to get file list as JSON."""
    svc = FileService(db)
    
    files, total = await svc.list_files(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        sort_by="created_at",
        sort_order="desc"
    )
    
    files_dict = files_to_dict_list(files)
    
    return JSONResponse({
        "success": True,
        "files": files_dict,
        "total": total,
        "limit": limit,
        "offset": offset,
    })


@router.get("/api/files/{file_id}")
async def api_get_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """API endpoint to get a single file by ID."""
    svc = FileService(db)
    
    try:
        f = await svc.get_file(file_id, current_user.id)
        file_dict = file_to_dict(f)
        return JSONResponse({
            "success": True,
            "file": file_dict
        })
    except Exception as e:
        logger.error(f"Error getting file: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=404)


@router.delete("/api/files/{file_id}")
async def api_delete_file(
    request: Request,
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """API endpoint for Alpine.js to delete a file."""
    svc = FileService(db)
    
    try:
        await svc.delete_file(file_id, current_user.id)
        return JSONResponse({
            "success": True,
            "message": "File deleted successfully"
        })
    except Exception as e:
        logger.error(f"Delete error: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)
