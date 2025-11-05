from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
