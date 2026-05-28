# Symmetric encryption with Fernet (and why we use it for API keys)

Sentinel stores per-project provider API keys (BYOK) in the database.
We never want them on disk in plaintext, but we do need to decrypt them
on every forwarded request. That makes this a **symmetric encryption**
problem, not a password-hashing one — we need to get the plaintext
back, not just check a hash.

## What Fernet is

Fernet is a recipe for symmetric encryption, defined in the `cryptography`
Python package. A Fernet token is roughly:

```
Version  ‖  Timestamp  ‖  IV  ‖  Ciphertext  ‖  HMAC
```

Concretely, it uses:

- **AES-128-CBC** for confidentiality, with a fresh random IV per
  encryption (so encrypting the same plaintext twice produces two
  different ciphertexts).
- **HMAC-SHA256** for authentication, so tampered ciphertext is
  rejected at decrypt time with a clear `InvalidToken` error rather
  than returning garbage bytes.
- A 32-byte key, URL-safe base64 encoded into 44 ASCII characters.

The "recipe" framing matters: you don't pick algorithms, modes, or
padding yourself. Fernet picked them for you, and they're known to
compose safely. That's the whole appeal.

## Why not just AES directly?

You could call `cryptography.hazmat.primitives.ciphers` and assemble
AES-GCM yourself. People do this and then:

- forget to randomize the IV (catastrophic for CBC, nonce-reuse
  catastrophic for GCM),
- skip authentication and ship encrypt-then-nothing,
- pick CBC without a MAC and become vulnerable to padding oracles,
- store the IV in the wrong place and break decryption on rotation.

Fernet exists to make these mistakes impossible without explicitly
opting out. The cost is that you can't pick the mode — and for a
secrets-at-rest workload, picking the mode wasn't adding value anyway.

## Why not password hashing (bcrypt / argon2)?

Password hashes are one-way by design. You can verify "did the user
type this password?" but you can't recover the plaintext to forward
upstream. We need the plaintext at request time, so a hash is the
wrong primitive entirely.

The trap to avoid: "I'll hash the key and then look it up." You can't
look up by hash without also storing it elsewhere as plaintext to do
the lookup — at which point the hash is doing no work.

## Why not asymmetric (RSA, age, NaCl boxes)?

Asymmetric encryption is for the case where the encryptor and
decryptor are different parties. Here, both ends are the gateway
process. There's no key-distribution problem to solve, so introducing
public/private keypairs would add operational burden (key rotation,
revocation, exposure of public keys) without security gain.

## How Sentinel uses it

The full flow lives in `gateway/app/security/keyvault.py`:

```python
from cryptography.fernet import Fernet, InvalidToken
from functools import lru_cache

@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    return Fernet(settings.sentinel_encryption_key.encode())

def encrypt(plaintext: str) -> bytes:
    return _fernet().encrypt(plaintext.encode("utf-8"))

def decrypt(ciphertext: bytes) -> str:
    try:
        return _fernet().decrypt(ciphertext).decode("utf-8")
    except InvalidToken as exc:
        raise KeyVaultError("...") from exc
```

Three concrete choices worth noting:

**1. Single master key in `Settings`.** The Fernet key itself lives in
`SENTINEL_ENCRYPTION_KEY` (an env var on production, a default in dev).
Rotation = re-encrypt all `provider_credentials` rows under the new
key in a single migration. We trade rotation ergonomics for one fewer
moving part — no KMS, no DEK/KEK hierarchy. For a self-hosted
proxy this is the right trade.

**2. `lru_cache(maxsize=1)` on the constructor.** Fernet's
constructor is cheap but not free (it base64-decodes and validates
the key). Caching makes encrypt/decrypt a single hash-table lookup on
the hot path.

**3. We store the ciphertext as `LargeBinary` (bytes), not text.**
Fernet outputs URL-safe base64, so it *would* fit in a `TEXT` column —
but treating it as opaque bytes makes the contract honest. The
database has no business reading the contents.

## Generating a key for production

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set the output as `SENTINEL_ENCRYPTION_KEY`. **Do not** check the
production key into version control or share it across environments —
the same key in dev and prod means a dev with read access to the
production database can decrypt everything.

## What Fernet does NOT do

- **Key rotation.** You have to re-encrypt rows yourself. Fernet
  supports a `MultiFernet` for read-time fallback to old keys during a
  rotation window, which is the right pattern if you need zero-downtime
  rotation.
- **Per-row isolation.** All rows are encrypted under the same master
  key. If you need cryptographic isolation per project, you want a
  KEK/DEK scheme on top.
- **HSM integration.** The master key sits in process memory. For a
  threat model that includes process-memory dumps, swap Fernet for a
  KMS client (AWS KMS, GCP KMS, HashiCorp Vault transit).

For Sentinel's threat model — protect against accidental log/dump
leaks and casual database access — Fernet is the right floor.
