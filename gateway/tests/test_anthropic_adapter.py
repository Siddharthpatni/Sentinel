"""Unit tests for the Anthropic provider adapter using respx mocks."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.providers.anthropic import ANTHROPIC_BASE_URL, AnthropicAdapter


@pytest.fixture
def adapter() -> AnthropicAdapter:
    return AnthropicAdapter()


class TestAnthropicAdapterForward:
    """Tests for the non-streaming Anthropic adapter."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_successful_message(self, adapter: AnthropicAdapter) -> None:
        """Should parse a successful Anthropic messages response."""
        mock_response = {
            "id": "msg_abc123",
            "type": "message",
            "role": "assistant",
            "model": "claude-3-5-sonnet-20241022",
            "content": [{"type": "text", "text": "Hello!"}],
            "usage": {"input_tokens": 15, "output_tokens": 8},
            "stop_reason": "end_turn",
        }
        respx.post(ANTHROPIC_BASE_URL).mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        result = await adapter.forward(
            {
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 100,
                "messages": [{"role": "user", "content": "Hi"}],
            },
            {"x-provider-key": "sk-ant-test"},
        )

        assert result.status_code == 200
        assert result.prompt_tokens == 15
        assert result.completion_tokens == 8
        assert result.model == "claude-3-5-sonnet-20241022"
        assert result.error_message is None

    @respx.mock
    @pytest.mark.asyncio
    async def test_error_response(self, adapter: AnthropicAdapter) -> None:
        """Should capture Anthropic error messages."""
        mock_response = {
            "type": "error",
            "error": {
                "type": "authentication_error",
                "message": "invalid x-api-key",
            },
        }
        respx.post(ANTHROPIC_BASE_URL).mock(
            return_value=httpx.Response(401, json=mock_response)
        )

        result = await adapter.forward(
            {
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 100,
                "messages": [],
            },
            {"x-provider-key": "sk-ant-bad"},
        )

        assert result.status_code == 401
        assert result.error_message == "invalid x-api-key"
