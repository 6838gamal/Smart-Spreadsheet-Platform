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
from app.infrastructure.database.models_intelligence import DocumentChunk, AIModelRegistry

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


async def ensure_model_table_columns(db: AsyncSession) -> bool:
    """Ensure required columns exist in ai_model_registry table."""
    try:
        # Check if hf_model_id column exists
        result = await db.execute(text("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name = 'ai_model_registry' 
                AND column_name = 'hf_model_id'
            )
        """))
        exists = result.scalar()
        
        if not exists:
            logger.warning("Model table columns missing, adding them now...")
            columns = [
                ("task_type", "VARCHAR(50) DEFAULT 'text-generation'"),
                ("visible_to_users", "BOOLEAN DEFAULT TRUE"),
                ("hf_model_id", "VARCHAR(200)"),
                ("languages", "JSONB DEFAULT '[]'::jsonb"),
                ("description", "TEXT"),
            ]
            
            for col_name, col_type in columns:
                await db.execute(text(
                    f"ALTER TABLE ai_model_registry "
                    f"ADD COLUMN IF NOT EXISTS {col_name} {col_type};"
                ))
                logger.info(f"✅ Column '{col_name}' added to ai_model_registry")
            
            # Create index
            await db.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_ai_model_registry_task_type "
                "ON ai_model_registry (task_type);"
            ))
            
            await db.commit()
            logger.info("✅ Model table columns added successfully")
            return True
            
        return False
        
    except Exception as e:
        logger.error(f"Error ensuring model table columns: {e}")
        await db.rollback()
        return False


@router.get("/search", response_class=HTMLResponse)
async def search_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Render the Smart Search / Document Q&A page."""
    # Ensure all required columns exist
    await ensure_storage_columns(db)
    await ensure_model_table_columns(db)
    
    try:
        # ── 1. Get indexed files ──
        indexed_file_ids_rows = (await db.execute(
            select(DocumentChunk.file_id).where(
                DocumentChunk.user_id == current_user.id
            ).distinct()
        )).scalars().all()
        indexed_ids = set(indexed_file_ids_rows)

        # ── 2. Get all user files ──
        all_files_rows = (await db.execute(
            select(File).where(File.owner_id == current_user.id).order_by(File.created_at.desc())
        )).scalars().all()

        files_info = [
            {
                "id": f.id,
                "original_name": f.original_name or f.name,
                "file_format": f.format,
                "is_indexed": f.id in indexed_ids,
                "size_bytes": f.size_bytes,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in all_files_rows
        ]

        indexed_count = len(indexed_ids)
        total_chunks_result = (await db.execute(
            select(DocumentChunk.id).where(DocumentChunk.user_id == current_user.id)
        ))
        total_chunks = total_chunks_result.scalars().all()

        # ── 3. Get available AI models ──
        models_result = await db.execute(
            select(AIModelRegistry).where(
                AIModelRegistry.source == "huggingface",
                AIModelRegistry.is_active == True,
                AIModelRegistry.visible_to_users == True,
            ).order_by(AIModelRegistry.is_default.desc(), AIModelRegistry.name)
        )
        models = models_result.scalars().all()

        models_data = [
            {
                "id": m.id,
                "name": m.name,
                "task_type": m.task_type or "text-generation",
                "hf_model_id": m.hf_model_id,
                "is_default": m.is_default,
                "description": m.description,
                "languages": m.languages or [],
            }
            for m in models
        ]

        # ── 4. Get default model ID ──
        default_model = next((m for m in models if m.is_default), models[0] if models else None)
        default_model_id = default_model.id if default_model else None

        # ── 5. Check if HF token is configured ──
        from app.core.config import settings
        hf_configured = bool(settings.HUGGINGFACE_TOKEN)

        # ── 6. Render template ──
        return templates.TemplateResponse(request, "search/index.html", {
            "user": current_user,
            "page_title": "البحث الذكي",
            "current_page": "search",
            "lang": current_user.default_lang if hasattr(current_user, 'default_lang') else "ar",
            
            # File data
            "files_info": files_info,
            "indexed_count": indexed_count,
            "total_chunks": len(total_chunks),
            
            # Model data
            "models": models_data,
            "default_model_id": default_model_id,
            "hf_configured": hf_configured,
            
            # Additional context
            "has_files": len(files_info) > 0,
            "has_indexed_files": indexed_count > 0,
        })
        
    except Exception as e:
        logger.error(f"Error in search_page: {e}")
        error_msg = str(e).lower()
        
        # Check if it's a column missing error
        if "column" in error_msg and "does not exist" in error_msg:
            logger.warning("Column error detected, attempting recovery...")
            await ensure_storage_columns(db)
            await ensure_model_table_columns(db)
            
            # Retry the query with recovery
            try:
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
                        "original_name": f.original_name or f.name,
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

                # Get models
                models_result = await db.execute(
                    select(AIModelRegistry).where(
                        AIModelRegistry.source == "huggingface",
                        AIModelRegistry.is_active == True,
                        AIModelRegistry.visible_to_users == True,
                    ).order_by(AIModelRegistry.is_default.desc())
                )
                models = models_result.scalars().all()
                models_data = [
                    {
                        "id": m.id,
                        "name": m.name,
                        "task_type": m.task_type or "text-generation",
                        "hf_model_id": m.hf_model_id,
                        "is_default": m.is_default,
                    }
                    for m in models
                ]
                default_model = next((m for m in models if m.is_default), models[0] if models else None)
                default_model_id = default_model.id if default_model else None

                from app.core.config import settings
                hf_configured = bool(settings.HUGGINGFACE_TOKEN)

                return templates.TemplateResponse(request, "search/index.html", {
                    "user": current_user,
                    "page_title": "البحث الذكي",
                    "current_page": "search",
                    "lang": "ar",
                    "files_info": files_info,
                    "indexed_count": indexed_count,
                    "total_chunks": len(total_chunks),
                    "models": models_data,
                    "default_model_id": default_model_id,
                    "hf_configured": hf_configured,
                    "has_files": len(files_info) > 0,
                    "has_indexed_files": indexed_count > 0,
                })
            except Exception as retry_error:
                logger.error(f"Retry also failed: {retry_error}")
                # Return a minimal page with error
                return templates.TemplateResponse(request, "search/index.html", {
                    "user": current_user,
                    "page_title": "البحث الذكي (خطأ)",
                    "current_page": "search",
                    "lang": "ar",
                    "files_info": [],
                    "indexed_count": 0,
                    "total_chunks": 0,
                    "models": [],
                    "default_model_id": None,
                    "hf_configured": False,
                    "has_files": False,
                    "has_indexed_files": False,
                    "error": "حدث خطأ في تحميل البيانات. يرجى تحديث الصفحة.",
                })
        
        # If it's a different error, re-raise
        raise


@router.get("/search/models")
async def get_search_models(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    API endpoint to get available models for the search page.
    This is used by the frontend to populate the model dropdown.
    """
    models_result = await db.execute(
        select(AIModelRegistry).where(
            AIModelRegistry.source == "huggingface",
            AIModelRegistry.is_active == True,
            AIModelRegistry.visible_to_users == True,
        ).order_by(AIModelRegistry.is_default.desc(), AIModelRegistry.name)
    )
    models = models_result.scalars().all()
    
    return {
        "models": [
            {
                "id": m.id,
                "name": m.name,
                "task_type": m.task_type or "text-generation",
                "hf_model_id": m.hf_model_id,
                "is_default": m.is_default,
            }
            for m in models
        ],
        "default_model_id": next((m.id for m in models if m.is_default), models[0].id if models else None),
    }
