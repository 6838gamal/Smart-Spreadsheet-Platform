"""Admin panel web routes — accessible only to ADMIN role users."""

import logging
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import verify_password, create_access_token
from app.core.templates import templates
from app.infrastructure.database.models import User, UserRole, File, OperationLog, ServerPing
from app.infrastructure.repositories.user_repository import UserRepository
from app.infrastructure.repositories.server_ping_repository import ServerPingRepository
from app.presentation.web.auth import _set_auth_cookie, _clear_auth_cookie

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Dependency ──────────────────────────────────────────────────────────────

async def get_admin_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Require authenticated ADMIN user or redirect to login."""
    try:
        user = await get_current_user(request, db)
    except Exception:
        return RedirectResponse("/auth/login", status_code=302)
    if user.role != UserRole.ADMIN:
        return RedirectResponse("/dashboard", status_code=302)
    return user


# ── Admin Login ──────────────────────────────────────────────────────────────

@router.post("/admin/login")
async def admin_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Authenticate admin via the secret modal on the login page."""
    user_repo = UserRepository(db)
    user = await user_repo.get_by_email(email)

    is_htmx = request.headers.get("HX-Request")

    if not user or not verify_password(password, user.hashed_password):
        msg = "بيانات غير صحيحة" if not is_htmx else "بيانات غير صحيحة"
        if is_htmx:
            return HTMLResponse(
                f'<p class="text-red-400 text-sm text-center mt-2">{msg}</p>',
                status_code=401,
            )
        return RedirectResponse("/auth/login?error=invalid", status_code=302)

    if not user.is_active:
        if is_htmx:
            return HTMLResponse(
                '<p class="text-red-400 text-sm text-center mt-2">الحساب معطّل</p>',
                status_code=403,
            )
        return RedirectResponse("/auth/login?error=disabled", status_code=302)

    if user.role != UserRole.ADMIN:
        if is_htmx:
            return HTMLResponse(
                '<p class="text-red-400 text-sm text-center mt-2">ليس لديك صلاحية الوصول</p>',
                status_code=403,
            )
        return RedirectResponse("/auth/login?error=forbidden", status_code=302)

    token = create_access_token({"sub": str(user.id)})

    if is_htmx:
        response = HTMLResponse(
            '<p class="text-green-400 text-sm text-center mt-2">جاري التحويل…</p>'
        )
        _set_auth_cookie(response, token)
        response.headers["HX-Redirect"] = "/admin"
        return response

    response = RedirectResponse("/admin", status_code=302)
    _set_auth_cookie(response, token)
    return response


# ── Dashboard ────────────────────────────────────────────────────────────────

@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    if isinstance(admin, RedirectResponse):
        return admin

    # Aggregate stats
    total_users = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    active_users = (await db.execute(
        select(func.count()).select_from(User).where(User.is_active == True)
    )).scalar_one()
    total_files = (await db.execute(select(func.count()).select_from(File))).scalar_one()
    total_ops = (await db.execute(select(func.count()).select_from(OperationLog))).scalar_one()

    # All users with file count
    users_result = await db.execute(
        select(User).order_by(User.created_at.desc())
    )
    users = list(users_result.scalars().all())

    # Recent operations (last 20)
    ops_result = await db.execute(
        select(OperationLog).order_by(OperationLog.started_at.desc()).limit(20)
    )
    recent_ops = list(ops_result.scalars().all())

    # File counts per user (dict user_id -> count)
    file_counts_result = await db.execute(
        select(File.owner_id, func.count(File.id)).group_by(File.owner_id)
    )
    file_counts = {row[0]: row[1] for row in file_counts_result.all()}

    return templates.TemplateResponse(
        request,
        "admin/index.html",
        {
            "user": admin,
            "lang": admin.default_lang,
            "total_users": total_users,
            "active_users": active_users,
            "total_files": total_files,
            "total_ops": total_ops,
            "users": users,
            "recent_ops": recent_ops,
            "file_counts": file_counts,
            "UserRole": UserRole,
        },
    )


# ── Server Activity / Keep-Alive Ping ────────────────────────────────────────

