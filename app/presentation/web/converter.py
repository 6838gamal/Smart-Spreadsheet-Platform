"""Converter web routes."""

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from app.core.templates import templates
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.infrastructure.database.models import User
from app.infrastructure.repositories.file_repository import FileRepository
from app.application.converter.service import ConverterService, EXPORT_FORMATS
from app.application.converter.dto import ConvertRequestDTO

router = APIRouter()


@router.get("/converter", response_class=HTMLResponse)
async def converter_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file_repo = FileRepository(db)
    files = await file_repo.get_by_owner(current_user.id, limit=100)
    return templates.TemplateResponse(
        request,
        "converter/index.html",
        {
            "user": current_user,
            "files": files,
            "export_formats": EXPORT_FORMATS,
            "current_page": "converter",
            "lang": current_user.default_lang,
        },
    )


@router.post("/converter/convert")
async def do_convert(
    request: Request,
    file_id: int = Form(...),
    target_format: str = Form(...),
    sheet: str = Form(""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        svc = ConverterService(db)
        result = await svc.convert(
            ConvertRequestDTO(
                file_id=file_id,
                target_format=target_format,
                sheet=sheet or None,
            ),
            current_user.id,
        )
        if request.headers.get("HX-Request"):
            return HTMLResponse(f"""
            <div class="p-4 bg-green-900/40 border border-green-500/30 rounded-xl text-green-300">
                <div class="flex items-center gap-3 mb-3">
                    <svg class="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                    </svg>
                    <span class="font-semibold">تم التحويل بنجاح!</span>
                </div>
                <p class="text-sm text-green-400 mb-3">
                    {result.rows:,} صف × {result.columns} عمود · {result.duration_ms}ms
                </p>
                <a href="/converter/download/{result.output_filename}"
                   class="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-white text-sm font-medium transition-colors">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                    </svg>
                    تحميل {result.output_filename}
                </a>
            </div>""")
        return RedirectResponse(url="/converter", status_code=302)
    except Exception as e:
        if request.headers.get("HX-Request"):
            return HTMLResponse(
                f'<div class="p-4 bg-red-900/40 border border-red-500/30 rounded-xl text-red-300">خطأ: {e}</div>',
                status_code=400,
            )
        return RedirectResponse(url="/converter", status_code=302)


@router.get("/converter/download/{filename}")
async def download_converted(
    filename: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.core.config import settings
    path = Path(settings.OUTPUT_DIR) / str(current_user.id) / filename
    if not path.exists():
        return RedirectResponse(url="/converter", status_code=302)
    return FileResponse(str(path), filename=filename)
