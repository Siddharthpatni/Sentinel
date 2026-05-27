"""Tests for the keyvault module (encryption + redaction + fingerprint)."""

from __future__ import annotations

import pytest

from app.security.keyvault import (
    KeyVaultError,
    decrypt,
    encrypt,
    fingerprint,
    redact,
    redact_event,
)


def test_encrypt_decrypt_roundtrip():
    plaintext = "sk-proj-abcdef1234567890ABCDEF1234567890"
    token = encrypt(plaintext)
    assert isinstance(token, bytes)
    assert plaintext.encode() not in token  # plaintext must not appear in ciphertext
    assert decrypt(token) == plaintext


def test_encrypt_rejects_empty():
    with pytest.raises(KeyVaultError):
        encrypt("")


def test_decrypt_rejects_garbage():
    with pytest.raises(KeyVaultError):
        decrypt(b"not-a-valid-fernet-token")


def test_fingerprint_long_key():
    assert fingerprint("sk-proj-abcdef1234567890") == "sk-p…7890"


def test_fingerprint_short_key_is_fully_masked():
    assert fingerprint("short") == "•••••"


def test_fingerprint_empty():
    assert fingerprint("") == ""


def test_redact_openai_pattern():
    msg = "calling provider with key sk-proj-abcdef1234567890ABCDEF1234567890"
    out = redact(msg)
    assert "sk-proj-abcdef1234567890ABCDEF1234567890" not in out
    assert "sk-p…7890" in out


def test_redact_anthropic_pattern():
    msg = "key=sk-ant-abcdef1234567890ABCDEF12345678abc"
    out = redact(msg)
    assert "sk-ant-abcdef1234567890ABCDEF12345678abc" not in out


def test_redact_gemini_pattern():
    msg = "Authorization: Bearer AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q"
    out = redact(msg)
    assert "AIzaSy" not in out or "…" in out


def test_redact_leaves_non_secret_text_alone():
    msg = "This is a normal log message with no secrets."
    assert redact(msg) == msg


def test_redact_event_processor_walks_dict():
    ev = {
        "event": "outgoing request to sk-proj-abcdef1234567890ABCDEF1234567890",
        "url": "https://api.openai.com/v1/chat",
        "headers": {"authorization": "Bearer sk-proj-abcdef1234567890ABCDEF1234567890"},
    }
    redacted = redact_event(None, "info", ev)
    assert "sk-proj-abcdef1234567890ABCDEF1234567890" not in redacted["event"]
    assert "sk-proj-abcdef1234567890ABCDEF1234567890" not in redacted["headers"]["authorization"]
    assert redacted["url"] == "https://api.openai.com/v1/chat"  # untouched
