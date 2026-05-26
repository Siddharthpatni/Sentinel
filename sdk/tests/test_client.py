"""Tests for the Sentinel SDK client wrappers."""

from __future__ import annotations

from sentinel.client import Anthropic, OpenAI


class TestOpenAIClient:
    """Tests for the Sentinel OpenAI wrapper."""

    def test_default_base_url(self) -> None:
        """Should set base URL to the Sentinel gateway."""
        client = OpenAI(sentinel_api_key="sk-test")
        assert "localhost:8000" in str(client.base_url)

    def test_custom_sentinel_url(self) -> None:
        """Should respect a custom Sentinel URL."""
        client = OpenAI(
            sentinel_api_key="sk-test",
            sentinel_url="http://sentinel.example.com:9000",
        )
        assert "sentinel.example.com:9000" in str(client.base_url)

    def test_api_key_is_sentinel_key(self) -> None:
        """The OpenAI api_key should be set to the Sentinel key."""
        client = OpenAI(sentinel_api_key="sk-sentinel-abc")
        assert client.api_key == "sk-sentinel-abc"

    def test_provider_key_in_headers(self) -> None:
        """Provider key should be passed via default headers."""
        client = OpenAI(
            sentinel_api_key="sk-test",
            provider_api_key="sk-openai-real",
        )
        assert client._custom_headers.get("x-provider-key") == "sk-openai-real"


class TestAnthropicClient:
    """Tests for the Sentinel Anthropic wrapper."""

    def test_default_base_url(self) -> None:
        """Should set base URL to the Sentinel gateway."""
        client = Anthropic(sentinel_api_key="sk-test")
        assert "localhost:8000" in str(client.base_url)

    def test_sentinel_key_in_headers(self) -> None:
        """Sentinel key should be in default headers."""
        client = Anthropic(sentinel_api_key="sk-sentinel-abc")
        assert client._custom_headers.get("x-sentinel-key") == "sk-sentinel-abc"
