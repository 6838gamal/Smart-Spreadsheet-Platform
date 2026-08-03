"""Web authentication routes (login/register pages + Google OAuth)."""

import secrets
import logging
import time
import threading
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.templates import templates
from app.core.config import settings
from app.application.auth.dto import RegisterDTO, LoginDTO
from app.application.auth.service import AuthService
from app.core.security import create_access_token

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Google OAuth constants ────────────────────────────────────────────────────
_GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_INFO_URL  = "https://www.googleapis.com/oauth2/v3/userinfo"

# ── Server-side OAuth state store ─────────────────────────────────────────────
# Replaces cookie-based state: works even when Replit's preview resets cookies
# across desktop↔mobile mode switches or iframe boundaries.
_state_lock: threading.Lock = threading.Lock()
_oauth_states: dict[str, float] = {}   # state_token → expiry (unix timestamp)
_STATE_TTL = 600   # seconds (10 min — same as before)


def _store_oauth_state(state: str) -> None:
    """Persist state token server-side and purge expired entries."""
    now = time.time()
    with _state_lock:
        # Remove expired
        expired = [k for k, v in _oauth_states.items() if v < now]
        for k in expired:
            del _oauth_states[k]
        _oauth_states[state] = now + _STATE_TTL


def _consume_oauth_state(state: str) -> bool:
    """Verify and remove state. Returns True if valid."""
    if not state:
        return False
    now = time.time()
    with _state_lock:
        expiry = _oauth_states.pop(state, 0.0)
    return expiry > now

# ── Cookie helpers ────────────────────────────────────────────────────────────
_AUTH_COOKIE_OPTS = dict(
    httponly=True,
    max_age=60 * 60 * 24,   # 24 h
    samesite="none",
    secure=True,
    path="/",
)


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie("access_token", token, **_AUTH_COOKIE_OPTS)


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie("access_token", path="/", httponly=True, samesite="none", secure=True)


def _redirect_uri(request: Request) -> str:
    """Build the Google callback URL using the app's public base URL."""
    base = settings.public_url
    return f"{base}/auth/google/callback"


# ── Root ──────────────────────────────────────────────────────────────────────
@router.get("/", response_class=HTMLResponse)
async def root(request: Request):
    if request.cookies.get("access_token"):
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/auth/login", status_code=302)


# ── Login page ────────────────────────────────────────────────────────────────
@router.get("/auth/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = "", lang: str = "ar"):
    google_enabled = bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)
    return templates.TemplateResponse(
        request, "auth/login.html",
        {"error": error, "lang": lang, "google_enabled": google_enabled},
    )


# ── Admin login (email+password) via HTMX ─────────────────────────────────────
@router.post("/admin/login")
async def admin_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        svc = AuthService(db)
        result = await svc.login(LoginDTO(email=email, password=password))

        from app.infrastructure.repositories.user_repository import UserRepository
        from app.infrastructure.database.models import UserRole
        user = await UserRepository(db).get_by_email(email)
        if not user or user.role != UserRole.ADMIN:
            return templates.TemplateResponse(
                request, "auth/_admin_error.html",
                {"error": "هذا الحساب ليس حساب إدارة"},
                status_code=403,
            )

        token = result.access_token
        # Inject token into sessionStorage so the login page can recover the
        # session automatically if the cookie is dropped (e.g. Replit iframe
        # mobile-mode reload blocks third-party cookies).
        response = HTMLResponse(
            '<p class="text-green-400 text-sm text-center mt-2">جاري التحويل…</p>'
            f'<script>try{{sessionStorage.setItem("_ark","{token}")}}catch(e){{}}</script>',
            status_code=200,
        )
        response.headers["HX-Redirect"] = "/admin"
        _set_auth_cookie(response, token)
        return response
    except Exception as e:
        return templates.TemplateResponse(
            request, "auth/_admin_error.html",
            {"error": str(e)},
            status_code=400,
        )


# ── Google OAuth: step 1 — redirect to Google ─────────────────────────────────
@router.get("/auth/google")
async def google_redirect(request: Request):
    if not (settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET):
        return RedirectResponse("/auth/login?error=google_not_configured", status_code=302)

    state = secrets.token_urlsafe(32)
    _store_oauth_state(state)   # server-side; no cookie needed
    params = urlencode({
        "response_type": "code",
        "client_id":     settings.GOOGLE_CLIENT_ID,
        "redirect_uri":  _redirect_uri(request),
        "scope":         "openid email profile",
        "state":         state,
        "access_type":   "online",
        "prompt":        "select_account",
    })
    return RedirectResponse(f"{_GOOGLE_AUTH_URL}?{params}", status_code=302)


