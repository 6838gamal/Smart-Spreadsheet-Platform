"""Settings web routes."""

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.infrastructure.database.models import User
from app.infrastructure.repositories.user_repository import UserRepository

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return templates.TemplateResponse(
        request,
        "settings/index.html",
        {"user": current_user, "current_page": "settings"},
    )


@router.post("/settings/preferences")
async def save_preferences(
    request: Request,
    theme: str = Form("dark"),
    language: str = Form("ar"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_repo = UserRepository(db)
    prefs = {**current_user.preferences, "theme": theme, "language": language}
    await user_repo.update(current_user, preferences=prefs)

    if request.headers.get("HX-Request"):
        return HTMLResponse('<div class="text-green-400 text-sm">✓ تم الحفظ</div>')
    return RedirectResponse(url="/settings", status_code=302)
