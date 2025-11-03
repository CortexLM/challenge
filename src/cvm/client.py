from __future__ import annotations

from typing import Any


class CVMClient:
    def __init__(self, client: Any, challenge_id: str, validator_hotkey: str) -> None:
        self.client = client
        self.challenge_id = challenge_id
        self.validator_hotkey = validator_hotkey

    def heartbeat(self) -> None:
        self.client.post("/cvm/heartbeat", json={"challenge_id": self.challenge_id})
