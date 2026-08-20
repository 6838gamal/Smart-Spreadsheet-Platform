"""Workspace web routes."""

import logging
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.templates import templates
from app.core.dependencies import CurrentUser, get_current_user_optional
from app.application.files.service import FileService
from app.infrastructure.database.models import File
from app.presentation.web.files import files_to_dict_list

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/workspace", response_class=HTMLResponse)
async def workspace_page(
    request: Request,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Display workspace page.
    """
    svc = FileService(db)
    
    # Get files for the user
    files, total = await svc.list_files(
        user_id=user.id,
        limit=50,
        offset=0,
        sort_by="created_at",
        sort_order="desc"
    )
    
    # Convert files to dictionaries for JSON serialization
    files_dict = files_to_dict_list(files)
    
    return templates.TemplateResponse(
        request,
        "workspace/index.html",
        {
            "user": user,
            "files": files_dict,
            "total": total,
            "lang": getattr(user, 'default_lang', 'ar'),
        },
    )


@router.get("/workspace/files-panel", response_class=HTMLResponse)
async def panel_files(
    request: Request,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Get files panel partial (HTMX).
    """
    svc = FileService(db)
    
    files, total = await svc.list_files(
        user_id=user.id,
        limit=50,
        offset=0,
        sort_by="created_at",
        sort_order="desc"
    )
    
    # Convert files to dictionaries for JSON serialization
    files_dict = files_to_dict_list(files)
    
    return templates.TemplateResponse(
        request,
        "workspace/_files_panel.html",
        {
            "files": files_dict,
            "total": total,
            "lang": getattr(user, 'default_lang', 'ar'),
        },
    )


@router.get("/workspace/files-list", response_class=HTMLResponse)
async def files_list_partial(
    request: Request,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Get files list partial for HTMX refresh.
    """
    svc = FileService(db)
    
    files, total = await svc.list_files(
        user_id=user.id,
        limit=50,
        offset=0,
        sort_by="created_at",
        sort_order="desc"
    )
    
    files_dict = files_to_dict_list(files)
    
    return templates.TemplateResponse(
        request,
        "workspace/_files_panel.html",
        {
            "files": files_dict,
            "total": total,
            "lang": getattr(user, 'default_lang', 'ar'),
        },
    )


@router.get("/workspace/file-card/{file_id}", response_class=HTMLResponse)
async def file_card_partial(
    request: Request,
    file_id: int,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a single file card partial.
    """
    svc = FileService(db)
    
    try:
        file = await svc.get_file(file_id, user.id)
        file_dict = files_to_dict_list([file])[0] if file else None
        
        return templates.TemplateResponse(
            request,
            "workspace/_file_card.html",
            {
                "file": file_dict,
                "lang": getattr(user, 'default_lang', 'ar'),
            },
        )
    except Exception as e:
        logger.error(f"Error getting file card: {e}")
        return HTMLResponse("", status_code=404)
