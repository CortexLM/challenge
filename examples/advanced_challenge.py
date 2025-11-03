from platform_challenge_sdk import challenge, run, Context


@challenge.on_startup()
async def on_startup():
    # Initialize challenge resources
    print("Initializing challenge resources...")


@challenge.on_ready()
async def on_ready():
    # Challenge is ready to accept jobs
    print("Challenge ready to accept jobs!")


@challenge.on_job()
def evaluate(ctx: Context, payload: dict) -> dict:
    # Process job
    score = 0.95
    metrics = {
        "accuracy": 0.95,
        "latency_ms": 150,
        "throughput": 1000,
    }
    job_type = "inference"
    logs = ["Processing started", "Model loaded", "Inference completed"]
    allowed_log_containers = ["model-checkpoint"]
    
    return {
        "score": score,
        "metrics": metrics,
        "job_type": job_type,
        "logs": logs,
        "allowed_log_containers": allowed_log_containers,
    }


@challenge.on_weights()
def on_weights(jobs: list[dict]) -> dict[str, float]:
    # Custom weights calculation
    weights = {}
    total_score = 0.0
    
    for j in jobs:
        uid = str(j.get("uid"))
        score = float(j.get("score", 0.0))
        total_score += score
        weights[uid] = score
    
    # Apply custom normalization if needed
    if total_score > 0:
        for uid in weights:
            weights[uid] = weights[uid] / total_score
    
    return weights


@challenge.api.public("upload_artefact")
async def upload_artefact(request):
    data = await request.body()
    token_info = request.state.token_info
    return {
        "artefact_id": f"art-{token_info['job_id']}",
        "size": len(data),
        "uploaded_by": token_info['miner_hotkey'],
    }


@challenge.on_cleanup()
def cleanup(ctx: Context):
    print("Cleaning up challenge resources...")


if __name__ == "__main__":
    run()

