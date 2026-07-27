"""Ollama provider adapter — forwards requests to a local Ollama server.

Ollama exposes an OpenAI-compatible endpoint (``/v1/chat/completions``), so
this adapter is a thin variant of :class:`OpenAIAdapter` with two
differences: no API key is required, and connection failures get a
message pointing at ``ollama serve`` instead of a billing page.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx

from app.config import settings
from app.providers.base import BaseAdapter, ProviderResponse, strip_sentinel_meta

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


class OllamaAdapter(BaseAdapter):
    """Adapter for forwarding requests to a local Ollama instance."""

    provider_name = "ollama"

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=180.0)

    def _url(self) -> str:
        return f"{settings.ollama_base_url.rstrip('/')}/v1/chat/completions"

    async def forward(
        self,
        request_body: dict,
        headers: dict[str, str],
    ) -> ProviderResponse:
        """Forward a non-streaming request to Ollama."""
        body = {**strip_sentinel_meta(request_body), "stream": False}

        try:
            resp = await self._client.post(self._url(), json=body)
            resp_json = resp.json()
        except httpx.HTTPError as exc:
            logger.error("Ollama request failed: %s", exc)
            return ProviderResponse(
                status_code=502,
                body={
                    "error": {
                        "message": (
                            f"Could not reach Ollama at {settings.ollama_base_url} — "
                            f"is `ollama serve` running? ({exc})"
                        )
                    }
                },
                error_message=str(exc),
            )

        usage = resp_json.get("usage", {})
        model = resp_json.get("model", request_body.get("model", "unknown"))

        return ProviderResponse(
            status_code=resp.status_code,
            body=resp_json,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            model=model,
            error_message=resp_json.get("error", {}).get("message") if resp.status_code >= 400 else None,
        )

    async def forward_stream(
        self,
        request_body: dict,
        headers: dict[str, str],
    ) -> AsyncIterator[bytes]:
        """Forward a streaming request to Ollama, yielding SSE chunks."""
        body = {**strip_sentinel_meta(request_body), "stream": True}

        async with self._client.stream("POST", self._url(), json=body) as resp:
            async for line in resp.aiter_lines():
                if line:
                    yield (line + "\n\n").encode("utf-8")
