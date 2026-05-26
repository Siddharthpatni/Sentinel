"""Unit tests for the OpenAI provider adapter using respx mocks."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.providers.openai import OPENAI_BASE_URL, OpenAIAdapter


@pytest.fixture
def adapter() -> OpenAIAdapter:
    return OpenAIAdapter()


class TestOpenAIAdapterForward:
    """Tests for the non-streaming OpenAI adapter."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_successful_completion(self, adapter: OpenAIAdapter) -> None:
        """Should parse a successful chat completion response."""
        mock_response = {
            "id": "chatcmpl-abc123",
            "object": "chat.completion",
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }
        respx.post(OPENAI_BASE_URL).mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        result = await adapter.forward(
            {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Hi"}]},
            {"x-provider-key": "sk-test"},
        )

        assert result.status_code == 200
        assert result.prompt_tokens == 10
        assert result.completion_tokens == 5
        assert result.model == "gpt-4o-mini"
        assert result.error_message is None

    @respx.mock
    @pytest.mark.asyncio
    async def test_error_response(self, adapter: OpenAIAdapter) -> None:
        """Should capture error messages from failed responses."""
        mock_response = {
            "error": {
                "message": "Invalid API key",
                "type": "invalid_request_error",
            }
        }
        respx.post(OPENAI_BASE_URL).mock(
            return_value=httpx.Response(401, json=mock_response)
        )

        result = await adapter.forward(
            {"model": "gpt-4o", "messages": []},
            {"x-provider-key": "sk-bad-key"},
        )

        assert result.status_code == 401
        assert result.error_message == "Invalid API key"
