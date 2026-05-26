"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration for the Sentinel gateway.

    All values can be overridden via environment variables or a ``.env`` file
    located in the project root.
    """

    # --- Database ---
    database_url: str = "postgresql+asyncpg://sentinel:sentinel@postgres:5432/sentinel"
    database_url_sync: str = "postgresql+psycopg2://sentinel:sentinel@postgres:5432/sentinel"

    # --- Redis / Celery ---
    redis_url: str = "redis://redis:6379/0"

    # --- LLM Provider Keys ---
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # --- Sentinel ---
    default_project_api_key: str = "sk-sentinel-dev-000"
    default_project_name: str = "default"

    # --- Server ---
    gateway_host: str = "0.0.0.0"
    gateway_port: int = 8000
    log_level: str = "info"

    # --- Streaming ---
    max_stream_buffer_bytes: int = 10 * 1024 * 1024  # 10 MB cap

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
