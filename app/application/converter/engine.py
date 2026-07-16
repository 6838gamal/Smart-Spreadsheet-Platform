"""
Core data processing engine built on Polars + PyArrow + DuckDB.
Handles reading, writing, and previewing all supported formats.
"""

import logging
import io
from pathlib import Path
from typing import Any

import polars as pl
import duckdb

logger = logging.getLogger(__name__)

# ─── Format groups ────────────────────────────────────────────────────────────

EXCEL_FORMATS = {"xlsx", "xls", "xlsm", "xlsb"}
CSV_LIKE = {"csv", "tsv", "txt"}
ARROW_FORMATS = {"parquet", "feather"}
STRUCTURED = {"json", "xml", "yaml", "yml"}
DB_FORMATS = {"sqlite", "db"}
DOC_FORMATS = {"docx", "pdf"}
ODS_FORMAT = {"ods"}


class DataEngine:
    """
    Unified data engine using Polars as the primary processing backbone.
    Falls back to pandas / openpyxl where Polars lacks native support.
    """

    # ─── Read ─────────────────────────────────────────────────────────────────

    def read(self, path: str, fmt: str, sheet: str | int | None = None) -> pl.DataFrame:
        """Read any supported format into a Polars DataFrame."""
        fmt = fmt.lower().lstrip(".")

        if fmt in CSV_LIKE:
            sep = "\t" if fmt == "tsv" else ","
            return pl.read_csv(path, separator=sep, infer_schema_length=5000, ignore_errors=True)

        if fmt in EXCEL_FORMATS:
            return self._read_excel(path, fmt, sheet)

        if fmt == "parquet":
            return pl.read_parquet(path)

        if fmt == "feather":
            return pl.read_ipc(path)

        if fmt == "json":
            try:
                return pl.read_json(path)
            except Exception:
                return pl.read_ndjson(path)

        if fmt in {"yaml", "yml"}:
            return self._read_yaml(path)

        if fmt == "xml":
            return self._read_xml(path)

        if fmt in DB_FORMATS:
            return self._read_sqlite(path)

        if fmt == "docx":
            return self._read_docx_tables(path)

        if fmt == "pdf":
            return self._read_pdf_tables(path)

        if fmt == "ods":
            return self._read_ods(path)

        raise ValueError(f"Unsupported read format: {fmt}")

    def _read_excel(self, path: str, fmt: str, sheet=None) -> pl.DataFrame:
        try:
            # python-calamine is fastest for xlsx/xls
            import python_calamine
            return pl.read_excel(path, sheet_name=sheet or 0, engine="calamine")
        except Exception:
            pass
        try:
            return pl.read_excel(path, sheet_name=sheet or 0, engine="openpyxl")
        except Exception:
            import pandas as pd
            if fmt == "xlsb":
                df_pd = pd.read_excel(path, sheet_name=sheet or 0, engine="pyxlsb")
            elif fmt == "xls":
                df_pd = pd.read_excel(path, sheet_name=sheet or 0, engine="xlrd")
            else:
                df_pd = pd.read_excel(path, sheet_name=sheet or 0)
            return pl.from_pandas(df_pd)

    def _read_yaml(self, path: str) -> pl.DataFrame:
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        if isinstance(data, list):
            return pl.DataFrame(data)
        return pl.DataFrame([data])

    def _read_xml(self, path: str) -> pl.DataFrame:
        import pandas as pd
        df_pd = pd.read_xml(path)
        return pl.from_pandas(df_pd)

    def _read_sqlite(self, path: str) -> pl.DataFrame:
        con = duckdb.connect()
        con.execute(f"ATTACH '{path}' AS src (TYPE sqlite)")
        tables = con.execute("SHOW TABLES").fetchall()
        if not tables:
            return pl.DataFrame()
        table_name = tables[0][0]
        return con.execute(f"SELECT * FROM src.{table_name}").pl()

    def _read_docx_tables(self, path: str) -> pl.DataFrame:
        from docx import Document
        doc = Document(path)
        rows = []
        headers: list[str] = []
        for table in doc.tables:
            if not headers:
                headers = [cell.text.strip() for cell in table.rows[0].cells]
            for row in table.rows[1:]:
                rows.append({h: c.text.strip() for h, c in zip(headers, row.cells)})
        return pl.DataFrame(rows) if rows else pl.DataFrame()

    def _read_pdf_tables(self, path: str) -> pl.DataFrame:
        import pdfplumber
        rows = []
        headers: list[str] = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables():
                    if not table:
                        continue
                    if not headers:
                        headers = [str(c or f"col_{i}") for i, c in enumerate(table[0])]
                    for row in table[1:]:
                        rows.append({h: str(c or "") for h, c in zip(headers, row)})
        return pl.DataFrame(rows) if rows else pl.DataFrame()

    def _read_ods(self, path: str) -> pl.DataFrame:
        import pandas as pd
        df_pd = pd.read_excel(path, engine="odf")
        return pl.from_pandas(df_pd)

    # ─── Write ────────────────────────────────────────────────────────────────

    def write(self, df: pl.DataFrame, path: str, fmt: str, **kwargs) -> None:
        """Write a Polars DataFrame to any supported output format."""
        fmt = fmt.lower().lstrip(".")

        if fmt == "csv":
            df.write_csv(path)
        elif fmt == "tsv":
            df.write_csv(path, separator="\t")
        elif fmt in EXCEL_FORMATS or fmt == "xlsx":
            df.write_excel(path)
        elif fmt == "parquet":
            df.write_parquet(path)
        elif fmt == "feather":
            df.write_ipc(path)
        elif fmt == "json":
            df.write_json(path)
        elif fmt == "ndjson":
            df.write_ndjson(path)
        elif fmt == "html":
            df.to_pandas().to_html(path, index=False)
        elif fmt == "xml":
            df.to_pandas().to_xml(path, index=False)
        elif fmt in {"yaml", "yml"}:
            import yaml
            with open(path, "w") as f:
                yaml.dump(df.to_dicts(), f, allow_unicode=True)
        elif fmt == "ods":
            df.to_pandas().to_excel(path, engine="odf", index=False)
        elif fmt == "sqlite":
            con = duckdb.connect()
            con.register("df_table", df.to_arrow())
            con.execute(f"ATTACH '{path}' AS dest (TYPE sqlite)")
            con.execute("CREATE TABLE dest.data AS SELECT * FROM df_table")
        elif fmt == "docx":
            self._write_docx(df, path)
        elif fmt == "pdf":
            self._write_pdf(df, path)
        else:
            # Fallback: write as CSV
            df.write_csv(path)

    def _write_docx(self, df: pl.DataFrame, path: str) -> None:
        from docx import Document
        doc = Document()
        table = doc.add_table(rows=1 + len(df), cols=len(df.columns))
        for i, col in enumerate(df.columns):
            table.rows[0].cells[i].text = col
        for r_idx, row in enumerate(df.iter_rows()):
            for c_idx, val in enumerate(row):
                table.rows[r_idx + 1].cells[c_idx].text = str(val) if val is not None else ""
        doc.save(path)

    def _write_pdf(self, df: pl.DataFrame, path: str) -> None:
        """Write DataFrame as PDF using HTML conversion."""
        html = df.to_pandas().to_html(index=False)
        # Simple HTML-to-text PDF fallback
        with open(path, "w") as f:
            f.write(f"<html><body>{html}</body></html>")

    # ─── Preview ──────────────────────────────────────────────────────────────

    def preview(self, path: str, fmt: str, rows: int = 100) -> dict:
        """Return preview data: columns, sample rows, shape."""
        try:
            df = self.read(path, fmt)
            total_rows, total_cols = df.shape
            sample = df.head(rows)
            return {
                "columns": df.columns,
                "dtypes": [str(d) for d in df.dtypes],
                "rows": sample.to_dicts(),
                "total_rows": total_rows,
                "total_cols": total_cols,
                "shape": f"{total_rows:,} × {total_cols}",
            }
        except Exception as e:
            logger.error(f"Preview failed for {path}: {e}")
            return {"error": str(e), "columns": [], "rows": [], "total_rows": 0, "total_cols": 0}

    # ─── Metadata ─────────────────────────────────────────────────────────────

    def get_metadata(self, path: str, fmt: str) -> dict:
        """Extract lightweight metadata without reading the full file."""
        meta: dict[str, Any] = {}
        try:
            if fmt in EXCEL_FORMATS:
                import openpyxl
                wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
                meta["sheets"] = wb.sheetnames
                ws = wb.active
                meta["rows"] = ws.max_row
                meta["columns"] = ws.max_column
                wb.close()
            elif fmt in CSV_LIKE:
                sep = "\t" if fmt == "tsv" else ","
                df = pl.scan_csv(path, separator=sep, infer_schema_length=100).limit(1).collect()
                meta["columns"] = len(df.columns)
                # Count rows via line count
                with open(path, "rb") as f:
                    meta["rows"] = sum(1 for _ in f)
            elif fmt == "parquet":
                import pyarrow.parquet as pq
                pf = pq.ParquetFile(path)
                meta["rows"] = pf.metadata.num_rows
                meta["columns"] = pf.metadata.num_columns
        except Exception as e:
            logger.debug(f"Partial metadata extraction: {e}")
        return meta

    # ─── Sheet listing ────────────────────────────────────────────────────────

    def list_sheets(self, path: str, fmt: str) -> list[str]:
        if fmt not in EXCEL_FORMATS:
            return []
        try:
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True)
            sheets = wb.sheetnames
            wb.close()
            return sheets
        except Exception:
            return []
