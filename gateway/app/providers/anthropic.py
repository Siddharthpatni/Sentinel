"""Anthropic provider adapter — forwards requests to api.anthropic.com."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx

from app.providers.base import BaseAdapter, ProviderResponse, strip_sentinel_meta

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1/messages"


class AnthropicAdapter(BaseAdapter):
    """Adapter for forwarding requests to Anthropic's messages API."""

    provider_name = "anthropic"

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=120.0)

    async def forward(
        self,
        request_body: dict,
        headers: dict[str, str],
    ) -> ProviderResponse:
        """Forward a non-streaming request to Anthropic."""
        api_key = headers.get("x-provider-key", "")
        if not api_key:
            return ProviderResponse(
                status_code=402,
                body={"error": {"message": "No Anthropic credential configured. Add one at /settings/keys."}},
                error_message="missing credential",
            )
        upstream_headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        body = {**strip_sentinel_meta(request_body), "stream": False}

        try:
            resp = await self._client.post(
                ANTHROPIC_BASE_URL,
                json=body,
                headers=upstream_headers,
            )
            resp_json = resp.json()
        except httpx.HTTPError as exc:
            logger.error("Anthropic request failed: %s", exc)
            return ProviderResponse(
                status_code=502,
                body={"error": {"message": str(exc)}},
                error_message=str(exc),
            )

        # Parse Anthropic usage format
        usage = resp_json.get("usage", {})
        model = resp_json.get("model", request_body.get("model", "unknown"))

        return ProviderResponse(
            status_code=resp.status_code,
            body=resp_json,
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
            model=model,
            error_message=resp_json.get("error", {}).get("message") if resp.status_code >= 400 else None,
        )

    async def forward_stream(
        self,
        request_body: dict,
        headers: dict[str, str],
    ) -> AsyncIterator[bytes]:
        """Forward a streaming request to Anthropic, yielding SSE chunks."""
        api_key = headers.get("x-provider-key", "")
        if not api_key:
            raise RuntimeError("No Anthropic credential configured. Add one at /settings/keys.")
        upstream_headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        body = {**strip_sentinel_meta(request_body), "stream": True}

        async with self._client.stream(
            "POST",
            ANTHROPIC_BASE_URL,
            json=body,
            headers=upstream_headers,
        ) as resp:
            async for line in resp.aiter_lines():
                if line:
                    yield (line + "\n\n").encode("utf-8")
