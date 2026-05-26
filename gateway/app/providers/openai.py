"""OpenAI provider adapter — forwards requests to api.openai.com."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx

from app.config import settings
from app.providers.base import BaseAdapter, ProviderResponse

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

OPENAI_BASE_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIAdapter(BaseAdapter):
    """Adapter for forwarding requests to OpenAI's chat completions API."""

    provider_name = "openai"

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=120.0)

    async def forward(
        self,
        request_body: dict,
        headers: dict[str, str],
    ) -> ProviderResponse:
        """Forward a non-streaming request to OpenAI."""
        upstream_headers = {
            "Authorization": f"Bearer {headers.get('x-provider-key', settings.openai_api_key)}",
            "Content-Type": "application/json",
        }

        # Ensure stream is off
        body = {**request_body, "stream": False}

        try:
            resp = await self._client.post(
                OPENAI_BASE_URL,
                json=body,
                headers=upstream_headers,
            )
            resp_json = resp.json()
        except httpx.HTTPError as exc:
            logger.error("OpenAI request failed: %s", exc)
            return ProviderResponse(
                status_code=502,
                body={"error": {"message": str(exc)}},
                error_message=str(exc),
            )

        # Parse usage
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
        """Forward a streaming request to OpenAI, yielding SSE chunks."""
        upstream_headers = {
            "Authorization": f"Bearer {headers.get('x-provider-key', settings.openai_api_key)}",
            "Content-Type": "application/json",
        }

        body = {**request_body, "stream": True, "stream_options": {"include_usage": True}}

        async with self._client.stream(
            "POST",
            OPENAI_BASE_URL,
            json=body,
            headers=upstream_headers,
        ) as resp:
            async for line in resp.aiter_lines():
                if line:
                    yield (line + "\n\n").encode("utf-8")
