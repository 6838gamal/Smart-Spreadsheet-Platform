"""
Text chunking utilities.
Splits raw document text into overlapping passages suitable for BM25 / embedding search.
Phase 1: paragraph-aware chunking — no model required.
Phase 2: replace or extend with sentence-level splitting via sentence-transformers.
"""
from __future__ import annotations
import logging
import re

logger = logging.getLogger(__name__)


def chunk_text(
    text: str,
    chunk_size: int = 400,
    overlap: int = 80,
    min_chunk: int = 50,
    max_chunks: int = 500,
) -> list[dict]:
    """
    Split *text* into overlapping chunks.

    Returns a list of dicts:
        {"chunk_index": int, "chunk_text": str}

    Strategy (upgrade path):
        Phase 1 — paragraph-aware sliding window (this implementation).
        Phase 2 — replace with sentence-level splits from sentence-transformers.
        Phase 3 — semantic chunking with a local LLM.
    """
    if not text or not text.strip():
        return []

    text = text.strip()
    total_len = len(text)

    # ── 1. Normalise whitespace & split into paragraphs ──
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    # ── 2. Build a sentence pool with fallbacks ──
    sentences: list[str] = []
    for para in paragraphs:
        # Try sentence split (multi-language punctuation)
        sents = re.split(r"(?<=[.!?؟。！？])\s+", para)

        # Fallback A: if no sentence boundaries detected and paragraph is huge,
        # split by newlines
        if len(sents) == 1 and len(para) > chunk_size * 2:
            sents = re.split(r"\n+", para)

        # Fallback B: if STILL one giant block, split into word groups
        if len(sents) == 1 and len(para) > chunk_size * 2:
            words = para.split()
            group: list[str] = []
            group_len = 0
            for w in words:
                if group_len + len(w) + 1 > chunk_size and group:
                    sentences.append(" ".join(group))
                    group = []
                    group_len = 0
                group.append(w)
                group_len += len(w) + 1
            if group:
                sentences.append(" ".join(group))
        else:
            sentences.extend([s.strip() for s in sents if s.strip()])

    if not sentences:
        return []

    # ── 3. Sliding window over sentences ──
    chunks: list[dict] = []
    current: list[str] = []
    current_len = 0
    chunk_idx = 0

    for sent in sentences:
        if chunk_idx >= max_chunks:
            logger.warning(f"⚠️ chunk_text hit max_chunks={max_chunks}")
            break

        sent_len = len(sent)

        # ── Edge case: single sentence larger than chunk_size ──
        if sent_len > chunk_size and not current:
            step = max(chunk_size - overlap, 1)
            for i in range(0, sent_len, step):
                piece = sent[i:i + chunk_size]
                if len(piece) >= min_chunk:
                    chunks.append({"chunk_index": chunk_idx, "chunk_text": piece})
                    chunk_idx += 1
                    if chunk_idx >= max_chunks:
                        break
            continue

        # ── Flush current chunk when window is full ──
        if current_len + sent_len > chunk_size and current:
            chunk_str = " ".join(current).strip()
            if len(chunk_str) >= min_chunk:
                chunks.append({"chunk_index": chunk_idx, "chunk_text": chunk_str})
                chunk_idx += 1

            # Build overlap from tail of current
            overlap_sents: list[str] = []
            overlap_len = 0
            for s in reversed(current):
                if overlap_len + len(s) <= overlap:
                    overlap_sents.insert(0, s)
                    overlap_len += len(s)
                else:
                    break
            current = overlap_sents
            current_len = overlap_len

        current.append(sent)
        current_len += sent_len

    # ── 4. Flush remaining ──
    if current and chunk_idx < max_chunks:
        chunk_str = " ".join(current).strip()
        if len(chunk_str) >= min_chunk:
            chunks.append({"chunk_index": chunk_idx, "chunk_text": chunk_str})

    logger.info(
        f"✂️ chunk_text: {total_len} chars → {len(chunks)} chunks "
        f"(chunk_size={chunk_size}, overlap={overlap})"
    )
    return chunks
