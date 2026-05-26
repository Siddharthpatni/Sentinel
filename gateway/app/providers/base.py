"""Abstract base adapter for LLM provider integrations."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass
class ProviderResponse:
    """Structured response from an LLM provider forward call."""

    status_code: int = 200
    body: dict = field(default_factory=dict)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    error_message: str | None = None


class BaseAdapter(abc.ABC):
    """Interface that all provider adapters must implement."""

    provider_name: str = "unknown"

    @abc.abstractmethod
    async def forward(
        self,
        request_body: dict,
        headers: dict[str, str],
    ) -> ProviderResponse:
        """Forward a non-streaming request to the upstream provider.

        Returns a :class:`ProviderResponse` containing the full body and
        parsed token usage.
        """
        ...

    @abc.abstractmethod
    async def forward_stream(
        self,
        request_body: dict,
        headers: dict[str, str],
    ) -> AsyncIterator[bytes]:
        """Forward a streaming request and yield raw SSE chunks.

        The caller is responsible for teeing the bytes to the HTTP client
        and buffering them for trace recording.
        """
        ...
        # Make this an async generator
        yield b""  # pragma: no cover
