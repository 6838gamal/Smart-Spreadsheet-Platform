"""Background task: analyze a file via the real pipeline, then index it.

Runs as a FastAPI BackgroundTask — no Celery required.
Uses the existing pipeline_manager.handle_analysis_job() for full analysis
(classify + OCR + tables + entities) and indexing.

Pipeline stages:
    Stage 1 (analyzing): handle_analysis_job() → DocumentAnalysis.status = COMPLETED
    Stage 2 (indexing):  search_service.index_document() → DocumentChunk rows

The frontend sees via /status:
    pending → analyzing → indexing → ready

✨ تحديث: تتبع التقدم الحقيقي (progress tracking) عبر تحديث DocumentAnalysis
         دوريًا من callback يُمرَّر إلى search_service.index_document.
         + إصلاح _mark_analysis_failed لتغيير status إلى FAILED فعليًا.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select, func

from app.core.database import AsyncSessionLocal
from app.infrastructure.database.models import File, utcnow
from app.infrastructure.database.models_intelligence import (
    DocumentAnalysis,
    AnalysisStatus,
    DocumentChunk,
)
from app.services.search.search_service import search_service

logger = logging.getLogger(__name__)

# ⏱️ Timeouts (seconds)
ANALYSIS_TIMEOUT = 300.0   # 5 دقائق للتحليل
INDEXING_TIMEOUT = 120.0   # 2 دقيقة للفهرسة

# ✨ عدد المقاطع بين كل تحديث تقدم في قاعدة البيانات
PROGRESS_UPDATE_EVERY = 5


async def analyze_and_index_background(file_id: int, user_id: int) -> None:
    """
    Full pipeline in background:
        1. Load file metadata
        2. Find or create a DocumentAnalysis record
        3. Stage 1 — Analysis via handle_analysis_job() (classify + OCR + persist)
        4. Stage 2 — Indexing via search_service.index_document()
        5. Safety net — if Stage 2 failed silently, retry indexing
    """
    logger.info(
        f"🚀 [BG] Start analyze+index for file_id={file_id} user_id={user_id}"
    )

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
                stage="analysis",           # ✨
                current_step="preparing",   # ✨
                progress_current=0,         # ✨
                progress_total=0,           # ✨
                progress_percent=0.0,       # ✨
                stage_started_at=utcnow(),  # ✨
                last_heartbeat_at=utcnow(), # ✨
            )
            db.add(analysis)
            await db.commit()
            await db.refresh(analysis)

            analysis_id = analysis.id
            logger.info(f"📝 [BG] Created DocumentAnalysis #{analysis_id}")

            file_path = file.path
            file_format = file.format

        # ═══════════════════════════════════════════════════════════
        # 2. Stage 1 — Analysis (handle_analysis_job) with timeout
        # ═══════════════════════════════════════════════════════════
        from app.services.pipeline.pipeline_manager import handle_analysis_job

        payload = {
            "file_id": file_id,
            "file_path": file_path,
            "file_format": file_format,
            "analysis_id": analysis_id,
        }

        try:
            logger.info(
                f"🔍 [BG] Stage 1 (analysis) started for file {file_id} "
                f"(timeout={ANALYSIS_TIMEOUT}s)"
            )
            # ✨ تحديث نبضة قبل البدء
            await _touch_heartbeat(analysis_id)

            result = await asyncio.wait_for(
                handle_analysis_job(payload),
                timeout=ANALYSIS_TIMEOUT,
            )
            logger.info(
                f"🎉 [BG] Stage 1 (analysis) completed for file {file_id}: "
                f"{result}"
            )
            # ✨ تحديث الحالة بعد التحليل
            await _update_analysis_stage(
                analysis_id,
                stage="indexing",
                step="preparing",
                heartbeat=True,
            )
        except asyncio.TimeoutError:
            logger.error(
                f"⏱️ [BG] Stage 1 TIMEOUT after {ANALYSIS_TIMEOUT}s "
                f"for file {file_id}"
            )
            await _mark_analysis_failed(
                analysis_id,
                f"analysis timed out after {int(ANALYSIS_TIMEOUT)}s",
            )
            return
        except Exception as e:
            logger.exception(
                f"❌ [BG] Stage 1 (analysis) failed for file {file_id}: {e}"
            )
            await _mark_analysis_failed(
                analysis_id,
                f"analysis failed: {str(e)[:400]}",
            )
            return

        # ═══════════════════════════════════════════════════════════
        # 3. Stage 2 — Indexing (search_service.index_document)
        # ═══════════════════════════════════════════════════════════
        await _run_stage_2_indexing(
            analysis_id=analysis_id,
            file_id=file_id,
            user_id=user_id,
        )

        logger.info(f"🏁 [BG] Full pipeline complete for file {file_id}")

    except Exception as e:
        logger.exception(f"❌ [BG] analyze_and_index failed for {file_id}: {e}")
        if analysis_id:
            await _mark_analysis_failed(
                analysis_id,
                f"pipeline crashed: {str(e)[:400]}",
            )


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
            # ✨ ضع علامة "done" لأن الفهرسة مكتملة
            await _update_analysis_stage(
                analysis_id,
                stage="done",
                step="done",
                heartbeat=True,
            )
            return

        # ── Guard: must have text ──
        if not analysis.raw_text or not analysis.raw_text.strip():
            logger.warning(
                f"⚠️ [BG] Stage 2 skipped — no raw_text for analysis #{analysis_id}"
            )
            # ✨ ضع علامة "done" لأن التحليل انتهى لكن لا نص للفهرسة
            await _update_analysis_stage(
                analysis_id,
                stage="done",
                step="done",
                heartbeat=True,
            )
            return

        # ═══════════════════════════════════════════════════════════
        # ✨ دالة callback لتحديث التقدم في DB
        # ═══════════════════════════════════════════════════════════
        async def update_progress(current: int, total: int, step: str) -> None:
            """تُستدعى من search_service.index_document دوريًا."""
            await _update_analysis_progress(
                analysis_id=analysis_id,
                stage="indexing",
                step=step,
                current=current,
                total=total,
            )

        # ── Run indexing with timeout ──
        try:
            logger.info(
                f"📇 [BG] Stage 2 (indexing) started for file {file_id} "
                f"({len(analysis.raw_text)} chars, timeout={INDEXING_TIMEOUT}s)"
            )

            # ✨ تحديث الحالة قبل البدء
            await _update_analysis_stage(
                analysis_id,
                stage="indexing",
                step="preparing",
                heartbeat=True,
            )

            chunk_count = await asyncio.wait_for(
                search_service.index_document(
                    db,
                    file_id=file_id,
                    analysis_id=analysis_id,
                    user_id=user_id,
                    text=analysis.raw_text,
                    doc_type=getattr(analysis, "doc_type", None),
                    language=getattr(analysis, "language", None),
                    filename=file.original_name,
                    on_progress=update_progress,           # ✨ جديد
                    progress_every=PROGRESS_UPDATE_EVERY,   # ✨ جديد
                ),
                timeout=INDEXING_TIMEOUT,
            )
            logger.info(
                f"🎉 [BG] Stage 2 (indexing) complete — "
                f"{chunk_count} chunks stored for file {file_id}"
            )

            # ✨ ضع علامة "done" عند النجاح
            await _update_analysis_stage(
                analysis_id,
                stage="done",
                step="done",
                heartbeat=True,
            )

        except asyncio.TimeoutError:
            logger.error(
                f"⏱️ [BG] Stage 2 TIMEOUT after {INDEXING_TIMEOUT}s "
                f"for file {file_id}"
            )
            await _mark_analysis_failed(
                analysis_id,
                f"indexing timed out after {int(INDEXING_TIMEOUT)}s",
            )
            raise

        except Exception as e:
            logger.exception(
                f"❌ [BG] Stage 2 (indexing) failed for file {file_id}: {e}"
            )
            await _mark_analysis_failed(
                analysis_id,
                f"indexing failed: {str(e)[:400]}",
            )
            raise


# ═══════════════════════════════════════════════════════════════════════════════
#  ✨ دوال مساعدة لتحديث التقدم في قاعدة البيانات
# ═══════════════════════════════════════════════════════════════════════════════

async def _update_analysis_progress(
    analysis_id: int,
    *,
    stage: str,
    step: str,
    current: int,
    total: int,
) -> None:
    """
    ✨ تحديث حقول التقدم في DocumentAnalysis بجلسة جديدة.
    آمن — أي استثناء لا يُفشل الفهرسة.
    """
    try:
        async with AsyncSessionLocal() as db:
            analysis = await db.get(DocumentAnalysis, analysis_id)
            if not analysis:
                return

            analysis.stage = stage
            analysis.current_step = step
            analysis.progress_current = current
            analysis.progress_total = total
            analysis.progress_percent = (
                round(current / total * 100, 2) if total > 0 else 0.0
            )
            analysis.last_heartbeat_at = utcnow()

            # إذا كانت خطوة البداية، سجّل وقت بدء المرحلة
            if step == "preparing" and current == 0:
                analysis.stage_started_at = utcnow()

            await db.commit()

    except Exception as e:
        logger.warning(
            f"⚠️ [BG] Could not update progress for #{analysis_id} "
            f"(step={step}, {current}/{total}): {e}"
        )


async def _update_analysis_stage(
    analysis_id: int,
    *,
    stage: str,
    step: str,
    heartbeat: bool = False,
) -> None:
    """
    ✨ تحديث مرحلة/خطوة DocumentAnalysis (بدون تغيير progress counts).
    """
    try:
        async with AsyncSessionLocal() as db:
            analysis = await db.get(DocumentAnalysis, analysis_id)
            if not analysis:
                return

            analysis.stage = stage
            analysis.current_step = step
            if heartbeat:
                analysis.last_heartbeat_at = utcnow()

            # إذا كانت المرحلة "done"، اضبط النسبة إلى 100
            if stage == "done":
                analysis.progress_percent = 100.0
                if analysis.progress_total > 0:
                    analysis.progress_current = analysis.progress_total

            await db.commit()

    except Exception as e:
        logger.warning(
            f"⚠️ [BG] Could not update stage for #{analysis_id}: {e}"
        )


async def _touch_heartbeat(analysis_id: int) -> None:
    """✨ تحديث نبضة فقط — لتفادي كشف المهمة كمعلقة أثناء التحليل."""
    try:
        async with AsyncSessionLocal() as db:
            analysis = await db.get(DocumentAnalysis, analysis_id)
            if analysis:
                analysis.last_heartbeat_at = utcnow()
                await db.commit()
    except Exception as e:
        logger.warning(f"⚠️ [BG] Could not touch heartbeat for #{analysis_id}: {e}")


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _count_chunks(db, file_id: int, user_id: int) -> int:
    """Count chunks for a given file/user."""
    return (await db.execute(
        select(func.count(DocumentChunk.id)).where(
            DocumentChunk.file_id == file_id,
            DocumentChunk.user_id == user_id,
        )
    )).scalar() or 0


async def _mark_analysis_failed(analysis_id: int, error_msg: str) -> None:
    """
    Safely mark an analysis as FAILED in a fresh session.

    ✨ يُغيّر status إلى FAILED + stage إلى 'failed' + يسجّل الخطأ.
    """
    try:
        async with AsyncSessionLocal() as db:
            analysis = await db.get(DocumentAnalysis, analysis_id)
            if analysis:
                # ✨ إصلاح جوهري: غيّر status إلى FAILED
                analysis.status = AnalysisStatus.FAILED
                analysis.stage = "failed"
                analysis.current_step = "failed"
                analysis.error_message = error_msg[:500]
                analysis.last_heartbeat_at = utcnow()
                await db.commit()
                logger.info(
                    f"📝 [BG] Marked analysis #{analysis_id} as FAILED: "
                    f"{error_msg[:100]}"
                )
    except Exception as e:
        logger.warning(
            f"⚠️ [BG] Could not mark analysis #{analysis_id} as failed: {e}"
        )


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
