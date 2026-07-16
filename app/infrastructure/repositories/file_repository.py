"""File repository — data access for File model."""

from sqlalchemy import select, func, desc
from app.infrastructure.repositories.base import BaseRepository
from app.infrastructure.database.models import File, FileStatus


class FileRepository(BaseRepository[File]):
    model = File

    async def get_by_owner(
        self,
        owner_id: int,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
        format_filter: str | None = None,
    ) -> list[File]:
        q = select(File).where(File.owner_id == owner_id)
        if search:
            q = q.where(File.name.ilike(f"%{search}%"))
        if format_filter:
            q = q.where(File.format == format_filter)
        q = q.order_by(desc(File.created_at)).limit(limit).offset(offset)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def count_by_owner(self, owner_id: int) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(File).where(File.owner_id == owner_id)
        )
        return result.scalar_one()

    async def total_size_by_owner(self, owner_id: int) -> int:
        result = await self.db.execute(
            select(func.coalesce(func.sum(File.size_bytes), 0)).where(File.owner_id == owner_id)
        )
        return result.scalar_one()

    async def get_favorites(self, owner_id: int, limit: int = 10) -> list[File]:
        result = await self.db.execute(
            select(File)
            .where(File.owner_id == owner_id, File.is_favorite == True)
            .order_by(desc(File.updated_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent(self, owner_id: int, limit: int = 8) -> list[File]:
        result = await self.db.execute(
            select(File)
            .where(File.owner_id == owner_id)
            .order_by(desc(File.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_format_counts(self, owner_id: int) -> dict[str, int]:
        result = await self.db.execute(
            select(File.format, func.count(File.id))
            .where(File.owner_id == owner_id)
            .group_by(File.format)
        )
        return {row[0]: row[1] for row in result.all()}