# ── Google OAuth: step 2 — callback ───────────────────────────────────────────
@router.get("/auth/google/callback")
async def google_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
    code: str = "",
    state: str = "",
    error: str = "",
):
    # Errors from Google (e.g. user denied)
    if error:
        return RedirectResponse(f"/auth/login?error={error}", status_code=302)

    # CSRF check — verified against server-side store (not a cookie)
    if not _consume_oauth_state(state):
        logger.warning("Google OAuth: invalid/expired state token received=%r", state)
        return RedirectResponse("/auth/login?error=state_mismatch", status_code=302)

    if not settings.EXTERNAL_APIS_ENABLED:
        return RedirectResponse("/auth/login?error=google_disabled", status_code=302)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Exchange code → access token
            tok_resp = await client.post(_GOOGLE_TOKEN_URL, data={
                "code":          code,
                "client_id":     settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri":  _redirect_uri(request),
                "grant_type":    "authorization_code",
            })
            tok_resp.raise_for_status()
            tokens = tok_resp.json()

            if "error" in tokens:
                raise ValueError(tokens.get("error_description", tokens["error"]))

            # Fetch user profile
            info_resp = await client.get(_GOOGLE_INFO_URL, headers={
                "Authorization": f"Bearer {tokens['access_token']}"
            })
            info_resp.raise_for_status()
            userinfo = info_resp.json()

        svc = AuthService(db)
        user = await svc.login_or_register_google(userinfo)
        jwt_token = create_access_token({"sub": str(user.id)})

        # Redirect through session-init so the token is saved to sessionStorage.
        # This lets the login page silently recover the session if the iframe
        # drops the cookie (e.g. Replit mobile-mode switch).
        response = RedirectResponse(url="/auth/session-init", status_code=302)
        _set_auth_cookie(response, jwt_token)
        return response

    except Exception as exc:
        logger.exception("Google OAuth callback error")
        return RedirectResponse(f"/auth/login?error={str(exc)[:80]}", status_code=302)


# ── Logout ────────────────────────────────────────────────────────────────────
@router.post("/auth/recover")
async def recover_session(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Re-establish the session cookie from an Authorization Bearer token.

    Used by the login page to recover a lost session (e.g. when the Replit
    preview iframe reloads in mobile mode and drops the SameSite=None cookie).
    The token is read from the Authorization header, validated, and a fresh
    cookie is set so the user is silently redirected back to /dashboard.
    """
    try:
        user = await get_current_user(request, db)
        token = create_access_token({"sub": str(user.id)})
        response = Response(content="ok", status_code=200)
        _set_auth_cookie(response, token)
        return response
    except Exception:
        return Response(content="unauthorized", status_code=401)


@router.get("/auth/session-init", response_class=HTMLResponse)
async def session_init(request: Request):
    """Bridge page: reads the httpOnly cookie server-side, stores the token in
    sessionStorage (so the login page can recover the session if the cookie is
    dropped by Replit's iframe), then redirects to /dashboard.

    Google OAuth redirects here instead of /dashboard directly.
    """
    token = request.cookies.get("access_token", "")
    if not token:
        return RedirectResponse("/auth/login", status_code=302)

    # Embed token safely — JWTs only contain base64url chars + dots, no quotes
    # or backslashes, so simple single-quote wrapping is safe here.
    html = (
        "<!DOCTYPE html><html><head><meta charset='UTF-8'/>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'/>"
        "</head><body>"
        "<script>"
        f"try{{sessionStorage.setItem('_ark','{token}');}}catch(e){{}}"
        "window.location.replace('/dashboard');"
        "</script>"
        "</body></html>"
    )
    return HTMLResponse(content=html)


@router.post("/auth/logout")
@router.get("/auth/logout")
async def logout():
    # Clear sessionStorage token via a tiny bridge page so the login page
    # doesn't silently re-authenticate the user after an intentional logout.
    html = (
        "<!DOCTYPE html><html><head><meta charset='UTF-8'/></head><body>"
        "<script>"
        "try{sessionStorage.removeItem('_ark');}catch(e){}"
        "window.location.replace('/auth/login?reason=logout');"
        "</script>"
        "</body></html>"
    )
    response = HTMLResponse(content=html, status_code=200)
    _clear_auth_cookie(response)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response
