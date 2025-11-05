"""Type definitions for platform challenge SDK."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SigningSession:
    public_key: bytes
    secret_key: bytes
    session_token: str | None = None
    expires_at: int | None = None
    aead_key: bytes | None = None  # XChaCha20-Poly1305 key for body encryption
    sdk_x25519_sk: bytes | None = None  # SDK X25519 secret key


@dataclass
class Context:
    validator_base_url: str
    session_token: str
    job_id: str
    challenge_id: str
    validator_hotkey: str
    client: Any
    cvm: Any
    values: Any
    results: Any
