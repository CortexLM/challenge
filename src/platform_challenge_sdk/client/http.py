from __future__ import annotations

import base64
import hashlib
import secrets
import time
import uuid
from typing import Any

import requests
from nacl import signing
from nacl.bindings import crypto_aead_xchacha20poly1305_ietf_encrypt
from nacl.encoding import RawEncoder

from ..types import SigningSession


def _sha256_hex(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


class SigningHttpClient:
    def __init__(self, base_url: str, validator_hotkey: str, session: SigningSession) -> None:
        self.base_url = base_url
        self.validator_hotkey = validator_hotkey
        self.session = session

    def post(self, path: str, json: dict[str, Any] | None = None) -> requests.Response:
        """Make signed POST request to validator with optional body encryption."""
        url = f"{self.base_url}{path}"

        # Serialize JSON body
        import json as json_module

        plaintext_body = json_module.dumps(json) if json else ""
        plaintext_bytes = plaintext_body.encode()

        # Encrypt body if AEAD key is available
        if self.session.aead_key:
            # Generate random 12-byte nonce for ChaCha20-Poly1305
            nonce = secrets.token_bytes(12)
            ciphertext = crypto_aead_xchacha20poly1305_ietf_encrypt(
                plaintext_bytes,
                None,  # No additional data
                nonce + b"\x00" * 12,  # Pad to 24 bytes for nacl XChaCha20 API
                self.session.aead_key,
            )

            # Create encrypted envelope
            envelope = {
                "enc": "chacha20poly1305",
                "nonce": base64.b64encode(nonce).decode("ascii"),
                "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
            }
            body = json_module.dumps(envelope)
            content_type = "application/x-encrypted+json"
        else:
            body = plaintext_body
            content_type = "application/json"

        body_bytes = body.encode()

        timestamp = str(int(time.time()))
        nonce = str(uuid.uuid4())

        canonical = f"POST\n{path}\n{_sha256_hex(body_bytes)}\n{timestamp}\n{nonce}\n{self.session.session_token or ''}"

        signature_bytes = (
            signing.SigningKey(self.session.secret_key)
            .sign(canonical.encode(), encoder=RawEncoder)
            .signature
        )
        signature_b64 = base64.b64encode(signature_bytes).decode("ascii")
        pubkey_b64 = base64.b64encode(self.session.public_key).decode("ascii")

        headers = {
            "Content-Type": content_type,
            "X-Session-Token": self.session.session_token or "",
            "X-Public-Key": pubkey_b64,
            "X-Timestamp": timestamp,
            "X-Nonce": nonce,
            "X-Signature": signature_b64,
        }

        return requests.post(url, data=body, headers=headers, timeout=30)
