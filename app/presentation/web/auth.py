"""Web authentication routes (login/register pages)."""

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.application.auth.dto import RegisterDTO, LoginDTO
from app.application.auth.service import AuthService

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def root(request: Request):
    token = request.cookies.get("access_token")
    if token:
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/auth/login", status_code=302)


@router.get("/auth/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse(request, "auth/login.html", {"error": error})


@router.get("/auth/register", response_class=HTMLResponse)
async def register_page(request: Request, error: str = ""):
    return templates.TemplateResponse(request, "auth/register.html", {"error": error})


@router.post("/auth/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        svc = AuthService(db)
        result = await svc.login(LoginDTO(email=email, password=password))
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie(
            "access_token",
            result.access_token,
            httponly=True,
            max_age=60 * 60 * 24,
            samesite="lax",
        )
        return response
    except Exception as e:
        return templates.TemplateResponse(
            request, "auth/login.html", {"error": str(e)}, status_code=400,
        )


@router.post("/auth/register")
async def register_submit(
    request: Request,
    email: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        svc = AuthService(db)
        dto = RegisterDTO(
            email=email,
            username=username,
            password=password,
            confirm_password=confirm_password,
        )
        user = await svc.register(dto)
        from app.core.security import create_access_token
        token = create_access_token({"sub": str(user.id)})
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie("access_token", token, httponly=True, max_age=60 * 60 * 24, samesite="lax")
        return response
    except Exception as e:
        return templates.TemplateResponse(
            request, "auth/register.html", {"error": str(e)}, status_code=400,
        )


@router.post("/auth/logout")
@router.get("/auth/logout")
async def logout():
    response = RedirectResponse(url="/auth/login", status_code=302)
    response.delete_cookie("access_token")
    return response
