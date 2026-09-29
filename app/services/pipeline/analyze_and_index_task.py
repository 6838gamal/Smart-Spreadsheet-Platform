"""Background task: analyze a file, then index it for search.

Runs as a FastAPI BackgroundTask — no Celery required.
Idempotent: safe to call multiple times on the same file.
"""
from __future__ import annotations

import logging

from sqlalchemy import select

from app.core.database import async_session_maker
from app.infrastructure.database.models import File
from app.infrastructure.database.models_intelligence import (
    DocumentAnalysis,
    AnalysisStatus,
)
from app.services.search.search_service import search_service

logger = logging.getLogger(__name__)


async def analyze_and_index_background(file_id: int, user_id: int) -> None:
    """
    Full pipeline in background:
        1. Load file
        2. Try existing analysis, or run a new one
        3. Index the analyzed text
    """
    logger.info(f"🚀 [BG] Start analyze+index for file_id={file_id} user_id={user_id}")

    try:
        async with async_session_maker() as db:
            # ── 1. Load file ──
            file = (await db.execute(
                select(File).where(File.id == file_id, File.owner_id == user_id)
            )).scalar_one_or_none()

            if not file:
                logger.warning(f"⚠️ [BG] File {file_id} not found")
                return

            # ── 2. Check for existing completed analysis ──
            analysis = (await db.execute(
                select(DocumentAnalysis)
                .where(
                    DocumentAnalysis.file_id == file_id,
                    DocumentAnalysis.status == AnalysisStatus.COMPLETED,
                )
                .order_by(DocumentAnalysis.id.desc())
                .limit(1)
            )).scalar_one_or_none()

            # ── 3. Run analysis if none exists ──
            if not analysis or not analysis.raw_text:
                logger.info(f"🔍 [BG] Analyzing file {file_id} ({file.original_name})...")

                try:
                    # ── استخدم الاستخراج السريع كحل مؤقت ──
                    # إذا كان لديك دالة تحليل متقدمة، استبدلها هنا
                    from app.services.pipeline.pipeline_manager import _quick_text

                    text = _quick_text(file.path, file.format)
                    if not text or not text.strip():
                        logger.warning(f"⚠️ [BG] No text extracted from file {file_id}")
                        return

                    # أنشئ سجل تحليل
                    analysis = DocumentAnalysis(
                        file_id=file_id,
                        user_id=user_id,
                        status=AnalysisStatus.COMPLETED,
                        raw_text=text,
                    )
                    db.add(analysis)
                    await db.commit()
                    await db.refresh(analysis)
                    logger.info(f"✅ [BG] Created analysis {analysis.id} ({len(text)} chars)")

                except Exception as e:
                    logger.exception(f"❌ [BG] Analysis failed for file {file_id}: {e}")
                    # سجّل الفشل إن أمكن
                    try:
                        failed = DocumentAnalysis(
                            file_id=file_id,
                            user_id=user_id,
                            status=AnalysisStatus.FAILED,
                        )
                        # حاول إضافة error_message إذا كان الحقل موجوداً
                        if hasattr(failed, "error_message"):
                            failed.error_message = str(e)[:500]
                        db.add(failed)
                        await db.commit()
                    except Exception:
                        pass
                    return

            if not analysis.raw_text or not analysis.raw_text.strip():
                logger.warning(f"⚠️ [BG] Analysis has no text for file {file_id}")
                return

            # ── 4. Index the analyzed text ──
            logger.info(f"📇 [BG] Indexing file {file_id}...")
            chunk_count = await search_service.index_document(
                db,
                file_id=file_id,
                analysis_id=analysis.id,
                user_id=user_id,
                text=analysis.raw_text,
                doc_type=getattr(analysis, "doc_type", None),
                language=getattr(analysis, "language", None),
                filename=file.original_name,
            )

            logger.info(
                f"🎉 [BG] Complete: file_id={file_id} → {chunk_count} chunks indexed"
            )

    except Exception as e:
        logger.exception(f"❌ [BG] analyze+index failed for {file_id}: {e}")
