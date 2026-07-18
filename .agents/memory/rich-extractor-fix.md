---
name: rich_extractor corruption fix
description: rich_extractor.py was triplicated (3 copies of all functions) with broken regex definitions at the junctions — how to detect and fix
---

# rich_extractor.py triplication bug

## The rule
`app/application/converter/rich_extractor.py` was corrupted: the entire file was concatenated 3 times. At each junction, a regex variable definition was split across the boundary, leaving an unterminated raw string literal on one line and a dangling `, re.DOTALL)` fragment on another.

**Why:** Unknown code-generation error. The file looked syntactically valid in a text editor but Python's parser rejected it at line 28.

**How to apply:** If the file ever fails with `SyntaxError: unterminated string literal`, check for:
1. Lines matching `_LATEX_INLINE\s*=.*re\.compile.*` that do NOT end with `)` — fix to: `_LATEX_INLINE  = re.compile(r'\$(?!\$).+?\$', re.DOTALL)`
2. Lines matching `_LATEX_DISPLAY\s*=.*re\.compile.*` that do NOT end with `)` — fix to: `_LATEX_DISPLAY = re.compile(r'\$\$.+?\$\$', re.DOTALL)`
3. Standalone lines containing only `, re.DOTALL)` — remove them

Fix script (safe to run multiple times):
```python
with open("app/application/converter/rich_extractor.py", "rb") as f:
    lines = f.read().split(b"\n")
fixed = []
for ln in lines:
    if ln.startswith(b"_LATEX_INLINE") and b"re.compile" in ln and not ln.rstrip().endswith(b")"):
        fixed.append(b"_LATEX_INLINE  = re.compile(r'\\$(?!\\$).+?\\$', re.DOTALL)")
    elif ln.startswith(b"_LATEX_DISPLAY") and b"re.compile" in ln and not ln.rstrip().endswith(b")"):
        fixed.append(b"_LATEX_DISPLAY = re.compile(r'\\$\\$.+?\\$\\$', re.DOTALL)")
    elif ln.strip() == b", re.DOTALL)":
        pass  # remove dangling fragment
    else:
        fixed.append(ln)
with open("app/application/converter/rich_extractor.py", "wb") as f:
    f.write(b"\n".join(fixed))
```

## Other engine.py fixes applied at same time
- `_read_sqlite`: `SHOW TABLES` doesn't see attached SQLite tables — must use `SHOW ALL TABLES` and filter by `database == 'src'`
- `_read_docx_tables`: added paragraph-text fallback for text-only DOCX files
- `_read_pptx`: replaced `tbl._tbl.col_count` / `tbl._tbl.tr_count` (private API) with `len(tbl.columns)` / `len(tbl.rows)`
