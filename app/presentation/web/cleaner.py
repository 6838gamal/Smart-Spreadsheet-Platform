"""Data cleaner web routes."""

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.infrastructure.database.models import User
from app.infrastructure.repositories.file_repository import FileRepository
from app.application.cleaner.service import CleanerService
from app.application.cleaner.dto import CleanOptionsDTO

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/cleaner", response_class=HTMLResponse)
async def cleaner_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file_repo = FileRepository(db)
    files = await file_repo.get_by_owner(current_user.id, limit=100)
    return templates.TemplateResponse(
        request,
        "cleaner/index.html",
        {"user": current_user, "files": files, "current_page": "cleaner"},
    )


@router.post("/cleaner/clean")
async def do_clean(
    request: Request,
    file_id: int = Form(...),
    target_format: str = Form("xlsx"),
    remove_duplicates: bool = Form(False),
    trim_spaces: bool = Form(False),
    remove_empty_rows: bool = Form(False),
    remove_empty_cols: bool = Form(False),
    fill_nulls: str = Form(""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        svc = CleanerService(db)
        result = await svc.clean(
            CleanOptionsDTO(
                file_id=file_id,
                target_format=target_format,
                remove_duplicates=remove_duplicates,
                trim_spaces=trim_spaces,
                remove_empty_rows=remove_empty_rows,
                remove_empty_cols=remove_empty_cols,
                fill_nulls=fill_nulls or None,
            ),
            current_user.id,
        )
        if request.headers.get("HX-Request"):
            changes_html = "".join(f"<li>✓ {c}</li>" for c in result["changes"]) or "<li>لا تغييرات</li>"
            return HTMLResponse(f"""
            <div class="p-4 bg-green-900/40 border border-green-500/30 rounded-xl text-green-300">
                <div class="flex items-center gap-3 mb-3">
                    <svg class="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                    </svg>
                    <span class="font-semibold">تم تنظيف البيانات!</span>
                </div>
                <div class="text-sm mb-2 text-slate-300">
                    {result['original_rows']:,} صف → {result['result_rows']:,} صف
                </div>
                <ul class="text-sm text-green-400 mb-3 space-y-1">{changes_html}</ul>
                <a href="/cleaner/download/{result['output_filename']}"
                   class="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-white text-sm font-medium">
                    تحميل الملف المنظف
                </a>
            </div>""")
        return RedirectResponse(url="/cleaner", status_code=302)
    except Exception as e:
        if request.headers.get("HX-Request"):
            return HTMLResponse(
                f'<div class="p-4 bg-red-900/40 border border-red-500/30 rounded-xl text-red-300">خطأ: {e}</div>',
                status_code=400,
            )
        return RedirectResponse(url="/cleaner", status_code=302)


@router.get("/cleaner/download/{filename}")
async def download_cleaned(
    filename: str,
    current_user: User = Depends(get_current_user),
):
    from app.core.config import settings
    path = Path(settings.OUTPUT_DIR) / str(current_user.id) / filename
    if not path.exists():
        return RedirectResponse(url="/cleaner", status_code=302)
    return FileResponse(str(path), filename=filename)
