"""
Text chunking utilities.
Splits raw document text into overlapping passages suitable for BM25 / embedding search.
Phase 1: paragraph-aware chunking — no model required.
Phase 2: replace or extend with sentence-level splitting via sentence-transformers.
"""
from __future__ import annotations
import re


def chunk_text(
    text: str,
    chunk_size: int = 400,
    overlap: int = 80,
    min_chunk: int = 50,
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

    # 1. Normalise whitespace & split into paragraphs
    text = text.strip()
    # Collapse runs of blank lines into a single paragraph separator
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]

    if not paragraphs:
        return []

    # 2. Build chunks by sliding a window over sentences/words
    # Merge small paragraphs, split large ones
    sentences: list[str] = []
    for para in paragraphs:
        # Split paragraph into sentences (rough heuristic)
        sents = re.split(r"(?<=[.!?؟])\s+", para)
        sentences.extend([s.strip() for s in sents if s.strip()])

    chunks: list[dict] = []
    current: list[str] = []
    current_len = 0
    chunk_idx = 0

    for sent in sentences:
        sent_len = len(sent)

        if current_len + sent_len > chunk_size and current:
            # Emit current chunk
            chunk_text = " ".join(current)
            if len(chunk_text) >= min_chunk:
                chunks.append({"chunk_index": chunk_idx, "chunk_text": chunk_text})
                chunk_idx += 1

            # Keep overlap: retain last N characters worth of sentences
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

    # Flush remaining
    if current:
        chunk_text = " ".join(current)
        if len(chunk_text) >= min_chunk:
            chunks.append({"chunk_index": chunk_idx, "chunk_text": chunk_text})

    return chunks
