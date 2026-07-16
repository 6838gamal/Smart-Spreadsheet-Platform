"""OperationLog repository."""

from datetime import datetime, timezone
from sqlalchemy import select, func, desc
from app.infrastructure.repositories.base import BaseRepository
from app.infrastructure.database.models import OperationLog, OperationStatus, OperationType


class OperationRepository(BaseRepository[OperationLog]):
    model = OperationLog

    async def get_by_user(self, user_id: int, limit: int = 50, offset: int = 0) -> list[OperationLog]:
        result = await self.db.execute(
            select(OperationLog)
            .where(OperationLog.user_id == user_id)
            .order_by(desc(OperationLog.started_at))
            .limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def count_by_user(self, user_id: int) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(OperationLog).where(OperationLog.user_id == user_id)
        )
        return result.scalar_one()

    async def get_recent_by_user(self, user_id: int, limit: int = 5) -> list[OperationLog]:
        result = await self.db.execute(
            select(OperationLog)
            .where(OperationLog.user_id == user_id)
            .order_by(desc(OperationLog.started_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_complete(
        self,
        operation: OperationLog,
        status: OperationStatus,
        result: dict | None = None,
        error: str | None = None,
        output_path: str | None = None,
        duration_ms: int | None = None,
    ) -> OperationLog:
        return await self.update(
            operation,
            status=status,
            result=result or {},
            error_message=error,
            output_path=output_path,
            duration_ms=duration_ms,
            completed_at=datetime.now(timezone.utc),
        )
