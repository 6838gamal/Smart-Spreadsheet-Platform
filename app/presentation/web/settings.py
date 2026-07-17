"""Settings web routes."""

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.templates import templates
from app.infrastructure.database.models import User
from app.infrastructure.repositories.user_repository import UserRepository

router = APIRouter()


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return templates.TemplateResponse(
        request,
        "settings/index.html",
        {
            "user": current_user,
            "current_page": "settings",
            "lang": current_user.default_lang,
        },
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
        saved_msg = "✓ Saved" if language == "en" else "✓ تم الحفظ"
        return HTMLResponse(f'<div class="text-green-400 text-sm">{saved_msg}</div>')
    return RedirectResponse(url="/settings", status_code=302)


@router.post("/settings/lang")
async def switch_language(
    request: Request,
    lang: str = Form(...),
    next_url: str = Form("/dashboard"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Quick language toggle from the topbar."""
    if lang not in ("ar", "en"):
        lang = "ar"
    user_repo = UserRepository(db)
    prefs = {**current_user.preferences, "language": lang}
    await user_repo.update(current_user, preferences=prefs)
    # Redirect back to the page the user was on
    safe_next = next_url if next_url.startswith("/") else "/dashboard"
    return RedirectResponse(url=safe_next, status_code=302)
