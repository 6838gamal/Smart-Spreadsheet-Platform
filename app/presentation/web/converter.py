"""Converter web routes."""

import asyncio
import json
import time
import uuid
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, StreamingResponse
from app.core.templates import templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.infrastructure.database.models import User, OperationType, OperationStatus
from app.infrastructure.repositories.file_repository import FileRepository
from app.infrastructure.repositories.operation_repository import OperationRepository
from app.infrastructure.storage.local_storage import storage
from app.application.converter.service import ConverterService, EXPORT_FORMATS
from app.application.converter.engine import DataEngine, DIRECT_PAIRS
from app.application.converter.dto import ConvertRequestDTO

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Friendly error classifier ────────────────────────────────────────────────

def _friendly_error(raw: str) -> tuple[str, str]:
    """Return (title, detail) friendly Arabic messages for common errors."""
    r = raw.lower()
    if "unsupported format" in r or "unsupported" in r:
        return "صيغة غير مدعومة", "الصيغة المطلوبة غير مدعومة للتحويل. جرّب صيغة أخرى."
    if "not found" in r or "no such file" in r:
        return "الملف غير موجود", "لم يُعثر على الملف في المخزن. ربما تم حذفه."
    if "permission" in r or "authorization" in r:
        return "ليس لديك صلاحية", "هذا الملف لا ينتمي لحسابك."
    if "corrupt" in r or "invalid file" in r or "bad zip" in r or "zipfile" in r:
        return "الملف تالف أو غير صالح", "الملف الأصلي يبدو تالفًا أو غير مكتمل. حاول رفعه من جديد."
    if "memory" in r or "out of memory" in r:
        return "الملف كبير جداً", "الملف يتجاوز الذاكرة المتاحة. حاول بملف أصغر أو قسّمه."
    if "sheet" in r:
        return "ورقة عمل غير موجودة", "اسم ورقة العمل المدخل غير صحيح. تحقق من الاسم وأعد المحاولة."
    if "column" in r or "schema" in r or "dtype" in r:
        return "خطأ في البيانات", "البيانات لا تتوافق مع الصيغة المستهدفة. تحقق من هيكل الملف."
    if "timeout" in r:
        return "انتهت المهلة الزمنية", "استغرقت العملية وقتًا طويلاً جداً. حاول بملف أصغر."
    return "خطأ في التحويل", raw[:200] if raw else "حدث خطأ غير متوقع."


# ── Pages ────────────────────────────────────────────────────────────────────

@router.get("/converter", response_class=HTMLResponse)
async def converter_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file_repo = FileRepository(db)
    files = await file_repo.get_by_owner(current_user.id, limit=100)
    return templates.TemplateResponse(
        request,
        "converter/index.html",
        {
            "user": current_user,
            "files": files,
            "export_formats": EXPORT_FORMATS,
            "current_page": "converter",
            "lang": current_user.default_lang,
        },
    )


# ── Preview endpoint (HTMX fragment) ────────────────────────────────────────

