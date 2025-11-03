from __future__ import annotations

from fastapi.responses import JSONResponse


async def sdk_health() -> JSONResponse:
    from .server import _is_ready

    return JSONResponse({"status": "ready" if _is_ready else "starting"})
