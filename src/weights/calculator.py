from __future__ import annotations


def default_get_weights(jobs: list[dict]) -> dict[str, float]:
    weights = {}
    for job in jobs:
        uid = str(job.get("uid", "0"))
        score = float(job.get("score", 0.0))
        weights[uid] = max(score, 0.0)
    return weights
