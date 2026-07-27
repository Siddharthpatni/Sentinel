"""Local embedding model — sentence-transformers, no network calls.

Replaces the OpenAI embeddings endpoint previously used by ``app.agents.rag``
and the triage cache registry. The model loads once per process (first call
downloads its weights from the HuggingFace hub if not already cached under
``~/.cache/huggingface``; every call after that is fully offline) and runs
on CPU, which is what makes RAG retrieval and the cache registry work with
no per-request API cost.
"""

from __future__ import annotations

from functools import lru_cache

from app.config import settings

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2's native output size


@lru_cache(maxsize=1)
def _model():  # type: ignore[no-untyped-def]
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.triage_embedding_model)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts with the local sentence-transformers model."""
    if not texts:
        return []
    vectors = _model().encode(texts, convert_to_numpy=True, normalize_embeddings=False)
    return [vector.tolist() for vector in vectors]


def embed_text(text: str) -> list[float]:
    """Embed a single text. Convenience wrapper around :func:`embed_texts`."""
    [vector] = embed_texts([text])
    return vector
