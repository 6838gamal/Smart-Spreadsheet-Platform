"""Data cleaning application service."""

import logging
import time
import uuid
from pathlib import Path
import polars as pl
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, AuthorizationError, ProcessingError
from app.infrastructure.repositories.file_repository import FileRepository
from app.infrastructure.repositories.operation_repository import OperationRepository
from app.infrastructure.database.models import OperationType, OperationStatus
from app.infrastructure.storage.local_storage import storage
from app.application.converter.engine import DataEngine
from app.application.cleaner.dto import CleanOptionsDTO

logger = logging.getLogger(__name__)


class CleanerService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.file_repo = FileRepository(db)
        self.op_repo = OperationRepository(db)
        self.engine = DataEngine()

    async def clean(self, dto: CleanOptionsDTO, user_id: int) -> dict:
        f = await self.file_repo.get_by_id(dto.file_id)
        if not f:
            raise NotFoundError("File")
        if f.owner_id != user_id:
            raise AuthorizationError()

        op = await self.op_repo.create(
            type=OperationType.CLEAN,
            user_id=user_id,
            file_id=f.id,
            input_path=f.path,
            params=dto.model_dump(),
        )

        t0 = time.time()
        try:
            df = self.engine.read(f.path, f.format)
            original_rows, original_cols = df.shape
            changes = []

            if dto.remove_empty_rows:
                before = len(df)
                df = df.filter(~pl.all_horizontal(pl.all().is_null()))
                removed = before - len(df)
                if removed:
                    changes.append(f"Removed {removed} empty rows")

            if dto.remove_empty_cols:
                before_cols = len(df.columns)
                null_counts = df.null_count()
                empty_cols = [
                    c for c in df.columns
                    if null_counts[c][0] == len(df)
                ]
                df = df.drop(empty_cols)
                if empty_cols:
                    changes.append(f"Removed {len(empty_cols)} empty columns")

            if dto.remove_duplicates:
                before = len(df)
                df = df.unique()
                removed = before - len(df)
                if removed:
                    changes.append(f"Removed {removed} duplicate rows")

            if dto.trim_spaces:
                str_cols = [c for c, d in zip(df.columns, df.dtypes) if d == pl.Utf8 or d == pl.String]
                df = df.with_columns([
                    pl.col(c).str.strip_chars() for c in str_cols
                ])
                if str_cols:
                    changes.append(f"Trimmed spaces in {len(str_cols)} text columns")

            if dto.fill_nulls is not None:
                df = df.fill_null(dto.fill_nulls)
                changes.append(f"Filled nulls with '{dto.fill_nulls}'")

            # Write output
            stem = Path(f.original_name).stem
            out_name = f"{stem}_cleaned_{uuid.uuid4().hex[:6]}.{dto.target_format}"
            out_path = storage.get_output_path(user_id, out_name)
            self.engine.write(df, str(out_path), dto.target_format)

            duration_ms = int((time.time() - t0) * 1000)
            result = {
                "original_rows": original_rows,
                "result_rows": len(df),
                "original_cols": original_cols,
                "result_cols": len(df.columns),
                "changes": changes,
                "output": str(out_path),
                "output_filename": out_name,
            }
            await self.op_repo.mark_complete(
                op, OperationStatus.SUCCESS,
                result=result, output_path=str(out_path), duration_ms=duration_ms,
            )
            return result

        except Exception as e:
            duration_ms = int((time.time() - t0) * 1000)
            await self.op_repo.mark_complete(
                op, OperationStatus.FAILED, error=str(e), duration_ms=duration_ms,
            )
            raise ProcessingError(str(e))
