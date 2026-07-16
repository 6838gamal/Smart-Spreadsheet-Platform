"""Cleaner API endpoints."""

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.infrastructure.database.models import User
from app.application.cleaner.service import CleanerService
from app.application.cleaner.dto import CleanOptionsDTO

router = APIRouter()


@router.post("/clean")
async def clean_file(
    dto: CleanOptionsDTO,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = CleanerService(db)
    return await svc.clean(dto, current_user.id)
