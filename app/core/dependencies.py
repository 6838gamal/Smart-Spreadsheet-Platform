"""
FastAPI dependency injection utilities.
"""

from typing import Annotated, Optional, Dict
from fastapi import Depends, HTTPException, Request, status, Response
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.core.database import get_db
from app.core.security import decode_token, get_token_from_request
from app.core.exceptions import AuthenticationError
from app.infrastructure.repositories.user_repository import UserRepository
from app.infrastructure.database.models import User
from app.core.templates import get_texts, get_language_direction, DEFAULT_TRANSLATIONS

logger = logging.getLogger(__name__)

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


# ============================================================
# USER DEPENDENCIES
# ============================================================

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency: returns the authenticated user or raises AuthenticationError.
    
    Args:
        request: FastAPI request
        db: Database session
    
    Returns:
        User: Authenticated user
    
    Raises:
        AuthenticationError: If user is not authenticated
    """
    token = get_token_from_request(request)
    if not token:
        raise AuthenticationError("no_token")

    try:
        payload = decode_token(token)
    except HTTPException:
        # JWT is invalid or expired — raise AuthenticationError so the
        # AppException handler can redirect to the login page cleanly.
        raise AuthenticationError("session_expired")

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("session_expired")

    repo = UserRepository(db)
    user = await repo.get_by_id(int(user_id))
    if not user or not user.is_active:
        raise AuthenticationError("session_expired")
    
    # Store user in request state for later use
    request.state.user = user
    
    return user


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Dependency: returns the authenticated user or None (no redirect).
    
    Args:
        request: FastAPI request
        db: Database session
    
    Returns:
        Optional[User]: User if authenticated, else None
    """
    try:
        return await get_current_user(request, db)
    except Exception as e:
        logger.debug(f"Optional user authentication failed: {e}")
        return None


# ============================================================
# LANGUAGE DEPENDENCIES
# ============================================================

async def get_lang(
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional),
) -> str:
    """
    Detect user's preferred language.
    
    Priority:
    1. User's default language (if authenticated)
    2. Cookie 'lang'
    3. Accept-Language header
    4. Default 'ar'
    
    Args:
        request: FastAPI request
        user: Authenticated user (optional)
    
    Returns:
        str: Language code (ar, en, etc.)
    """
    # 1. Check authenticated user's preference
    if user and hasattr(user, 'default_lang') and user.default_lang:
        if user.default_lang in DEFAULT_TRANSLATIONS:
            request.state.lang = user.default_lang
            return user.default_lang
    
    # 2. Check cookie
    lang = request.cookies.get('lang')
    if lang and lang in DEFAULT_TRANSLATIONS:
        request.state.lang = lang
        return lang
    
    # 3. Check Accept-Language header
    accept_language = request.headers.get('accept-language', 'ar')
    lang = accept_language.split(',')[0][:2]
    if lang in DEFAULT_TRANSLATIONS:
        request.state.lang = lang
        return lang
    
    # 4. Default to Arabic
    request.state.lang = 'ar'
    return 'ar'


async def get_translations(
    request: Request,
    lang: str = Depends(get_lang),
) -> Dict[str, str]:
    """
    Get translations for the detected language.
    
    Args:
        request: FastAPI request
        lang: Language code
    
    Returns:
        Dict: Translation dictionary
    """
    translations = get_texts(lang)
    request.state.translations = translations
    return translations


async def get_language_direction_dep(
    request: Request,
    lang: str = Depends(get_lang),
) -> str:
    """
    Get text direction for the detected language.
    
    Args:
        request: FastAPI request
        lang: Language code
    
    Returns:
        str: 'rtl' or 'ltr'
    """
    direction = get_language_direction(lang)
    request.state.direction = direction
    return direction


async def get_language_context(
    request: Request,
    lang: str = Depends(get_lang),
) -> Dict[str, any]:
    """
    Get complete language context for templates.
    
    Args:
        request: FastAPI request
        lang: Language code
    
    Returns:
        Dict: Language context with translations and direction
    """
    translations = get_texts(lang)
    direction = get_language_direction(lang)
    
    context = {
        'lang': lang,
        'direction': direction,
        'translations': translations,
        'get_texts': get_texts,
        't': lambda text, **kwargs: translations.get(text, text).format(**kwargs) if kwargs else translations.get(text, text),
    }
    
    request.state.lang = lang
    request.state.direction = direction
    request.state.translations = translations
    
    return context


# ============================================================
# COOKIE HELPERS
# ============================================================

async def set_lang_cookie(
    response: Response,
    lang: str,
    max_age: int = 60 * 60 * 24 * 30,  # 30 days
) -> None:
    """
    Set language cookie in response.
    
    Args:
        response: FastAPI response
        lang: Language code
        max_age: Cookie max age in seconds
    """
    if lang not in DEFAULT_TRANSLATIONS:
        lang = 'ar'
    
    response.set_cookie(
        key="lang",
        value=lang,
        max_age=max_age,
        path="/",
        httponly=True,
        samesite="lax",
        secure=False,  # Set to True in production with HTTPS
    )


async def clear_lang_cookie(response: Response) -> None:
    """
    Clear language cookie.
    
    Args:
        response: FastAPI response
    """
    response.delete_cookie(
        key="lang",
        path="/",
    )


# ============================================================
# USER LANGUAGE UPDATE
# ============================================================

async def update_user_language(
    user: User,
    lang: str,
    db: AsyncSession,
) -> User:
    """
    Update user's preferred language.
    
    Args:
        user: User object
        lang: Language code
        db: Database session
    
    Returns:
        User: Updated user
    
    Raises:
        ValueError: If language is not supported
    """
    if lang not in DEFAULT_TRANSLATIONS:
        raise ValueError(f"Language '{lang}' is not supported")
    
    # Update user
    user.default_lang = lang
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    logger.info(f"Updated user {user.id} language to {lang}")
    return user


# ============================================================
# TYPE ALIASES
# ============================================================

CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[Optional[User], Depends(get_current_user_optional)]
DB = Annotated[AsyncSession, Depends(get_db)]
Lang = Annotated[str, Depends(get_lang)]
Translations = Annotated[Dict[str, str], Depends(get_translations)]
LanguageDirection = Annotated[str, Depends(get_language_direction_dep)]
LanguageContext = Annotated[Dict[str, any], Depends(get_language_context)]


# ============================================================
# HELPER FUNCTIONS FOR ROUTES
# ============================================================

def get_user_language(user: Optional[User]) -> str:
    """
    Get user's preferred language from user object.
    
    Args:
        user: User object or None
    
    Returns:
        str: Language code
    """
    if user and hasattr(user, 'default_lang') and user.default_lang:
        return user.default_lang
    return 'ar'


def get_user_name(user: User) -> str:
    """
    Get user's display name.
    
    Args:
        user: User object
    
    Returns:
        str: User's display name
    """
    if hasattr(user, 'full_name') and user.full_name:
        return user.full_name
    return user.username or user.email or "User"


def is_user_authenticated(user: Optional[User]) -> bool:
    """
    Check if user is authenticated.
    
    Args:
        user: User object or None
    
    Returns:
        bool: True if user is authenticated
    """
    return user is not None and user.is_active
