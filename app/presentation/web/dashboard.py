"""Dashboard web route."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.infrastructure.database.models import User
from app.application.dashboard.service import DashboardService

router = APIRouter()
templates = Jinja2Templates(directory="templates")


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
        {"user": current_user, "stats": stats, "current_page": "dashboard"},
    )
