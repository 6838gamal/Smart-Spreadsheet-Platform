"""Web route — Smart Search / Document Q&A page."""
from __future__ import annotations
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.templates import templates
from app.infrastructure.database.models import User, File
from app.infrastructure.database.models_intelligence import DocumentChunk

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/search", response_class=HTMLResponse)
async def search_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Render the Smart Search / Document Q&A page."""
    # Files that have indexed chunks
    indexed_file_ids_rows = (await db.execute(
        select(DocumentChunk.file_id).where(
            DocumentChunk.user_id == current_user.id
        ).distinct()
    )).scalars().all()
    indexed_ids = set(indexed_file_ids_rows)

    # All user files (to show which are indexed)
    all_files_rows = (await db.execute(
        select(File).where(File.owner_id == current_user.id).order_by(File.created_at.desc())
    )).scalars().all()

    files_info = [
        {
            "id": f.id,
            "original_name": f.original_name,
            "file_format": f.file_format,
            "is_indexed": f.id in indexed_ids,
        }
        for f in all_files_rows
    ]

    indexed_count = len(indexed_ids)
    total_chunks = (await db.execute(
        select(DocumentChunk.id).where(DocumentChunk.user_id == current_user.id)
    )).scalars().all()

    return templates.TemplateResponse(request, "search/index.html", {
        "user": current_user,
        "page_title": "البحث الذكي",
        "current_page": "search",
        "lang": current_user.default_lang,
        "files_info": files_info,
        "indexed_count": indexed_count,
        "total_chunks": len(total_chunks),
    })
