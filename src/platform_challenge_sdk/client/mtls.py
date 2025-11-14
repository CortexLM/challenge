from __future__ import annotations

import base64
import hashlib
import os
import secrets
from typing import Any

import requests
from nacl import signing
from nacl.bindings import crypto_scalarmult
from nacl.encoding import RawEncoder

from ..types import SigningSession
from .http import SigningHttpClient


def derive_aead_key(
    shared_secret: bytes, hkdf_salt_b64: str, info: bytes = b"platform-api-sdk-v1"
) -> bytes:
    """Derive AEAD key using HKDF-SHA256.

    Args:
        shared_secret: The shared secret from X25519 key exchange
        hkdf_salt_b64: Base64-encoded HKDF salt
        info: HKDF info parameter (default: b"platform-api-sdk-v1" for platform-api compatibility)
    """
    import hmac

    salt = base64.b64decode(hkdf_salt_b64)
    hkdf_extract = hmac.new(salt, shared_secret, hashlib.sha256).digest()

    # HKDF expand with the same info string as platform-api uses
    hkdf_expand = hmac.new(hkdf_extract, info + b"\x01", hashlib.sha256).digest()
    return hkdf_expand


def get_tls_materials() -> dict[str, str]:
    """Deprecated: mTLS removed in favor of X25519/ChaCha20-Poly1305 encryption."""
    return {}


def bootstrap_attested_session(base_url: str, validator_hotkey: str) -> Any:
    """Bootstrap secure session with TDX attestation and X25519/ChaCha20-Poly1305 encryption.

    Generates Ed25519 ephemeral keypair for signatures and X25519 keypair for encryption.
    Uses secrets.token_bytes() which calls os.urandom() on Linux/devices.
    """
    nonce_resp = requests.post(f"{base_url}/attestation/challenge", timeout=10)
    nonce_resp.raise_for_status()
    nonce_json = nonce_resp.json()

    nonce = nonce_json.get("nonce", "")
    report_data = hashlib.sha256(nonce.encode()).digest()[:32]

    # Generate Ed25519 keypair for request signing
    seed = secrets.token_bytes(32)
    signer = signing.SigningKey(seed)

    # Generate X25519 keypair for encryption
    sdk_x25519_sk = secrets.token_bytes(32)
    sdk_x25519_pub = crypto_scalarmult.scalarmult_base(sdk_x25519_sk)

    session = SigningSession(
        public_key=signer.verify_key.encode(encoder=RawEncoder),
        secret_key=signer.encode(encoder=RawEncoder),
        sdk_x25519_sk=sdk_x25519_sk,
    )
    client = SigningHttpClient(base_url, validator_hotkey, session)

    quote = None
    event_log = None
    rtmrs = None

    try:
        from dstack_sdk import DstackClient

        dstack_client = DstackClient()
        quote_result = dstack_client.get_quote(report_data)
        quote = quote_result.quote
        event_log = quote_result.event_log
        rtmrs_result = quote_result.replay_rtmrs()
        rtmrs = {
            "rtmr0": rtmrs_result[0] if len(rtmrs_result) > 0 else None,
            "rtmr1": rtmrs_result[1] if len(rtmrs_result) > 1 else None,
            "rtmr2": rtmrs_result[2] if len(rtmrs_result) > 2 else None,
            "rtmr3": rtmrs_result[3] if len(rtmrs_result) > 3 else None,
        }
    except ImportError:
        # dstack-sdk not available, RTMRs cannot be retrieved
        pass
    except Exception:
        # RTMR retrieval failed, non-critical
        pass

    attestation_payload = {
        "attestation_type": "Tdx",
        "nonce": nonce,
        "quote": quote,
        "report": None,
        "measurements": [],
        "capabilities": ["cvm"],
        "event_log": event_log,
        "rtmrs": rtmrs,
    }

    attest_req = {
        "ephemeral_public_key": base64.b64encode(session.public_key).decode("ascii"),
        "attestation": attestation_payload,
        "sdk_x25519_pub": base64.b64encode(sdk_x25519_pub).decode("ascii"),
    }

    try:
        attest_resp = requests.post(f"{base_url}/attest", json=attest_req, timeout=20)

        # Log response for debugging
        print(f"Attest response status: {attest_resp.status_code}")
        print(f"Attest response text: {attest_resp.text[:200]}")

        attest_resp.raise_for_status()  # Raise exception for bad status codes

        if not attest_resp.text or not attest_resp.text.strip():
            raise RuntimeError(
                f"Empty response from /attest endpoint: status={attest_resp.status_code}"
            )

        attest_json = attest_resp.json()
    except requests.exceptions.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON response from /attest: {attest_resp.text[:200]}") from e
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(
            f"HTTP error from /attest: {e.response.status_code} - {e.response.text[:200]}"
        ) from e
    session.session_token = attest_json.get("session_token")

    # Parse crypto block and derive AEAD key
    crypto = attest_json.get("crypto") or {}
    srv_x25519_pub_b64 = crypto.get("srv_x25519_pub")
    hkdf_salt = crypto.get("hkdf_salt")

    if srv_x25519_pub_b64 and hkdf_salt:
        srv_x25519_pub = base64.b64decode(srv_x25519_pub_b64)
        shared_secret = crypto_scalarmult.scalarmult(sdk_x25519_sk, srv_x25519_pub)
        aead_key = derive_aead_key(shared_secret, hkdf_salt)
        session.aead_key = aead_key

        ephemeral_sk_b64 = base64.b64encode(session.secret_key).decode("ascii")
        os.environ["SDK_EPHEMERAL_SK_B64"] = ephemeral_sk_b64

    return client
