"""Background task: analyze a file via the real pipeline, then index it.

Runs as a FastAPI BackgroundTask — no Celery required.
Uses the existing pipeline_manager.handle_analysis_job() for full analysis
(classify + OCR + tables + entities) and auto-indexing.
"""
from __future__ import annotations

import logging

from sqlalchemy import select, func

from app.core.database import AsyncSessionLocal
from app.infrastructure.database.models import File
from app.infrastructure.database.models_intelligence import (
    DocumentAnalysis,
    AnalysisStatus,
    DocumentChunk,
)
from app.services.search.search_service import search_service

logger = logging.getLogger(__name__)


async def analyze_and_index_background(file_id: int, user_id: int) -> None:
    """
    Full pipeline in background:
        1. Load file metadata
        2. Find or create a DocumentAnalysis record
        3. Call handle_analysis_job() — which does:
             - classify
             - run appropriate pipeline (OCR/tables/entities)
             - persist results
             - auto-index chunks
        4. Safety net: if analysis ran but no chunks, index manually
    """
    logger.info(f"🚀 [BG] Start analyze+index for file_id={file_id} user_id={user_id}")

    analysis_id: int | None = None

    try:
        # ═══════════════════════════════════════════════════════════
        # 1. Load file + find/create analysis record
        # ═══════════════════════════════════════════════════════════
        async with AsyncSessionLocal() as db:
            file = (await db.execute(
                select(File).where(File.id == file_id, File.owner_id == user_id)
            )).scalar_one_or_none()

            if not file:
                logger.warning(f"⚠️ [BG] File {file_id} not found")
                return

            # Reuse existing analysis if it exists and is not stale
            analysis = (await db.execute(
                select(DocumentAnalysis)
                .where(DocumentAnalysis.file_id == file_id)
                .order_by(DocumentAnalysis.id.desc())
                .limit(1)
            )).scalar_one_or_none()

            # If we already have a COMPLETED analysis with raw_text,
            # just verify chunks and exit.
            if (
                analysis
                and analysis.status == AnalysisStatus.COMPLETED
                and analysis.raw_text
            ):
                chunks_count = await _count_chunks(db, file_id, user_id)
                if chunks_count > 0:
                    logger.info(
                        f"✅ [BG] File {file_id} already analyzed & indexed "
                        f"({chunks_count} chunks). Skipping."
                    )
                    return
                else:
                    # Analysis done, but no chunks → index only
                    logger.info(
                        f"📇 [BG] File {file_id} analyzed but not indexed. "
                        f"Indexing only..."
                    )
                    analysis_id = analysis.id
                    await _index_only(db, file, analysis, user_id)
                    return

            # Otherwise, create a fresh analysis record
            analysis = DocumentAnalysis(
                file_id=file_id,
                user_id=user_id,
                status=AnalysisStatus.PENDING,
            )
            db.add(analysis)
            await db.commit()
            await db.refresh(analysis)

            analysis_id = analysis.id
            logger.info(f"📝 [BG] Created DocumentAnalysis #{analysis_id}")

            file_path = file.path
            file_format = file.format

        # ═══════════════════════════════════════════════════════════
        # 2. Call handle_analysis_job (the real pipeline)
        #    — This runs the full analysis + auto-index inside.
        # ═══════════════════════════════════════════════════════════
        from app.services.pipeline.pipeline_manager import handle_analysis_job

        payload = {
            "file_id": file_id,
            "file_path": file_path,
            "file_format": file_format,
            "analysis_id": analysis_id,
        }

        try:
            result = await handle_analysis_job(payload)
            logger.info(
                f"🎉 [BG] handle_analysis_job completed for file {file_id}: "
                f"{result}"
            )
        except Exception as e:
            logger.exception(
                f"❌ [BG] handle_analysis_job failed for file {file_id}: {e}"
            )
            # The handler already marks the analysis as FAILED in DB.
            return

        # ═══════════════════════════════════════════════════════════
        # 3. Safety net — if analysis completed but no chunks were
        #    created (e.g., indexing step in handler failed silently),
        #    index here.
        # ═══════════════════════════════════════════════════════════
        async with AsyncSessionLocal() as db:
            file = (await db.execute(
                select(File).where(File.id == file_id)
            )).scalar_one_or_none()

            analysis = (await db.execute(
                select(DocumentAnalysis)
                .where(DocumentAnalysis.id == analysis_id)
            )).scalar_one_or_none()

            if not file or not analysis:
                return

            chunks_count = await _count_chunks(db, file_id, user_id)

            if chunks_count == 0 and analysis.raw_text:
                logger.warning(
                    f"⚠️ [BG] Analysis #{analysis_id} completed but no chunks. "
                    f"Running fallback indexing..."
                )
                await _index_only(db, file, analysis, user_id)
            else:
                logger.info(
                    f"✅ [BG] File {file_id} complete: {chunks_count} chunks in DB"
                )

    except Exception as e:
        logger.exception(f"❌ [BG] analyze_and_index failed for {file_id}: {e}")


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _count_chunks(db, file_id: int, user_id: int) -> int:
    """Count chunks for a given file/user."""
    return (await db.execute(
        select(func.count(DocumentChunk.id)).where(
            DocumentChunk.file_id == file_id,
            DocumentChunk.user_id == user_id,
        )
    )).scalar() or 0


async def _index_only(db, file, analysis, user_id: int) -> None:
    """Index the analysis text only (analysis already exists)."""
    try:
        if not analysis.raw_text:
            logger.warning(f"⚠️ [BG] Analysis #{analysis.id} has no raw_text — cannot index")
            return

        chunk_count = await search_service.index_document(
            db,
            file_id=file.id,
            analysis_id=analysis.id,
            user_id=user_id,
            text=analysis.raw_text,
            doc_type=getattr(analysis, "doc_type", None),
            language=getattr(analysis, "language", None),
            filename=file.original_name,
        )
        logger.info(f"✅ [BG] Indexed {chunk_count} chunks for file {file.id}")
    except Exception as e:
        logger.exception(f"❌ [BG] Indexing failed for file {file.id}: {e}")
        raise
