"""Local SQLite cache registry for triage resolutions.

Before running the diagnostic + remediation-planning LLM calls against an
incident, check whether an equivalent one has already been resolved: exact
match on the incident signature, or semantic match (cosine similarity over
local sentence-transformers embeddings) above
``settings.sentinel_cache_similarity_threshold``. A hit skips both LLM calls
entirely and replays the stored diagnosis + patch — the compliance gate
(app/agents/risk.py) still re-runs on every execution since it's a cheap,
deterministic, rule-based check rather than a model call.

Kept as a single dependency-light SQLite file (like the rest of Sentinel's
hand-rolled internals) rather than a vector database — the cache is small
enough that a linear cosine-similarity scan in Python is fast.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import sqlite3
import threading
from pathlib import Path
from typing import Any

from app.agents.embeddings import embed_text
from app.config import settings

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]

# Rough estimate of combined diagnostic+planner token spend a cache hit
# avoids. Simulated, not measured — see docstring above on why an exact
# per-resolution figure isn't worth tracking for a demo cost metric.
ESTIMATED_TOKENS_PER_RESOLUTION = 1500


class TriageCacheRegistry:
    """SQLite-backed exact + semantic cache of triage resolutions."""

    def __init__(self, db_path: str | None = None) -> None:
        path = Path(db_path or settings.sentinel_cache_db_path)
        if not path.is_absolute():
            path = REPO_ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.execute("PRAGMA busy_timeout = 5000")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cache_registry (
                log_hash TEXT PRIMARY KEY,
                raw_log TEXT NOT NULL,
                embedding TEXT NOT NULL,
                resolution_json TEXT NOT NULL,
                tokens_saved INTEGER NOT NULL DEFAULT 0,
                hit_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        self._conn.commit()

    @staticmethod
    def _hash(raw_log: str) -> str:
        return hashlib.md5(raw_log.strip().encode("utf-8"), usedforsecurity=False).hexdigest()

    def lookup(self, raw_log: str) -> tuple[dict[str, Any], int] | None:
        """Return ``(resolution, tokens_saved)`` on a cache hit, else ``None``.

        Checks an exact hash match first (<5ms, no embedding call needed),
        then falls back to a cosine-similarity scan over stored embeddings.
        """
        log_hash = self._hash(raw_log)
        with self._lock:
            row = self._conn.execute(
                "SELECT resolution_json, tokens_saved FROM cache_registry WHERE log_hash = ?",
                (log_hash,),
            ).fetchone()
        if row is not None:
            self._bump_hit(log_hash)
            logger.info("Triage cache exact hit")
            return json.loads(row[0]), row[1]

        query_vector = embed_text(raw_log)
        best_hash: str | None = None
        best_score = 0.0
        best_payload: tuple[str, int] | None = None
        with self._lock:
            rows = self._conn.execute(
                "SELECT log_hash, embedding, resolution_json, tokens_saved FROM cache_registry"
            ).fetchall()
        for cached_hash, embedding_json, resolution_json, tokens_saved in rows:
            score = _cosine_similarity(query_vector, json.loads(embedding_json))
            if score > best_score:
                best_hash, best_score, best_payload = cached_hash, score, (resolution_json, tokens_saved)

        if best_payload is not None and best_score >= settings.sentinel_cache_similarity_threshold:
            logger.info("Triage cache semantic hit (similarity=%.3f)", best_score)
            self._bump_hit(best_hash)  # type: ignore[arg-type]
            resolution_json, tokens_saved = best_payload
            return json.loads(resolution_json), tokens_saved

        return None

    def store(
        self, raw_log: str, resolution: dict[str, Any], *, tokens_saved: int = ESTIMATED_TOKENS_PER_RESOLUTION
    ) -> None:
        """Persist a resolved incident's diagnosis + patch for future reuse."""
        log_hash = self._hash(raw_log)
        embedding = embed_text(raw_log)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO cache_registry
                    (log_hash, raw_log, embedding, resolution_json, tokens_saved)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(log_hash) DO UPDATE SET
                    resolution_json = excluded.resolution_json,
                    tokens_saved = excluded.tokens_saved
                """,
                (log_hash, raw_log, json.dumps(embedding), json.dumps(resolution, default=str), tokens_saved),
            )
            self._conn.commit()

    def _bump_hit(self, log_hash: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE cache_registry SET hit_count = hit_count + 1 WHERE log_hash = ?", (log_hash,)
            )
            self._conn.commit()


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


_registry: TriageCacheRegistry | None = None


def get_cache_registry() -> TriageCacheRegistry:
    """Process-wide singleton — one SQLite connection per worker process."""
    global _registry
    if _registry is None:
        _registry = TriageCacheRegistry()
    return _registry
