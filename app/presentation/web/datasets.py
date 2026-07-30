"""Web routes for the Dataset Manager UI."""
from __future__ import annotations
import logging
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.infrastructure.database.models import User

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/datasets", response_class=HTMLResponse)
async def datasets_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return templates.TemplateResponse("datasets/index.html", {
        "request": request,
        "user": current_user,
        "current_page": "datasets",
        "lang": current_user.default_lang,
        "page_title": "مدير مجموعات البيانات",
    })
