"""
FastAPI dependency injection utilities.
"""

from typing import Annotated
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token, get_token_from_request
from app.core.exceptions import AuthenticationError
from app.infrastructure.repositories.user_repository import UserRepository
from app.infrastructure.database.models import User


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency: returns the authenticated user or raises 401."""
    token = get_token_from_request(request)
    if not token:
        raise AuthenticationError()
    
    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError()

    repo = UserRepository(db)
    user = await repo.get_by_id(int(user_id))
    if not user or not user.is_active:
        raise AuthenticationError()
    return user


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Dependency: returns the authenticated user or None (no redirect)."""
    try:
        return await get_current_user(request, db)
    except Exception:
        return None


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]
DB = Annotated[AsyncSession, Depends(get_db)]
