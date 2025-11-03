from __future__ import annotations

import base64
import os

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from nacl import public as nacl_public
from nacl import signing as nacl_signing

from ..config import Settings
from ..db import init_db, init_models
from ..db.migrations import run_startup_migrations
from .security import verify_request_security


async def sdk_admin_db_credentials(request: Request) -> JSONResponse:
    """Handle encrypted database credentials from validator.

    Decrypts DB credentials encrypted with ephemeral Ed25519 key pair.
    Key was generated using cryptographically secure random during bootstrap
    and stored in SDK_EPHEMERAL_SK_B64 env var.
    """
    await verify_request_security(
        session_token=request.headers.get("X-Session-Token"),
        public_key=request.headers.get("X-Public-Key"),
        timestamp=request.headers.get("X-Timestamp"),
        nonce=request.headers.get("X-Nonce"),
        signature=request.headers.get("X-Signature"),
    )
    body = await request.json()
    sealed_b64 = body.get("sealed")
    challenge_name = body.get("challenge_name")
    version = str(body.get("version")) if body.get("version") is not None else None
    if not sealed_b64 or not challenge_name or not version:
        raise HTTPException(status_code=400, detail="missing fields")

    sk_b64 = os.getenv("SDK_EPHEMERAL_SK_B64")
    if not sk_b64:
        raise HTTPException(status_code=500, detail="missing SDK ephemeral key")
    try:
        sk_raw = base64.b64decode(sk_b64)
        signing_key = nacl_signing.SigningKey(sk_raw)
        curve_sk = signing_key.to_curve25519_private_key()
        sealed = base64.b64decode(sealed_b64)
        box = nacl_public.SealedBox(curve_sk)
        plaintext = box.decrypt(sealed)
    except Exception as err:
        raise HTTPException(status_code=400, detail="credentials decrypt failed") from err

    try:
        decoded = plaintext.decode("utf-8")
        if decoded.startswith("{"):
            import json as _json

            d = _json.loads(decoded)
            dsn = d.get("dsn")
        else:
            dsn = decoded
        if not dsn:
            raise ValueError("missing dsn")
        os.environ["SDK_DB_DSN"] = dsn
    except Exception as err:
        raise HTTPException(status_code=400, detail="invalid credentials payload") from err

    await run_startup_migrations(challenge_name, version, sealed_b64)

    # Initialize SQLAlchemy with the decrypted DSN
    settings = Settings()
    await init_db(settings, dsn)

    # Initialize models
    init_models()

    from .server import set_ready

    await set_ready()
    return JSONResponse({"migrated": True})
