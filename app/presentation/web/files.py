"""File manager web routes."""

import json
from fastapi import APIRouter, Depends, Request, UploadFile, File, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.infrastructure.database.models import User
from app.application.files.service import FileService

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/files", response_class=HTMLResponse)
async def files_page(
    request: Request,
    search: str = "",
    fmt: str = "",
    page: int = 1,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = FileService(db)
    limit = 20
    offset = (page - 1) * limit
    files, total = await svc.list_files(
        current_user.id,
        search=search or None,
        format_filter=fmt or None,
        limit=limit,
        offset=offset,
    )
    total_pages = max(1, (total + limit - 1) // limit)
    return templates.TemplateResponse(
        request,
        "files/index.html",
        {
            "user": current_user,
            "files": files,
            "total": total,
            "page": page,
            "total_pages": total_pages,
            "search": search,
            "fmt": fmt,
            "current_page": "files",
        },
    )


@router.post("/files/upload")
async def upload_files(
    request: Request,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = FileService(db)
    uploaded = []
    errors = []
    for file in files:
        try:
            f = await svc.upload(file, current_user.id)
            uploaded.append(f.original_name)
        except Exception as e:
            errors.append(f"{file.filename}: {e}")

    if request.headers.get("HX-Request"):
        msg = f"تم رفع {len(uploaded)} ملف بنجاح"
        if errors:
            msg += f" | {len(errors)} أخطاء"
        return HTMLResponse(f'<div class="alert-success">{msg}</div>')
    return RedirectResponse(url="/files", status_code=302)


@router.get("/files/{file_id}", response_class=HTMLResponse)
async def file_detail(
    request: Request,
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = FileService(db)
    f = await svc.get_file(file_id, current_user.id)
    preview = await svc.get_preview(file_id, current_user.id, rows=200)
    return templates.TemplateResponse(
        request,
        "files/detail.html",
        {
            "user": current_user,
            "file": f,
            "preview": preview,
            "current_page": "files",
        },
    )


@router.get("/files/{file_id}/download")
async def download_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = FileService(db)
    f = await svc.get_file(file_id, current_user.id)
    if not Path(f.path).exists():
        return RedirectResponse(url="/files", status_code=302)
    return FileResponse(f.path, filename=f.original_name)


@router.post("/files/{file_id}/delete")
async def delete_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = FileService(db)
    await svc.delete_file(file_id, current_user.id)
    return RedirectResponse(url="/files", status_code=302)


@router.post("/files/{file_id}/favorite")
async def toggle_favorite(
    request: Request,
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = FileService(db)
    f = await svc.toggle_favorite(file_id, current_user.id)
    if request.headers.get("HX-Request"):
        icon = "★" if f.is_favorite else "☆"
        cls = "text-yellow-400" if f.is_favorite else "text-slate-200 dark:text-slate-600"
        return HTMLResponse(f'<span class="{cls}">{icon}</span>')
    return RedirectResponse(url=f"/files/{file_id}", status_code=302)
