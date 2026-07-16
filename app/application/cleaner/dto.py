"""DTOs for data cleaning operations."""

from pydantic import BaseModel


class CleanOptionsDTO(BaseModel):
    file_id: int
    remove_duplicates: bool = False
    trim_spaces: bool = False
    remove_empty_rows: bool = False
    remove_empty_cols: bool = False
    fill_nulls: str | None = None        # value to fill nulls with
    normalize_text: bool = False
    standardize_dates: bool = False
    target_format: str = "xlsx"
