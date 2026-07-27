"""Codebase RAG: chunking, embedding, indexing, and retrieval for triage diagnosis.

Chunks are plain sliding-window slices of source files — no AST parsing, kept
deliberately simple like the rest of Sentinel's hand-rolled internals.
Embeddings are computed locally via ``app.agents.embeddings`` (sentence-
transformers) — no network call, no per-request cost.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.agents.embeddings import embed_texts
from app.db.models import CodeChunk

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
INDEXED_ROOTS = ("gateway/app", "dashboard")
INDEXED_SUFFIXES = {".py", ".ts", ".tsx"}
EXCLUDED_DIR_NAMES = {"node_modules", ".venv", "__pycache__", ".next", "migrations"}

WINDOW_LINES = 80
OVERLAP_LINES = 10


def iter_source_files() -> list[Path]:
    """Enumerate indexable source files under the configured repo roots."""
    files: list[Path] = []
    for rel_root in INDEXED_ROOTS:
        root = REPO_ROOT / rel_root
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in INDEXED_SUFFIXES:
                continue
            if EXCLUDED_DIR_NAMES & set(path.relative_to(REPO_ROOT).parts):
                continue
            files.append(path)
    return files


def chunk_file(path: Path) -> list[dict[str, Any]]:
    """Split one file into overlapping line-window chunks.

    Returns dicts with ``start_line``/``end_line`` (1-indexed, inclusive),
    ``content``, and ``content_hash`` (sha256 of ``content``).
    """
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True)
    except OSError as exc:
        logger.warning("Failed to read %s for indexing: %s", path, exc)
        return []
    if not lines:
        return []

    step = max(WINDOW_LINES - OVERLAP_LINES, 1)
    chunks: list[dict[str, Any]] = []
    start = 0
    while start < len(lines):
        end = min(start + WINDOW_LINES, len(lines))
        content = "".join(lines[start:end])
        if content.strip():
            chunks.append(
                {
                    "start_line": start + 1,
                    "end_line": end,
                    "content": content,
                    "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                }
            )
        if end == len(lines):
            break
        start += step
    return chunks


def _upsert_chunk(session: Session, meta: dict[str, Any], embedding: list[float]) -> None:
    existing = session.execute(
        select(CodeChunk).where(
            CodeChunk.file_path == meta["file_path"],
            CodeChunk.start_line == meta["start_line"],
            CodeChunk.end_line == meta["end_line"],
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.content = meta["content"]
        existing.content_hash = meta["content_hash"]
        existing.embedding = embedding
    else:
        session.add(
            CodeChunk(
                file_path=meta["file_path"],
                start_line=meta["start_line"],
                end_line=meta["end_line"],
                content=meta["content"],
                content_hash=meta["content_hash"],
                embedding=embedding,
            )
        )


def reindex_codebase(session: Session, *, batch_size: int = 64) -> dict[str, int]:
    """Re-embed changed chunks and drop stale ones. Caller commits.

    Safe to run repeatedly (``make reindex``) — chunks whose content hash is
    unchanged are skipped, so incremental re-indexing only pays for what
    actually moved.
    """
    existing_hashes = {
        (row.file_path, row.start_line, row.end_line): row.content_hash
        for row in session.execute(select(CodeChunk)).scalars()
    }
    seen_keys: set[tuple[str, int, int]] = set()
    pending_texts: list[str] = []
    pending_meta: list[dict[str, Any]] = []
    embedded = 0
    files = iter_source_files()

    def _flush() -> None:
        nonlocal embedded, pending_texts, pending_meta
        if not pending_texts:
            return
        vectors = embed_texts(pending_texts)
        for meta, vector in zip(pending_meta, vectors, strict=True):
            _upsert_chunk(session, meta, vector)
        embedded += len(pending_texts)
        pending_texts, pending_meta = [], []

    for path in files:
        rel_path = str(path.relative_to(REPO_ROOT))
        for chunk in chunk_file(path):
            key = (rel_path, chunk["start_line"], chunk["end_line"])
            seen_keys.add(key)
            if existing_hashes.get(key) == chunk["content_hash"]:
                continue
            pending_meta.append({**chunk, "file_path": rel_path})
            pending_texts.append(chunk["content"])
            if len(pending_texts) >= batch_size:
                _flush()
    _flush()

    stale_keys = [key for key in existing_hashes if key not in seen_keys]
    for file_path, start_line, end_line in stale_keys:
        row = session.execute(
            select(CodeChunk).where(
                CodeChunk.file_path == file_path,
                CodeChunk.start_line == start_line,
                CodeChunk.end_line == end_line,
            )
        ).scalar_one_or_none()
        if row is not None:
            session.delete(row)

    session.commit()
    return {
        "scanned_files": len(files),
        "chunks_embedded": embedded,
        "chunks_removed": len(stale_keys),
    }


def retrieve_relevant_chunks(session: Session, query_text: str, k: int = 8) -> list[CodeChunk]:
    """Embed ``query_text`` and return the ``k`` nearest code chunks by cosine distance.

    Postgres-only (uses the pgvector ``<=>`` operator via the ORM comparator);
    never exercised against the SQLite test fallback.
    """
    [query_vector] = embed_texts([query_text])
    stmt = (
        select(CodeChunk)
        .order_by(CodeChunk.embedding.cosine_distance(query_vector))
        .limit(k)
    )
    return list(session.execute(stmt).scalars().all())
