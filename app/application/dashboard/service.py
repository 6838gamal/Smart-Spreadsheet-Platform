"""Dashboard application service — aggregates stats for the homepage."""

from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.repositories.file_repository import FileRepository
from app.infrastructure.repositories.operation_repository import OperationRepository


class DashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.file_repo = FileRepository(db)
        self.op_repo = OperationRepository(db)

    async def get_stats(self, user_id: int) -> dict:
        total_files = await self.file_repo.count_by_owner(user_id)
        total_size = await self.file_repo.total_size_by_owner(user_id)
        total_ops = await self.op_repo.count_by_user(user_id)
        recent_files = await self.file_repo.get_recent(user_id, limit=6)
        recent_ops = await self.op_repo.get_recent_by_user(user_id, limit=8)
        favorites = await self.file_repo.get_favorites(user_id, limit=4)
        format_counts = await self.file_repo.get_by_format_counts(user_id)

        return {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_human": _human_size(total_size),
            "total_operations": total_ops,
            "recent_files": recent_files,
            "recent_operations": recent_ops,
            "favorites": favorites,
            "format_counts": format_counts,
        }


def _human_size(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"
