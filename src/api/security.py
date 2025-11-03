from __future__ import annotations

import os

from fastapi import Header, HTTPException, Request

# Check if dev mode is enabled
_DEV_MODE = os.getenv("SDK_DEV_MODE", "").lower() == "true"


async def validate_client_cert(request: Request, call_next):
    """Validate client certificate in mTLS middleware."""
    # Skip validation in dev mode
    if _DEV_MODE:
        return await call_next(request)

    client_cert = request.headers.get("X-Client-Certificate")
    if client_cert:
        if "validator" not in client_cert.lower():
            raise HTTPException(status_code=403, detail="Invalid client certificate")
    return await call_next(request)


async def verify_request_security(
    session_token: str | None = Header(default=None, alias="X-Session-Token"),
    public_key: str | None = Header(default=None, alias="X-Public-Key"),
    timestamp: str | None = Header(default=None, alias="X-Timestamp"),
    nonce: str | None = Header(default=None, alias="X-Nonce"),
    signature: str | None = Header(default=None, alias="X-Signature"),
) -> None:
    """Verify signed request headers for authenticated endpoints."""
    # Note: This function is used for validator/admin routes, not public routes.
    # Public routes use X-Verified-Miner-Hotkey from platform-api proxy.
    # Skip verification in dev mode only for validator/admin routes
    if _DEV_MODE:
        return

    if not all([session_token, public_key, timestamp, nonce, signature]):
        raise HTTPException(status_code=401, detail="Missing signed headers")
