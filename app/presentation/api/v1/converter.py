"""Converter API endpoints."""

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.infrastructure.database.models import User
from app.application.converter.service import ConverterService, EXPORT_FORMATS
from app.application.converter.dto import ConvertRequestDTO

router = APIRouter()


@router.get("/formats")
async def list_formats():
    return {"formats": EXPORT_FORMATS}


@router.post("/convert")
async def convert_file(
    dto: ConvertRequestDTO,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = ConverterService(db)
    result = await svc.convert(dto, current_user.id)
    return result


@router.get("/download/{filename}")
async def download_output(
    filename: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.core.config import settings
    path = Path(settings.OUTPUT_DIR) / str(current_user.id) / filename
    if not path.exists():
        from fastapi import HTTPException
        raise HTTPException(404, "File not found")
    return FileResponse(str(path), filename=filename)