@router.get("/converter/preview/{file_id}", response_class=HTMLResponse)
async def preview_file(
    file_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file_repo = FileRepository(db)
    f = await file_repo.get_by_id(file_id)
    if not f or f.owner_id != current_user.id:
        return HTMLResponse("")

    fmt = f.format.lower().lstrip(".")
    # Non-tabular formats — just show metadata card
    non_tabular = {"jpg", "jpeg", "png", "bmp", "gif", "webp", "svg", "pdf"}
    if fmt in non_tabular:
        return HTMLResponse(f"""
        <div class="p-4 bg-slate-50 dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700 text-sm text-slate-500 dark:text-slate-400 flex items-center gap-3">
          <svg class="w-6 h-6 flex-shrink-0 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
          </svg>
          <div>
            <p class="font-medium text-slate-700 dark:text-slate-300">{f.original_name}</p>
            <p class="text-xs mt-0.5">{f.size_human} · صيغة {fmt.upper()} — لا تتوفر معاينة جدولية لهذا النوع</p>
          </div>
        </div>""")

    loop = asyncio.get_event_loop()
    engine = DataEngine()
    try:
        data = await loop.run_in_executor(None, lambda: engine.preview(f.path, fmt, 8))
    except Exception as exc:
        return HTMLResponse(f"""
        <div class="p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700/50 rounded-xl text-sm text-amber-700 dark:text-amber-400">
          تعذّرت المعاينة: {exc}
        </div>""")

    if data.get("error"):
        return HTMLResponse(f"""
        <div class="p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700/50 rounded-xl text-sm text-amber-700 dark:text-amber-400">
          تعذّرت المعاينة: {data['error']}
        </div>""")

    cols = data["columns"]
    rows = data["rows"]
    total_rows = data["total_rows"]
    total_cols = data["total_cols"]

    if not cols:
        return HTMLResponse("""
        <div class="p-3 text-sm text-slate-400 text-center">الملف فارغ أو لا يحتوي بيانات</div>""")

    # Build header cells
    ths = "".join(
        f'<th class="px-3 py-2 text-start text-xs font-semibold text-slate-500 dark:text-slate-400 whitespace-nowrap border-b border-slate-200 dark:border-slate-700">{c}</th>'
        for c in cols
    )
    # Build data rows
    trs = ""
    for i, row in enumerate(rows):
        bg = "bg-white dark:bg-slate-800" if i % 2 == 0 else "bg-slate-50/60 dark:bg-slate-800/40"
        tds = ""
        for c in cols:
            cell = str(row.get(c, ""))
            short = cell[:60]
            tds += (
                f'<td class="px-3 py-1.5 text-xs text-slate-600 dark:text-slate-300'
                f' whitespace-nowrap max-w-[180px] truncate" title="{cell}">{short}</td>'
            )
        trs += f'<tr class="{bg}">{tds}</tr>'

    shown = len(rows)
    more_label = f"· يُعرض {shown} من {total_rows:,} صف" if total_rows > shown else f"· {total_rows:,} صف"

    return HTMLResponse(f"""
    <div class="space-y-2">
      <div class="flex items-center justify-between text-xs text-slate-400 dark:text-slate-500 px-0.5">
        <span class="font-medium text-slate-600 dark:text-slate-300">معاينة: {f.original_name}</span>
        <span>{total_cols} عمود {more_label}</span>
      </div>
      <div class="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700 max-h-52">
        <table class="w-full text-sm border-collapse">
          <thead class="bg-slate-50 dark:bg-slate-800/80 sticky top-0"><tr>{ths}</tr></thead>
          <tbody>{trs}</tbody>
        </table>
      </div>
    </div>""")


# ── SSE conversion stream ────────────────────────────────────────────────────

@router.get("/converter/convert-sse")
async def convert_sse(
    request: Request,
    file_id: int = Query(...),
    target_format: str = Query(...),
    sheet: str = Query(""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    def _sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    async def stream():
        loop = asyncio.get_event_loop()
        engine = DataEngine()
        file_repo = FileRepository(db)
        op_repo = OperationRepository(db)
        target_fmt = target_format.lower()

        yield _sse("progress", {"pct": 8, "step": "validation", "msg": "التحقق من البيانات…"})
        await asyncio.sleep(0)

        # --- Validate ---
        try:
            if target_fmt not in EXPORT_FORMATS:
                yield _sse("done", {"ok": False, "title": "صيغة غير مدعومة",
                                    "detail": f"الصيغة .{target_fmt} غير متاحة للتصدير."})
                return

            f = await file_repo.get_by_id(file_id)
            if not f:
                yield _sse("done", {"ok": False, "title": "الملف غير موجود",
                                    "detail": "لم يُعثر على الملف. ربما تم حذفه."})
                return
            if f.owner_id != current_user.id:
                yield _sse("done", {"ok": False, "title": "ليس لديك صلاحية",
                                    "detail": "هذا الملف لا ينتمي لحسابك."})
                return
        except Exception as exc:
            t, d = _friendly_error(str(exc))
            yield _sse("done", {"ok": False, "title": t, "detail": d})
            return

        src_fmt = f.format.lower().lstrip(".")
        is_direct = (src_fmt, target_fmt) in DIRECT_PAIRS

        # --- Log operation ---
        op = await op_repo.create(
            type=OperationType.CONVERT,
            user_id=current_user.id,
            file_id=f.id,
            input_path=f.path,
            params={"file_id": file_id, "target_format": target_fmt, "sheet": sheet},
        )
        t0 = time.time()

        # --- Read ---
        yield _sse("progress", {"pct": 28, "step": "reading", "msg": f"جاري قراءة {f.original_name}…"})
        await asyncio.sleep(0)

        try:
            if is_direct:
                df = None
            else:
                df = await loop.run_in_executor(
                    None,
                    lambda: engine.read(f.path, src_fmt, sheet=sheet or None),
                )
        except Exception as exc:
            t, d = _friendly_error(str(exc))
            duration_ms = int((time.time() - t0) * 1000)
            await op_repo.mark_complete(op, OperationStatus.FAILED, error=str(exc), duration_ms=duration_ms)
            yield _sse("done", {"ok": False, "title": t, "detail": d})
            return

        rows_count = df.shape[0] if df is not None else 0
        cols_count = df.shape[1] if df is not None else 0

        # --- Convert ---
        yield _sse("progress", {"pct": 62, "step": "converting",
                                 "msg": f"جاري التحويل إلى .{target_fmt.upper()}…"})
        await asyncio.sleep(0)

        stem = Path(f.original_name).stem
        out_name = f"{stem}_{uuid.uuid4().hex[:6]}.{target_fmt}"
        out_path = storage.get_output_path(current_user.id, out_name)

        try:
            if is_direct:
                actual_path = await loop.run_in_executor(
                    None,
                    lambda: engine.convert_direct(f.path, src_fmt, str(out_path), target_fmt),
                )
                actual_name = Path(actual_path).name
            else:
                await loop.run_in_executor(None, lambda: engine.write(df, str(out_path), target_fmt))
                actual_path = str(out_path)
                actual_name = out_name
        except Exception as exc:
            t, d = _friendly_error(str(exc))
            duration_ms = int((time.time() - t0) * 1000)
            await op_repo.mark_complete(op, OperationStatus.FAILED, error=str(exc), duration_ms=duration_ms)
            yield _sse("done", {"ok": False, "title": t, "detail": d})
            return

        # --- Save & finish ---
        yield _sse("progress", {"pct": 90, "step": "saving", "msg": "جاري حفظ الملف الناتج…"})
        await asyncio.sleep(0)

        duration_ms = int((time.time() - t0) * 1000)
        await op_repo.mark_complete(
            op, OperationStatus.SUCCESS,
            result={"rows": rows_count, "columns": cols_count, "output": actual_path},
            output_path=actual_path,
            duration_ms=duration_ms,
        )

        yield _sse("done", {
            "ok": True,
            "filename": actual_name,
            "rows": rows_count,
            "cols": cols_count,
            "duration_ms": duration_ms,
            "src_name": f.original_name,
            "target_fmt": target_fmt.upper(),
        })

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Legacy POST (non-JS fallback) ────────────────────────────────────────────

@router.post("/converter/convert")
async def do_convert(
    request: Request,
    file_id: int = Form(...),
    target_format: str = Form(...),
    sheet: str = Form(""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        svc = ConverterService(db)
        result = await svc.convert(
            ConvertRequestDTO(file_id=file_id, target_format=target_format, sheet=sheet or None),
            current_user.id,
        )
        if request.headers.get("HX-Request"):
            return HTMLResponse(f"""
            <div class="p-4 bg-green-900/40 border border-green-500/30 rounded-xl text-green-300">
                <p class="font-semibold mb-2">✓ تم التحويل بنجاح</p>
                <p class="text-sm mb-3">{result.rows:,} صف × {result.columns} عمود · {result.duration_ms}ms</p>
                <a href="/converter/download/{result.output_filename}"
                   class="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-white text-sm font-medium">
                   تحميل {result.output_filename}
                </a>
            </div>""")
        return RedirectResponse(url="/converter", status_code=302)
    except Exception as e:
        if request.headers.get("HX-Request"):
            return HTMLResponse(
                f'<div class="p-4 bg-red-900/40 border border-red-500/30 rounded-xl text-red-300">خطأ: {e}</div>',
                status_code=400,
            )
        return RedirectResponse(url="/converter", status_code=302)


# ── Download ─────────────────────────────────────────────────────────────────

@router.get("/converter/download/{filename}")
async def download_converted(
    filename: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.core.config import settings
    path = Path(settings.OUTPUT_DIR) / str(current_user.id) / filename
    if not path.exists():
        return RedirectResponse(url="/converter", status_code=302)
    return FileResponse(str(path), filename=filename)
