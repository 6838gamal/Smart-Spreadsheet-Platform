---
name: Search & Q&A system design
description: Architecture decisions for the BM25-based document Q&A feature, upgrade path to embeddings.
---

# Search & Q&A System

## Rule
Phase 1 uses BM25 (rank-bm25, pure Python). Backend is injected via `SearchService(backend=...)`. Swap to `EmbeddingBackend` for Phase 2 with zero changes to callers.

**Why:** User explicitly asked for the lightest solution that's ready to upgrade. The abstraction boundary (`SearchBackend` ABC) is the key design decision.

## How to apply
- `app/services/search/backends.py` — `SearchBackend` ABC + `BM25Backend`
- `app/services/search/search_service.py` — `search_service` singleton (import this)
- `app/services/search/text_chunker.py` — paragraph-aware chunking, ~400 chars, 80 overlap
- `app/infrastructure/database/models_intelligence.py` — `DocumentChunk` table stores chunks (no vector yet)
- Auto-indexing: hooked into `pipeline_manager.py` `handle_analysis_job` after COMPLETED status
- Phase 2: add `embedding JSON` column to `DocumentChunk`, implement `EmbeddingBackend` with sentence-transformers + FAISS

## Admin credentials
Default admin: `admin@spreadsheet.com` / `Spreadsheet123` (set in main.py lifespan on first run)

## File model
Storage path field is `file.path` (not `storage_path`).
