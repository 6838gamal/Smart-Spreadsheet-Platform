"""Workspace web routes."""

import logging
import math
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.templates import templates
from app.core.config import settings
from app.core.dependencies import CurrentUser
from app.application.files.service import FileService
from app.presentation.web.files import files_to_dict_list

logger = logging.getLogger(__name__)
router = APIRouter()

PER_PAGE = 50


def _human_size(num_bytes: int) -> str:
    """Convert bytes to human-readable string."""
    if not num_bytes:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(num_bytes)
    while size >= 1024 and i < len(units) - 1:
        size /= 1024.0
        i += 1
    return f"{size:.2f} {units[i]}"


@router.get("/workspace", response_class=HTMLResponse)
async def workspace_page(
    request: Request,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Display workspace page (unified: tools + files + upload).
    """
    svc = FileService(db)

    # ─── Pagination ─────────────────────────────────────────────
    try:
        page = max(1, int(request.query_params.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    offset = (page - 1) * PER_PAGE

    # ─── Filtering ──────────────────────────────────────────────
    search = (request.query_params.get("search") or "").strip() or None
    fmt = (request.query_params.get("fmt") or "").strip().lower() or None

    # ─── open_file_id ───────────────────────────────────────────
    open_file_id: Optional[int] = None
    raw_file_id = request.query_params.get("file_id")
    if raw_file_id:
        try:
            open_file_id = int(raw_file_id)
        except (TypeError, ValueError):
            open_file_id = None

    # ─── Load files ─────────────────────────────────────────────
    files, total = await svc.list_files(
        user_id=user.id,
        search=search,
        format_filter=fmt,
        limit=PER_PAGE,
        offset=offset,
        sort_by="created_at",
        sort_order="desc",
    )

    files_dict = files_to_dict_list(files)

    # ─── Storage stats ──────────────────────────────────────────
    total_size_human = "0 B"
    try:
        stats = await svc.get_storage_stats(user.id)
        # get_storage_stats يرجع dict — قد يحتوي total_size_human أو total_size
        if isinstance(stats, dict):
            if stats.get("total_size_human"):
                total_size_human = stats["total_size_human"]
            elif stats.get("total_size") is not None:
                total_size_human = _human_size(int(stats["total_size"]))
    except Exception as e:
        logger.warning(f"Failed to get storage stats: {e}")

    # ─── Pagination metadata ────────────────────────────────────
    total_pages = max(1, math.ceil(total / PER_PAGE)) if total else 1

    # ─── Language ───────────────────────────────────────────────
    lang = getattr(user, "default_lang", None) or "ar"

    return templates.TemplateResponse(
        request,
        "workspace/index.html",
        {
            "user": user,
            "files": files_dict,
            "total": total,
            "total_pages": total_pages,
            "page": page,
            "per_page": PER_PAGE,
            "search": search or "",
            "fmt": fmt or "",
            "total_size_human": total_size_human,
            "open_file_id": open_file_id,
            "settings": settings,
            "lang": lang,
        },
    )


@router.get("/workspace/files-panel", response_class=HTMLResponse)
async def panel_files(
    request: Request,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Get files panel partial (HTMX)."""
    svc = FileService(db)

    files, total = await svc.list_files(
        user_id=user.id,
        limit=PER_PAGE,
        offset=0,
        sort_by="created_at",
        sort_order="desc",
    )

    files_dict = files_to_dict_list(files)

    return templates.TemplateResponse(
        request,
        "workspace/_files_panel.html",
        {
            "files": files_dict,
            "total": total,
            "lang": getattr(user, "default_lang", None) or "ar",
        },
    )


@router.get("/workspace/files-list", response_class=HTMLResponse)
async def files_list_partial(
    request: Request,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Get files list partial for HTMX refresh."""
    return await panel_files(request, user, db)


@router.get("/workspace/file-card/{file_id}", response_class=HTMLResponse)
async def file_card_partial(
    request: Request,
    file_id: int,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Get a single file card partial."""
    svc = FileService(db)

    try:
        file = await svc.get_file(file_id, user.id)
        file_dict = files_to_dict_list([file])[0] if file else None

        return templates.TemplateResponse(
            request,
            "workspace/_file_card.html",
            {
                "file": file_dict,
                "lang": getattr(user, "default_lang", None) or "ar",
            },
        )
    except Exception as e:
        logger.error(f"Error getting file card: {e}")
        return HTMLResponse("", status_code=404)
