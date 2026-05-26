"""Sentinel SDK — Drop-in replacement clients for OpenAI and Anthropic.

Usage::

    from sentinel import OpenAI

    client = OpenAI(
        sentinel_api_key="sk-sentinel-dev-000",
        sentinel_url="http://localhost:8000",
    )
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello!"}],
    )
"""

from __future__ import annotations

import anthropic as _anthropic
import openai as _openai

_DEFAULT_SENTINEL_URL = "http://localhost:8000"


class OpenAI(_openai.OpenAI):
    """Drop-in replacement for ``openai.OpenAI`` that routes through Sentinel.

    Args:
        sentinel_api_key: Your Sentinel project API key (e.g. ``sk-sentinel-dev-000``).
        sentinel_url: Base URL of the Sentinel gateway. Defaults to ``http://localhost:8000``.
        provider_api_key: Your actual OpenAI API key. If provided, it is sent
            via ``x-provider-key`` header so the gateway can forward it upstream.
        **kwargs: Additional arguments passed to ``openai.OpenAI``.
    """

    def __init__(
        self,
        *,
        sentinel_api_key: str = "sk-sentinel-dev-000",
        sentinel_url: str = _DEFAULT_SENTINEL_URL,
        provider_api_key: str | None = None,
        **kwargs,  # type: ignore[no-untyped-def]
    ) -> None:
        default_headers = kwargs.pop("default_headers", {}) or {}
        if provider_api_key:
            default_headers["x-provider-key"] = provider_api_key

        super().__init__(
            api_key=sentinel_api_key,
            base_url=f"{sentinel_url.rstrip('/')}/v1",
            default_headers=default_headers,
            **kwargs,
        )


class Anthropic(_anthropic.Anthropic):
    """Drop-in replacement for ``anthropic.Anthropic`` that routes through Sentinel.

    Args:
        sentinel_api_key: Your Sentinel project API key.
        sentinel_url: Base URL of the Sentinel gateway.
        provider_api_key: Your actual Anthropic API key.
        **kwargs: Additional arguments passed to ``anthropic.Anthropic``.
    """

    def __init__(
        self,
        *,
        sentinel_api_key: str = "sk-sentinel-dev-000",
        sentinel_url: str = _DEFAULT_SENTINEL_URL,
        provider_api_key: str | None = None,
        **kwargs,  # type: ignore[no-untyped-def]
    ) -> None:
        default_headers = kwargs.pop("default_headers", {}) or {}
        default_headers["x-sentinel-key"] = sentinel_api_key
        if provider_api_key:
            default_headers["x-provider-key"] = provider_api_key

        super().__init__(
            api_key=provider_api_key or "placeholder",
            base_url=f"{sentinel_url.rstrip('/')}/v1",
            default_headers=default_headers,
            **kwargs,
        )
