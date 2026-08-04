"""
Async SQLAlchemy database setup.
Supports SQLite (development) and PostgreSQL (production) via DATABASE_URL.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

_db_url = settings.async_database_url
# use_ssl is True for all PostgreSQL URLs unless sslmode=disable is set explicitly.
_connect_args: dict = {"ssl": settings.use_ssl}

engine = create_async_engine(
    _db_url,
    echo=settings.DEBUG,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


async def get_db() -> AsyncSession:
    """Dependency that provides a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
