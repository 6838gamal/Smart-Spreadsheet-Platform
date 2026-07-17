"""Logs web routes."""

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.templates import templates
from app.infrastructure.database.models import User
from app.infrastructure.repositories.operation_repository import OperationRepository

router = APIRouter()


@router.get("/logs", response_class=HTMLResponse)
async def logs_page(
    request: Request,
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    op_repo = OperationRepository(db)
    limit = 25
    offset = (page - 1) * limit
    operations = await op_repo.get_by_user(current_user.id, limit=limit, offset=offset)
    total = await op_repo.count_by_user(current_user.id)
    total_pages = max(1, (total + limit - 1) // limit)

    return templates.TemplateResponse(
        request,
        "logs/index.html",
        {
            "user": current_user,
            "operations": operations,
            "total": total,
            "page": page,
            "total_pages": total_pages,
            "current_page": "logs",
            "lang": current_user.default_lang,
        },
    )
