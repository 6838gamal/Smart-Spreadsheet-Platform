"""Authentication application service."""

import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password, create_access_token
from app.core.exceptions import ValidationError, AuthenticationError
from app.infrastructure.repositories.user_repository import UserRepository
from app.infrastructure.database.models import User, UserRole
from app.application.auth.dto import RegisterDTO, LoginDTO, TokenResponseDTO

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)

    async def register(self, dto: RegisterDTO) -> User:
        dto.check_passwords_match()

        if await self.user_repo.email_exists(dto.email):
            raise ValidationError("Email address already registered")
        if await self.user_repo.username_exists(dto.username):
            raise ValidationError("Username already taken")

        user = await self.user_repo.create(
            email=dto.email,
            username=dto.username,
            hashed_password=hash_password(dto.password),
            role=UserRole.USER,
            preferences={"theme": "dark", "language": "ar"},
        )
        logger.info(f"New user registered: {user.email}")
        return user

    async def login_or_register_google(self, userinfo: dict) -> "User":
        """Find or create a USER-role account from Google userinfo payload."""
        email: str = userinfo.get("email", "").lower().strip()
        if not email:
            raise ValidationError("لم يتم الحصول على البريد الإلكتروني من Google")

        user = await self.user_repo.get_by_email(email)
        if user:
            if not user.is_active:
                raise AuthenticationError("الحساب معطّل")
            logger.info("Google login: existing user %s", email)
            return user

        # First-time — create a USER account (no password)
        name: str = userinfo.get("name", "")
        username_base = email.split("@")[0]
        username = username_base
        suffix = 1
        while await self.user_repo.username_exists(username):
            username = f"{username_base}{suffix}"
            suffix += 1

        user = await self.user_repo.create(
            email=email,
            username=username,
            hashed_password="",          # Google users never use a password
            role=UserRole.USER,
            preferences={"theme": "dark", "language": "ar", "full_name": name},
        )
        logger.info("Google login: new user created %s", email)
        return user

    async def login(self, dto: LoginDTO) -> TokenResponseDTO:
        user = await self.user_repo.get_by_email(dto.email)
        if not user or not verify_password(dto.password, user.hashed_password):
            raise AuthenticationError("Invalid email or password")
        if not user.is_active:
            raise AuthenticationError("Account is disabled")

        token = create_access_token({"sub": str(user.id)})
        logger.info(f"User logged in: {user.email}")
        return TokenResponseDTO(
            access_token=token,
            user_id=user.id,
            username=user.username,
        )
