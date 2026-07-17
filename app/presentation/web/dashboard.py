"""Dashboard web route."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.templates import templates
from app.infrastructure.database.models import User
from app.application.dashboard.service import DashboardService

router = APIRouter()


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = DashboardService(db)
    stats = await svc.get_stats(current_user.id)
    return templates.TemplateResponse(
        request,
        "dashboard/index.html",
        {
            "user": current_user,
            "stats": stats,
            "current_page": "dashboard",
            "lang": current_user.default_lang,
        },
    )
