"""Index the Sentinel codebase into `code_chunks` for triage RAG retrieval.

Chunks gateway/app and dashboard source files, embeds anything new or
changed locally via sentence-transformers (app/agents/embeddings.py, no
network call), and upserts into Postgres (pgvector). Safe to re-run —
unchanged chunks are skipped by content hash.

Prereqs
-------
    docker compose up -d postgres redis
    cd gateway && alembic -c app/db/migrations/alembic.ini upgrade head   # or: make demo

Run
---
    python scripts/index_codebase.py
    # or: make reindex
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gateway"))

from app.agents.rag import reindex_codebase  # noqa: E402
from app.db.session import get_sync_session  # noqa: E402


def main() -> None:
    session = get_sync_session()
    try:
        summary = reindex_codebase(session)
        print(
            f"Indexed {summary['scanned_files']} files: "
            f"{summary['chunks_embedded']} chunks embedded, "
            f"{summary['chunks_removed']} stale chunks removed."
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
