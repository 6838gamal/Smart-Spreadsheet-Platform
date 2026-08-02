"""Files API endpoints."""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.infrastructure.database.models import User
from app.application.files.service import FileService
from app.application.files.dto import RenameFileDTO

router = APIRouter()


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


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = FileService(db)
    f = await svc.upload(file, current_user.id)
    return {"id": f.id, "name": f.name, "original_name": f.original_name, "size": f.size_human}


@router.get("/{file_id}/preview")
async def preview_file(
    file_id: int,
    rows: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = FileService(db)
    return await svc.get_preview(file_id, current_user.id, rows=rows)


@router.delete("/{file_id}")
async def delete_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = FileService(db)
    await svc.delete_file(file_id, current_user.id)
    return {"message": "File deleted"}


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


@router.post("/{file_id}/favorite")
async def toggle_favorite(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = FileService(db)
    f = await svc.toggle_favorite(file_id, current_user.id)
    return {"id": f.id, "is_favorite": f.is_favorite}


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
