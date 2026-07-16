"""Auth API endpoints."""

from fastapi import APIRouter, Response, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.application.auth.dto import RegisterDTO, LoginDTO, TokenResponseDTO
from app.application.auth.service import AuthService

router = APIRouter()


@router.post("/register", response_model=TokenResponseDTO)
async def register(dto: RegisterDTO, db: AsyncSession = Depends(get_db)):
    svc = AuthService(db)
    user = await svc.register(dto)
    # Auto-login after register
    from app.core.security import create_access_token
    token = create_access_token({"sub": str(user.id)})
    return TokenResponseDTO(access_token=token, user_id=user.id, username=user.username)


@router.post("/login", response_model=TokenResponseDTO)
async def login(dto: LoginDTO, db: AsyncSession = Depends(get_db)):
    svc = AuthService(db)
    return await svc.login(dto)
