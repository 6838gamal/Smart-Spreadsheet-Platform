"""Background task: analyze a file via the real pipeline, then index it.

Runs as a FastAPI BackgroundTask — no Celery required.
Uses the existing pipeline_manager.handle_analysis_job() for full analysis
(classify + OCR + tables + entities) and indexing.

Pipeline stages:
    Stage 1 (analyzing): handle_analysis_job() → DocumentAnalysis.status = COMPLETED
    Stage 2 (indexing):  search_service.index_document() → DocumentChunk rows

The frontend sees via /status:
    pending → analyzing → indexing → ready
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
        3. Stage 1 — Analysis via handle_analysis_job() (classify + OCR + persist)
        4. Stage 2 — Indexing via search_service.index_document()
        5. Safety net — if Stage 2 failed silently, retry indexing
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

            analysis = (await db.execute(
                select(DocumentAnalysis)
                .where(DocumentAnalysis.file_id == file_id)
                .order_by(DocumentAnalysis.id.desc())
                .limit(1)
            )).scalar_one_or_none()

            # ── Case A: already analyzed & indexed ──
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
                # ── Case B: analyzed but not indexed → skip to Stage 2 ──
                logger.info(
                    f"📇 [BG] File {file_id} analyzed but not indexed. "
                    f"Skipping Stage 1, going directly to indexing..."
                )
                analysis_id = analysis.id
                file_path = file.path
                file_format = file.format
                await _run_stage_2_indexing(
                    analysis_id=analysis_id,
                    file_id=file_id,
                    user_id=user_id,
                )
                return

            # ── Case C: fresh analysis needed ──
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
        # 2. Stage 1 — Analysis (handle_analysis_job)
        #    The handler does classify + OCR + tables + entities.
        #    NOTE: It no longer auto-indexes (removed in pipeline_manager).
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
                f"🎉 [BG] Stage 1 (analysis) completed for file {file_id}: "
                f"{result}"
            )
        except Exception as e:
            logger.exception(
                f"❌ [BG] Stage 1 (analysis) failed for file {file_id}: {e}"
            )
            return

        # ═══════════════════════════════════════════════════════════
        # 3. Stage 2 — Indexing (search_service.index_document)
        #    This is what the frontend displays as the "indexing" bar.
        # ═══════════════════════════════════════════════════════════
        await _run_stage_2_indexing(
            analysis_id=analysis_id,
            file_id=file_id,
            user_id=user_id,
        )

        logger.info(f"🏁 [BG] Full pipeline complete for file {file_id}")

    except Exception as e:
        logger.exception(f"❌ [BG] analyze_and_index failed for {file_id}: {e}")


# ── Stage 2: Indexing ─────────────────────────────────────────────────────────

async def _run_stage_2_indexing(
    analysis_id: int,
    file_id: int,
    user_id: int,
) -> None:
    """
    Stage 2 — index the analysis text into DocumentChunk.

    This is a separate function so it can be called directly when:
      - Stage 1 produced fresh text (normal flow)
      - Analysis already existed but wasn't indexed (Case B)
      - Safety net after Stage 1 (idempotent)
    """
    async with AsyncSessionLocal() as db:
        file = await db.get(File, file_id)
        analysis = await db.get(DocumentAnalysis, analysis_id)

        if not file or not analysis:
            logger.warning(
                f"⚠️ [BG] Stage 2 skipped — file or analysis missing "
                f"(file={file_id}, analysis={analysis_id})"
            )
            return

        # ── Idempotency: skip if chunks already exist ──
        chunks_count = await _count_chunks(db, file_id, user_id)
        if chunks_count > 0:
            logger.info(
                f"✅ [BG] Stage 2 skipped — {chunks_count} chunks already in DB"
            )
            return

        # ── Guard: must have text ──
        if not analysis.raw_text or not analysis.raw_text.strip():
            logger.warning(
                f"⚠️ [BG] Stage 2 skipped — no raw_text for analysis #{analysis_id}"
            )
            return

        # ── Run indexing ──
        try:
            logger.info(
                f"📇 [BG] Stage 2 (indexing) started for file {file_id} "
                f"({len(analysis.raw_text)} chars)"
            )
            chunk_count = await search_service.index_document(
                db,
                file_id=file_id,
                analysis_id=analysis_id,
                user_id=user_id,
                text=analysis.raw_text,
                doc_type=getattr(analysis, "doc_type", None),
                language=getattr(analysis, "language", None),
                filename=file.original_name,
            )
            logger.info(
                f"🎉 [BG] Stage 2 (indexing) complete — "
                f"{chunk_count} chunks stored for file {file_id}"
            )
        except Exception as e:
            logger.exception(
                f"❌ [BG] Stage 2 (indexing) failed for file {file_id}: {e}"
            )
            # Store the error so the UI can display it
            try:
                analysis.error_message = f"indexing failed: {str(e)[:400]}"
                await db.commit()
            except Exception:
                pass
            raise


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
    """Legacy helper — kept for backward compatibility.

    Prefer _run_stage_2_indexing() which opens its own session.
    """
    try:
        if not analysis.raw_text:
            logger.warning(
                f"⚠️ [BG] Analysis #{analysis.id} has no raw_text — cannot index"
            )
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
