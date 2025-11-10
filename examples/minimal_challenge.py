from platform_challenge_sdk import challenge, run, Context


@challenge.on_startup()
async def on_startup():
    print("Challenge starting...")


@challenge.on_ready()
async def on_ready():
    print("Challenge ready!")


@challenge.on_job()
def evaluate(ctx: Context, payload: dict) -> dict:
    score = 0.9
    metrics = {"accuracy": 0.9}
    job_type = "classification"
    return {"score": score, "metrics": metrics, "job_type": job_type}


@challenge.on_weights()
def on_weights(jobs: list[dict]) -> dict[str, float]:
    weights = {}
    for j in jobs:
        uid = str(j.get("uid"))
        score = float(j.get("score", 0.0))
        weights[uid] = max(score, 0.0)
    return weights


if __name__ == "__main__":
    run()
