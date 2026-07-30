"""Web routes for the Model Manager UI."""
from __future__ import annotations
import logging
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.templates import templates
from app.infrastructure.database.models import User

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/models", response_class=HTMLResponse)
async def models_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return templates.TemplateResponse("models/index.html", {
        "request": request,
        "user": current_user,
        "current_page": "models",
        "lang": current_user.default_lang,
        "page_title": "مدير النماذج",
    })
