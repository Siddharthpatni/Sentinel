"""Symmetric encryption + redaction for project-scoped provider credentials.

Encryption uses Fernet (cryptography library) with a single master key
configured via :pyattr:`app.config.Settings.sentinel_encryption_key`. The
plaintext API key never leaves this module — callers store the ciphertext
in the ``provider_credentials`` table and only decrypt at the moment of
forwarding a request to the upstream LLM provider.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy import select

from app.config import settings


class KeyVaultError(RuntimeError):
    """Raised when encryption / decryption fails."""


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    try:
        return Fernet(settings.sentinel_encryption_key.encode())
    except (ValueError, TypeError) as exc:
        raise KeyVaultError(
            "SENTINEL_ENCRYPTION_KEY is not a valid Fernet key — generate one with "
            "`python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`"
        ) from exc


def encrypt(plaintext: str) -> bytes:
    """Encrypt an API key for storage. Output is opaque ciphertext bytes."""
    if not plaintext:
        raise KeyVaultError("Refusing to encrypt empty value")
    return _fernet().encrypt(plaintext.encode("utf-8"))


def decrypt(ciphertext: bytes) -> str:
    """Decrypt a previously-encrypted API key."""
    try:
        return _fernet().decrypt(ciphertext).decode("utf-8")
    except InvalidToken as exc:
        raise KeyVaultError(
            "Ciphertext could not be decrypted — has SENTINEL_ENCRYPTION_KEY changed?"
        ) from exc


def fingerprint(plaintext: str) -> str:
    """Short display-only identifier: first 4 + ``…`` + last 4 chars.

    Safe to log and show in the dashboard. For very short keys returns
    a masked variant so we never accidentally render the full secret.
    """
    if not plaintext:
        return ""
    if len(plaintext) <= 10:
        return "•" * len(plaintext)
    return f"{plaintext[:4]}…{plaintext[-4:]}"


# ──────────────────────────────────────────────────────────────────────
# Redaction
# ──────────────────────────────────────────────────────────────────────

# Catches common LLM-provider key shapes anywhere they slip into a log line.
# We deliberately accept some false positives — better to over-redact than
# leak a key. Patterns are conservative on length to avoid matching ordinary
# words that start with the same characters.
_API_KEY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),      # Anthropic
    re.compile(r"sk-or-[A-Za-z0-9_\-]{20,}"),       # OpenRouter
    re.compile(r"sk-proj-[A-Za-z0-9_\-]{20,}"),     # OpenAI project keys
    re.compile(r"sk-[A-Za-z0-9]{20,}"),             # Generic OpenAI / fallback
    re.compile(r"AIza[A-Za-z0-9_\-]{30,}"),         # Google / Gemini
    re.compile(r"xoxb-[A-Za-z0-9\-]{20,}"),         # Slack bot
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),            # GitHub PAT
]


def redact(value: str) -> str:
    """Replace any API-key-shaped substring with a fingerprint placeholder."""
    if not value:
        return value
    out = value
    for pat in _API_KEY_PATTERNS:
        out = pat.sub(lambda m: fingerprint(m.group(0)), out)
    return out


def redact_event(_logger: object, _method: str, event_dict: dict) -> dict:
    """structlog processor: redact every string value in the event dict."""
    for k, v in list(event_dict.items()):
        if isinstance(v, str):
            event_dict[k] = redact(v)
        elif isinstance(v, dict):
            event_dict[k] = {
                ik: redact(iv) if isinstance(iv, str) else iv for ik, iv in v.items()
            }
    return event_dict


# ──────────────────────────────────────────────────────────────────────
# Per-project resolution
# ──────────────────────────────────────────────────────────────────────

_ENV_FALLBACK = {
    "openai": lambda: settings.openai_api_key,
    "anthropic": lambda: settings.anthropic_api_key,
    "openrouter": lambda: settings.openrouter_api_key,
    "gemini": lambda: "",  # no env var yet — extend Settings if needed
}


async def get_provider_key(project_id: uuid.UUID, provider: str) -> str:
    """Resolve an API key for ``provider`` scoped to ``project_id``.

    Order of resolution:
      1. Active ``provider_credentials`` row for this project + provider.
         Decrypt and return; opportunistically bump ``last_used_at``.
      2. Env-var fallback from :class:`Settings`.
      3. Raise :class:`HTTPException(402)` with a helpful message.
    """
    # Local imports keep the module importable from places where the ORM
    # session module hasn't been initialised yet (tests, migrations).
    from app.db.models import ProviderCredential
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ProviderCredential)
            .where(
                ProviderCredential.project_id == project_id,
                ProviderCredential.provider == provider,
                ProviderCredential.is_active.is_(True),
            )
            .order_by(ProviderCredential.created_at.desc())
            .limit(1)
        )
        cred = result.scalar_one_or_none()
        if cred is not None:
            plaintext = decrypt(cred.encrypted_key)
            cred.last_used_at = datetime.now(UTC)
            await session.commit()
            return plaintext

    env_key = _ENV_FALLBACK.get(provider, lambda: "")()
    if env_key:
        return env_key

    raise HTTPException(
        status_code=402,
        detail=(
            f"No credentials configured for provider {provider!r}. "
            f"Add one at /settings/keys."
        ),
    )
