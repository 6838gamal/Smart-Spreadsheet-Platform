"""Web route — Smart Search / Document Q&A page."""
from __future__ import annotations
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.templates import templates
from app.infrastructure.database.models import User, File
from app.infrastructure.database.models_intelligence import DocumentChunk

logger = logging.getLogger(__name__)
router = APIRouter()


async def ensure_storage_columns(db: AsyncSession) -> bool:
    """Ensure storage columns exist in files table."""
    try:
        # Check if columns exist
        result = await db.execute(text("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name = 'files' 
                AND column_name = 'storage_key'
            )
        """))
        exists = result.scalar()
        
        if not exists:
            logger.warning("Storage columns missing, adding them now...")
            storage_columns = [
                ("storage_key", "VARCHAR"),
                ("is_locally_stored", "BOOLEAN DEFAULT TRUE"),
                ("last_synced_at", "TIMESTAMP"),
                ("storage_backend", "VARCHAR"),
                ("storage_bucket", "VARCHAR"),
                ("storage_object_key", "VARCHAR"),
            ]
            
            for col_name, col_type in storage_columns:
                await db.execute(text(
                    f"ALTER TABLE files "
                    f"ADD COLUMN IF NOT EXISTS {col_name} {col_type};"
                ))
                logger.info(f"✅ Column '{col_name}' added to files")
            
            # Create index
            await db.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_files_storage_key "
                "ON files (storage_key);"
            ))
            
            await db.commit()
            logger.info("✅ Storage columns added successfully")
            return True
            
        return False
        
    except Exception as e:
        logger.error(f"Error ensuring storage columns: {e}")
        await db.rollback()
        return False


@router.get("/search", response_class=HTMLResponse)
async def search_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Render the Smart Search / Document Q&A page."""
    # Ensure storage columns exist
    await ensure_storage_columns(db)
    
    try:
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
                "file_format": f.format,
                "is_indexed": f.id in indexed_ids,
            }
            for f in all_files_rows
        ]

        indexed_count = len(indexed_ids)
        total_chunks_result = (await db.execute(
            select(DocumentChunk.id).where(DocumentChunk.user_id == current_user.id)
        ))
        total_chunks = total_chunks_result.scalars().all()

        return templates.TemplateResponse(request, "search/index.html", {
            "user": current_user,
            "page_title": "البحث الذكي",
            "current_page": "search",
            "lang": current_user.default_lang,
            "files_info": files_info,
            "indexed_count": indexed_count,
            "total_chunks": len(total_chunks),
        })
        
    except Exception as e:
        logger.error(f"Error in search_page: {e}")
        # Check if it's a column missing error
        if "column" in str(e).lower() and "does not exist" in str(e).lower():
            # Try one more time with recovery
            logger.warning("Column error detected, attempting recovery...")
            await ensure_storage_columns(db)
            
            # Retry the query
            indexed_file_ids_rows = (await db.execute(
                select(DocumentChunk.file_id).where(
                    DocumentChunk.user_id == current_user.id
                ).distinct()
            )).scalars().all()
            indexed_ids = set(indexed_file_ids_rows)

            all_files_rows = (await db.execute(
                select(File).where(File.owner_id == current_user.id).order_by(File.created_at.desc())
            )).scalars().all()

            files_info = [
                {
                    "id": f.id,
                    "original_name": f.original_name,
                    "file_format": f.format,
                    "is_indexed": f.id in indexed_ids,
                }
                for f in all_files_rows
            ]

            indexed_count = len(indexed_ids)
            total_chunks_result = (await db.execute(
                select(DocumentChunk.id).where(DocumentChunk.user_id == current_user.id)
            ))
            total_chunks = total_chunks_result.scalars().all()

            return templates.TemplateResponse(request, "search/index.html", {
                "user": current_user,
                "page_title": "البحث الذكي",
                "current_page": "search",
                "lang": current_user.default_lang,
                "files_info": files_info,
                "indexed_count": indexed_count,
                "total_chunks": len(total_chunks),
            })
        
        # Re-raise if not a column error
        raise
