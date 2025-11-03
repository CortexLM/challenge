from __future__ import annotations

import os
from typing import Any


class ResultsClient:
    def __init__(self, client: Any, session_token: str) -> None:
        self.client = client
        self.session_token = session_token
        self._ws_sender = None  # set by runtime when WS is available

    def submit(
        self,
        score: float,
        metrics: dict[str, Any],
        job_type: str,
        logs: list[str] | None = None,
        allowed_log_containers: list[str] | None = None,
        error: str | None = None,
    ) -> None:
        payload = {
            "score": score,
            "metrics": metrics,
            "job_type": job_type,
            "logs": logs or [],
            "allowed_log_containers": allowed_log_containers or [],
            "error": error,
        }
        # If WS transport is enabled and sender injected, emit over WS
        if os.getenv("WS_TRANSPORT", "true").lower() == "true" and self._ws_sender:
            try:
                self._ws_sender({"type": "submit", "payload": payload})
                return
            except Exception:
                # WebSocket submission failed, fallback to HTTP
                pass
        # Fallback to HTTP
        self.client.post("/results/submit", json=payload)
