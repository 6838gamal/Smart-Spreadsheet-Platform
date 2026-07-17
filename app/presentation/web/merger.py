"""Merger web routes."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.templates import templates
from app.infrastructure.database.models import User
from app.infrastructure.repositories.file_repository import FileRepository

router = APIRouter()


@router.get("/merger", response_class=HTMLResponse)
async def merger_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file_repo = FileRepository(db)
    files = await file_repo.get_by_owner(current_user.id, limit=100)
    return templates.TemplateResponse(
        request,
        "merger/index.html",
        {
            "user": current_user,
            "files": files,
            "current_page": "merger",
            "lang": current_user.default_lang,
        },
    )
