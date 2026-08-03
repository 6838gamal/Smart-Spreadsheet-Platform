"""Auth API endpoints."""

import httpx
from fastapi import APIRouter, Response, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token
from app.application.auth.dto import RegisterDTO, LoginDTO, TokenResponseDTO
from app.application.auth.service import AuthService
from app.core.exceptions import ValidationError, AuthenticationError

router = APIRouter()

_GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
_GOOGLE_USERINFO_URL  = "https://www.googleapis.com/oauth2/v3/userinfo"


@router.post("/register", response_model=TokenResponseDTO)
async def register(dto: RegisterDTO, db: AsyncSession = Depends(get_db)):
    svc = AuthService(db)
    user = await svc.register(dto)
    token = create_access_token({"sub": str(user.id)})
    return TokenResponseDTO(access_token=token, user_id=user.id, username=user.username)


@router.post("/login", response_model=TokenResponseDTO)
async def login(dto: LoginDTO, db: AsyncSession = Depends(get_db)):
    svc = AuthService(db)
    return await svc.login(dto)


class GoogleMobileLoginDTO(BaseModel):
    id_token: str


@router.post("/google", response_model=TokenResponseDTO)
async def google_mobile_login(
    dto: GoogleMobileLoginDTO,
    db: AsyncSession = Depends(get_db),
):
    """Mobile Google Sign-In: accepts a Google ID token, returns a JWT.

    The Flutter app obtains the ID token via google_sign_in, then posts it here.
    We verify it with Google's tokeninfo endpoint and log in / auto-register.
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                _GOOGLE_TOKENINFO_URL,
                params={"id_token": dto.id_token},
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=401, detail="رمز Google غير صالح")
            info = resp.json()

        if "error_description" in info or "error" in info:
            raise HTTPException(
                status_code=401,
                detail=info.get("error_description", "رمز Google غير صالح"),
            )

        userinfo = {
            "email": info.get("email", ""),
            "name":  info.get("name", info.get("email", "").split("@")[0]),
        }

        svc = AuthService(db)
        user = await svc.login_or_register_google(userinfo)
        token = create_access_token({"sub": str(user.id)})
        return TokenResponseDTO(
            access_token=token,
            user_id=user.id,
            username=user.username,
        )

    except HTTPException:
        raise
    except (ValidationError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="خطأ في الخادم") from exc
