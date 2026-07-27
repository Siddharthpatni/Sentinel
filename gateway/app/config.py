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
    openrouter_api_key: str = ""

    # OpenRouter attribution headers (recommended for correct rate-limit tier)
    openrouter_referer: str = "https://github.com/Siddharthpatni/Sentinel"
    openrouter_title: str = "Sentinel"

    # --- Ollama (local, offline LLM) ---
    # Host default assumes `ollama serve` running natively on the machine.
    # docker-compose.yml overrides this to http://host.docker.internal:11434
    # so the containerized gateway/worker can reach the host's Ollama.
    ollama_base_url: str = "http://localhost:11434"

    # --- Sentinel ---
    default_project_api_key: str = "sk-sentinel-dev-000"
    default_project_name: str = "default"

    # Fernet master key for encrypting per-project provider credentials at rest.
    # Generate one with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # The default below is a dev-only key — REPLACE in production.
    sentinel_encryption_key: str = "WAjHM_cvg60vuFrpOGE7qX-m2tCB5raU3w0j6QxrfJA="

    # JWT signing secret for dashboard session cookies. Replace in production.
    sentinel_jwt_secret: str = "dev-jwt-secret-change-me-in-prod"
    sentinel_jwt_ttl_seconds: int = 60 * 60 * 24 * 7  # 7 days
    sentinel_cookie_name: str = "sentinel_session"

    # --- Server ---
    gateway_host: str = "0.0.0.0"
    gateway_port: int = 8000
    log_level: str = "info"

    # --- Streaming ---
    max_stream_buffer_bytes: int = 10 * 1024 * 1024  # 10 MB cap

    # --- Autonomous Incident Triage ---
    # `ollama/` prefix routes through the local Ollama adapter (see
    # app/providers/ollama.py) — qwen2.5-coder:7b is already pulled locally
    # and code-focused, so triage runs fully offline with $0 marginal cost.
    # Ollama tags always need an explicit size suffix (`ollama list`); there
    # is no bare "qwen2.5-coder" tag.
    triage_llm_model: str = "ollama/qwen2.5-coder:7b"
    # sentence-transformers model name, loaded locally (app/agents/embeddings.py)
    triage_embedding_model: str = "all-MiniLM-L6-v2"
    triage_auto_approve_low_risk: bool = True

    # --- Local Cache Registry ---
    # Exact-hash + semantic (cosine similarity) cache of triage resolutions,
    # keyed off the incident signature (see app/agents/triage.py). A hit
    # skips both the diagnostic and remediation-planning LLM calls.
    sentinel_cache_enabled: bool = True
    sentinel_cache_db_path: str = ".sentinel/cache/sentinel_cache.db"
    sentinel_cache_similarity_threshold: float = 0.88

    # GitHub PR creation for approved fixes. Execution falls back to writing
    # a local .sentinel/patches/ artifact when github_token is unset — the
    # feature works out of the box on a fresh clone without secrets.
    github_token: str = ""
    triage_github_repo: str = ""  # "owner/repo"
    triage_github_base_branch: str = "main"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
