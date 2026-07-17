"""Repository for ServerPing — persisted DB health-check records."""

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import ServerPing
from app.infrastructure.repositories.base import BaseRepository


class ServerPingRepository(BaseRepository):
    model = ServerPing

    def __init__(self, db: AsyncSession):
        super().__init__(db)

    async def add_ping(self, ok: bool, latency_ms: int | None, detail: str) -> ServerPing:
        return await self.create(ok=ok, latency_ms=latency_ms, detail=detail)

    async def get_history(self, limit: int = 30) -> list[ServerPing]:
        result = await self.db.execute(
            select(ServerPing).order_by(ServerPing.pinged_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def get_stats(self) -> dict:
        total = (
            await self.db.execute(select(func.count()).select_from(ServerPing))
        ).scalar_one()
        fails = (
            await self.db.execute(
                select(func.count()).select_from(ServerPing).where(ServerPing.ok == False)  # noqa: E712
            )
        ).scalar_one()
        return {"total_pings": total, "total_fails": fails}
