"""Unit tests for the gateway config module."""

from __future__ import annotations

from app.config import Settings


class TestSettings:
    """Tests for the Settings configuration class."""

    def test_defaults(self) -> None:
        """Default values should be sensible."""
        s = Settings(
            _env_file=None,  # type: ignore[call-arg]
        )
        assert s.gateway_port == 8000
        assert s.default_project_api_key == "sk-sentinel-dev-000"
        assert s.max_stream_buffer_bytes == 10 * 1024 * 1024
        assert "asyncpg" in s.database_url

    def test_custom_values(self) -> None:
        """Should accept custom values."""
        s = Settings(
            gateway_port=9000,
            openai_api_key="sk-test",
            _env_file=None,  # type: ignore[call-arg]
        )
        assert s.gateway_port == 9000
        assert s.openai_api_key == "sk-test"
