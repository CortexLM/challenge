from __future__ import annotations

from typing import Any


class ValuesClient:
    def __init__(self, client: Any, challenge_id: str) -> None:
        self.client = client
        self.challenge_id = challenge_id

    def get(self, key: str) -> Any | None:
        resp = self.client.post(f"/values/{self.challenge_id}", json={"key": key})
        return resp.json().get("value")

    def set(self, key: str, value: Any) -> None:
        self.client.post(f"/values/{self.challenge_id}", json={"key": key, "value": value})

    def delete(self, key: str) -> None:
        self.client.post(f"/values/{self.challenge_id}/delete", json={"key": key})
