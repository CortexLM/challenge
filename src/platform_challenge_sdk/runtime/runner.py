from __future__ import annotations

import asyncio
import os

from ..challenge import Context


def _register_lifecycle_defaults() -> None:
    pass


async def _run_async_server() -> None:
    """Async runtime logic for WS server mode."""
    _register_lifecycle_defaults()
    # WS server mode: just start the FastAPI server
    # Validator will connect via WebSocket and initiate attestation
    from ..api.server import init_app, set_ready
    from ..challenge.decorators import challenge

    # Check dev mode for local DB initialization
    dev_mode = os.getenv("SDK_DEV_MODE", "").lower() == "true"
    db_manager = None
    if dev_mode:
        import logging

        from ..dev.local_db import init_local_db_if_needed, run_dev_migrations_if_possible
        from ..dev.local_orm_adapter import LocalORMAdapter
        from ..orm.permissions import ORMPermissions

        logger = logging.getLogger(__name__)

        # Try to initialize local DB if DEV_DB_URL is provided
        db_manager = await init_local_db_if_needed()
        if db_manager:
            logger.info("🔧 DEV MODE: Using local database connection")

            # Create local ORM adapter and set it on challenge
            challenge_id = os.getenv("CHALLENGE_ID", "term-challenge")
            db_version = challenge.db_version or 1
            schema_name = f"{challenge_id}_v{db_version}"

            permissions = (
                challenge.orm_permissions if challenge.orm_permissions else ORMPermissions()
            )
            local_adapter = LocalORMAdapter(
                db_manager=db_manager,
                permissions=permissions,
                challenge_id=challenge_id,
                schema_name=schema_name,
            )
            challenge._server_orm_adapter = local_adapter
            logger.info(f"🔧 DEV MODE: Local ORM adapter initialized for schema '{schema_name}'")

            # Call on_orm_ready() automatically in dev mode
            if challenge.orm_ready_handler:
                try:
                    logger.info("🔧 DEV MODE: Calling on_orm_ready() handler automatically...")
                    handler = challenge.orm_ready_handler
                    if asyncio.iscoroutinefunction(handler):
                        await handler()
                    else:
                        handler()
                    logger.info("✅ DEV MODE: on_orm_ready() handler completed")
                except Exception as e:
                    logger.error(f"Failed to call on_orm_ready() handler: {e}", exc_info=True)
        else:
            # Even without DEV_DB_URL, try to run migrations if a default DB is available
            # This allows migrations to run in dev mode without explicit DB URL
            await run_dev_migrations_if_possible()

    app = await init_app(challenge, challenge.api)
    await set_ready()

    import uvicorn

    # Allow custom port in dev mode
    port = int(os.getenv("SDK_PORT", "10000"))
    host = os.getenv("SDK_HOST", "0.0.0.0")  # noqa: S104

    if dev_mode:
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"🔧 DEV MODE: Starting server on {host}:{port}")

    config = uvicorn.Config(app, host=host, port=port)
    server = uvicorn.Server(config)
    await server.serve()


async def _run_async(ctx: Context) -> None:
    """Async runtime logic."""
    _register_lifecycle_defaults()
    # mTLS server removed - encryption now handled via X25519/ChaCha20-Poly1305


def run() -> None:
    """Main entry point for challenge runtime.

    The challenge always runs as a WebSocket server, regardless of CHALLENGE_ADMIN.
    CHALLENGE_ADMIN determines capabilities:
    - CHALLENGE_ADMIN=true: Migrations, ORM write, public endpoints (for platform-api)
    - CHALLENGE_ADMIN=false/absent: ORM read-only bridge, no migrations, no public endpoints (for platform-validator)
    """
    # Always run as WebSocket server (both platform-api and platform-validator connect to challenge)
    asyncio.run(_run_async_server())