@router.get("/admin/ping")
async def admin_ping(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """DB health-check used by the server-activity panel (keep-alive).
    Each call is persisted to server_pings so counters survive restarts.
    Always returns HTTP 200 so the browser fetch() never throws on errors.
    """
    import time as _time

    if isinstance(admin, RedirectResponse):
        return JSONResponse({"ok": False, "latency_ms": 0, "detail": "غير مصرّح"})

    ping_repo = ServerPingRepository(db)
    t0 = _time.perf_counter()
    try:
        await db.execute(select(func.now()))
        latency_ms = round((_time.perf_counter() - t0) * 1000)
        detail = "اتصال ناجح بقاعدة البيانات"
        await ping_repo.add_ping(ok=True, latency_ms=latency_ms, detail=detail)
        await db.commit()
        return JSONResponse({"ok": True, "latency_ms": latency_ms, "detail": detail})
    except Exception as exc:
        latency_ms = round((_time.perf_counter() - t0) * 1000)
        detail = str(exc)
        logger.warning("admin/ping: DB error — %s", exc)
        try:
            await ping_repo.add_ping(ok=False, latency_ms=latency_ms, detail=detail)
            await db.commit()
        except Exception:
            pass
        return JSONResponse({"ok": False, "latency_ms": latency_ms, "detail": detail})


@router.get("/admin/activity/history")
async def admin_activity_history(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Return aggregated ping stats + last 30 records from the DB.
    Used by the server-activity panel on init to restore persisted counters.
    """
    if isinstance(admin, RedirectResponse):
        return JSONResponse({"ok": False})

    ping_repo = ServerPingRepository(db)
    stats = await ping_repo.get_stats()
    history_rows = await ping_repo.get_history(limit=30)

    history = [
        {
            "ok": row.ok,
            "lat": row.latency_ms,
            "detail": row.detail,
            "time": row.pinged_at.isoformat(),
        }
        for row in history_rows
    ]

    # Derive last ping info from most-recent record
    last = history_rows[0] if history_rows else None

    return JSONResponse({
        "total_pings": stats["total_pings"],
        "total_fails": stats["total_fails"],
        "history": history,
        "last_ping_at": last.pinged_at.isoformat() if last else None,
        "last_latency_ms": last.latency_ms if last else None,
        "last_status": last.ok if last else None,
    })


# ── User Management ──────────────────────────────────────────────────────────

@router.post("/admin/users/{user_id}/toggle", response_class=HTMLResponse)
async def toggle_user_active(
    request: Request,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    if isinstance(admin, RedirectResponse):
        return admin
    if user_id == admin.id:
        return HTMLResponse('<span class="text-red-400 text-xs">لا يمكن تعطيل نفسك</span>')

    user_repo = UserRepository(db)
    target = await user_repo.get_by_id(user_id)
    if not target:
        return HTMLResponse('<span class="text-red-400 text-xs">مستخدم غير موجود</span>')

    await user_repo.update(target, is_active=not target.is_active)
    status_label = "مفعّل" if target.is_active else "معطّل"
    color = "emerald" if target.is_active else "red"
    return HTMLResponse(
        f'<span class="badge bg-{color}-100 text-{color}-700 dark:bg-{color}-900/40 dark:text-{color}-400">'
        f'{status_label}</span>'
        f'<script>location.reload()</script>'
    )


@router.post("/admin/users/{user_id}/role")
async def change_user_role(
    request: Request,
    user_id: int,
    role: str = Form(...),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    if isinstance(admin, RedirectResponse):
        return admin
    if user_id == admin.id:
        return HTMLResponse('<span class="text-red-400 text-xs">لا يمكن تغيير دورك</span>')

    user_repo = UserRepository(db)
    target = await user_repo.get_by_id(user_id)
    if not target:
        return HTMLResponse('<span class="text-red-400 text-xs">مستخدم غير موجود</span>')

    try:
        new_role = UserRole(role)
    except ValueError:
        return HTMLResponse('<span class="text-red-400 text-xs">دور غير صالح</span>')

    await user_repo.update(target, role=new_role)
    return RedirectResponse("/admin", status_code=302)


@router.post("/admin/users/{user_id}/delete")
async def delete_user(
    request: Request,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    if isinstance(admin, RedirectResponse):
        return admin
    if user_id == admin.id:
        return RedirectResponse("/admin?error=self_delete", status_code=302)

    user_repo = UserRepository(db)
    target = await user_repo.get_by_id(user_id)
    if target:
        await user_repo.delete(target)
        await db.commit()

    return RedirectResponse("/admin", status_code=302)
