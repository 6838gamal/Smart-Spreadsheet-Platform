"""Files API endpoints.

Includes automatic analysis + indexing on upload:
when a file is uploaded, `analyze_and_index_background` is scheduled
as a FastAPI BackgroundTask so the file becomes searchable without
any manual action from the user.
"""

import logging

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    UploadFile,
    File,
    HTTPException,
)
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.infrastructure.database.models import User, File as FileModel
from app.infrastructure.database.models_intelligence import (
    DocumentAnalysis,
    DocumentChunk,
)
from app.application.files.service import FileService
from app.application.files.dto import RenameFileDTO

logger = logging.getLogger(__name__)

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════
#  List files
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/")
async def list_files(
    page: int = 1,
    per_page: int = 20,
    section: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.application.files.service import FileService

    svc = FileService(db)
    limit = per_page
    offset = (page - 1) * per_page
    files, total = await svc.list_files(
        current_user.id,
        limit=limit,
        offset=offset,
    )
    items = [
        {
            "id": f.id,
            "filename": f.name,
            "original_filename": f.original_name,
            "file_type": f.extension,
            "file_size": f.size_bytes,
            "status": f.status.value if hasattr(f.status, "value") else str(f.status),
            "created_at": f.created_at.isoformat() if f.created_at else None,
            "is_favorite": getattr(f, "is_favorite", False),
        }
        for f in files
    ]
    return {"items": items, "total": total, "page": page, "per_page": per_page}


# ═══════════════════════════════════════════════════════════════════════════
#  Upload file — with AUTO analyze + index
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a file and automatically schedule analysis + indexing.

    The response includes:
        - ``auto_analyzing``: True if the background task was scheduled
        - ``status_url``: endpoint to poll for pipeline status
    """
    # ── 1. Persist file via FileService (storage + DB) ───────────────────
    svc = FileService(db)
    f = await svc.upload(file, current_user.id)

    # ── 2. Schedule automatic analysis + indexing ────────────────────────
    analysis_scheduled = False
    try:
        from app.services.pipeline.analyze_and_index_task import (
            analyze_and_index_background,
        )

        background_tasks.add_task(
            analyze_and_index_background,
            file_id=f.id,
            user_id=current_user.id,
        )
        analysis_scheduled = True
        logger.info(
            f"🚀 [upload] Auto-analyze scheduled for file {f.id} "
            f"({f.original_name}, user={current_user.id})"
        )
    except ImportError as e:
        logger.error(
            f"❌ [upload] Cannot import analyze_and_index_background: {e}"
        )
    except Exception as e:
        logger.exception(
            f"⚠️ [upload] Failed to schedule auto-analyze for file {f.id}: {e}"
        )

    # ── 3. Response ──────────────────────────────────────────────────────
    return {
        "id": f.id,
        "name": f.name,
        "original_name": f.original_name,
        "size": f.size_human,
        "auto_analyzing": analysis_scheduled,
        "status_url": f"/api/v1/search/files/{f.id}/status",
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Bulk: analyze all pending files
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/analyze-all-pending")
async def analyze_all_pending_files(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Schedule analysis + indexing for every file that is not yet ready.

    Useful for:
      - enabling the search feature on an existing account
      - recovering after a crashed/killed background task
    """
    try:
        from app.services.pipeline.analyze_and_index_task import (
            analyze_and_index_background,
        )
    except ImportError as e:
        logger.error(f"❌ [analyze-all] Cannot import background task: {e}")
        raise HTTPException(
            status_code=500,
            detail="خدمة التحليل غير متوفرة حالياً.",
        )

    # ── Fetch all user files ─────────────────────────────────────────────
    files = (
        await db.execute(
            select(FileModel).where(FileModel.owner_id == current_user.id)
        )
    ).scalars().all()

    if not files:
        return {"ok": True, "scheduled": 0, "total_files": 0}

    # ── Fetch which files already have chunks ────────────────────────────
    file_ids = [f.id for f in files]
    indexed_ids = set(
        (
            await db.execute(
                select(DocumentChunk.file_id)
                .where(
                    DocumentChunk.user_id == current_user.id,
                    DocumentChunk.file_id.in_(file_ids),
                )
                .distinct()
            )
        ).scalars().all()
    )

    # ── Schedule analysis for non-indexed files ──────────────────────────
    scheduled = 0
    for f in files:
        if f.id in indexed_ids:
            continue
        background_tasks.add_task(
            analyze_and_index_background,
            file_id=f.id,
            user_id=current_user.id,
        )
        scheduled += 1

    logger.info(
        f"🚀 [analyze-all] Scheduled {scheduled}/{len(files)} files "
        f"for user {current_user.id}"
    )

    return {
        "ok": True,
        "scheduled": scheduled,
        "total_files": len(files),
        "already_indexed": len(indexed_ids),
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Preview
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/{file_id}/preview")
async def preview_file(
    file_id: int,
    rows: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = FileService(db)
    return await svc.get_preview(file_id, current_user.id, rows=rows)


# ═══════════════════════════════════════════════════════════════════════════
#  Delete
# ═══════════════════════════════════════════════════════════════════════════

@router.delete("/{file_id}")
async def delete_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = FileService(db)
    await svc.delete_file(file_id, current_user.id)
    return {"message": "File deleted"}


# ═══════════════════════════════════════════════════════════════════════════
#  Rename
# ═══════════════════════════════════════════════════════════════════════════

@router.patch("/{file_id}/rename")
async def rename_file(
    file_id: int,
    dto: RenameFileDTO,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = FileService(db)
    f = await svc.rename_file(file_id, current_user.id, dto)
    return {"id": f.id, "name": f.name}


# ═══════════════════════════════════════════════════════════════════════════
#  Favorite
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/{file_id}/favorite")
async def toggle_favorite(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = FileService(db)
    f = await svc.toggle_favorite(file_id, current_user.id)
    return {"id": f.id, "is_favorite": f.is_favorite}


# ═══════════════════════════════════════════════════════════════════════════
#  Download
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/{file_id}/download")
async def download_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = FileService(db)
    f = await svc.get_file(file_id, current_user.id)
    if not Path(f.path).exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(f.path, filename=f.original_name)
