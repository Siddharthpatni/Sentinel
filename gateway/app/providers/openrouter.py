"""OpenRouter provider adapter — OpenAI-compatible API at openrouter.ai."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx

from app.config import settings
from app.providers.base import BaseAdapter, ProviderResponse

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterAdapter(BaseAdapter):
    """Adapter for forwarding requests to OpenRouter (OpenAI-compatible surface)."""

    provider_name = "openrouter"

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=120.0)

    def _headers(self, api_key: str | None) -> dict[str, str]:
        if not api_key:
            raise RuntimeError("No OpenRouter credential configured. Add one at /settings/keys.")
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # OpenRouter recommends these for attribution / rate-limit tier:
            "HTTP-Referer": settings.openrouter_referer,
            "X-Title": settings.openrouter_title,
        }

    async def forward(
        self,
        request_body: dict,
        headers: dict[str, str],
    ) -> ProviderResponse:
        upstream_headers = self._headers(headers.get("x-provider-key"))
        body = {**request_body, "stream": False}

        try:
            resp = await self._client.post(
                OPENROUTER_BASE_URL,
                json=body,
                headers=upstream_headers,
            )
            resp_json = resp.json()
        except httpx.HTTPError as exc:
            logger.error("OpenRouter request failed: %s", exc)
            return ProviderResponse(
                status_code=502,
                body={"error": {"message": str(exc)}},
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
            error_message=(
                resp_json.get("error", {}).get("message")
                if resp.status_code >= 400
                else None
            ),
        )

    async def forward_stream(
        self,
        request_body: dict,
        headers: dict[str, str],
    ) -> AsyncIterator[bytes]:
        upstream_headers = self._headers(headers.get("x-provider-key"))
        body = {**request_body, "stream": True, "stream_options": {"include_usage": True}}

        async with self._client.stream(
            "POST",
            OPENROUTER_BASE_URL,
            json=body,
            headers=upstream_headers,
        ) as resp:
            async for line in resp.aiter_lines():
                if line:
                    yield (line + "\n\n").encode("utf-8")
