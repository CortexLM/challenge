# Usage Guide

## Challenge Lifecycle

The SDK provides decorators for all lifecycle stages:

```python
from platform_challenge_sdk import challenge, Context

@challenge.on_startup()
async def init():
    """Called before database migrations."""
    pass

@challenge.on_ready()
async def ready():
    """Called after migrations and initialization."""
    pass

@challenge.on_job()
def process_job(ctx: Context, payload: dict) -> dict:
    """Process a job evaluation."""
    return {"score": 0.9, "metrics": {}, "job_type": "default"}

@challenge.on_cleanup()
def cleanup(ctx: Context):
    """Final cleanup."""
    pass
```

## Job Evaluation

The `@challenge.on_job()` decorator receives a `Context` object and payload:

```python
@challenge.on_job()
def evaluate(ctx: Context, payload: dict) -> dict:
    # Access validator clients
    ctx.client.post("/some/endpoint", json={"data": "value"})
    
    # Use CVM client
    ctx.cvm.heartbeat()
    
    # Store values
    ctx.values.set("key", "value")
    value = ctx.values.get("key")
    
    # Submit results (auto-called with return dict)
    return {
        "score": 0.95,
        "metrics": {"accuracy": 0.95},
        "job_type": "classification",
        "logs": ["Processing started"],
        "allowed_log_containers": ["model-checkpoint"],
        "error": None
    }
```

### Named Job Handlers

You can register multiple job handlers for different job types:

```python
@challenge.on_job("evaluate_agent")
def evaluate_agent(ctx: Context, payload: dict) -> dict:
    """Handler for evaluate_agent jobs."""
    return {"score": 0.9, "job_type": "evaluate_agent"}

@challenge.on_job("train_model")
def train_model(ctx: Context, payload: dict) -> dict:
    """Handler for train_model jobs."""
    return {"score": 0.85, "job_type": "train_model"}
```

## Weights Calculation

Define custom weights calculation:

```python
@challenge.on_weights()
def on_weights(jobs: list[dict]) -> dict[str, float]:
    """Calculate mining weights from job scores."""
    weights = {}
    total_score = 0.0
    
    for job in jobs:
        uid = str(job.get("uid"))
        score = float(job.get("score", 0.0))
        total_score += score
        weights[uid] = score
    
    # Normalize if needed
    if total_score > 0:
        for uid in weights:
            weights[uid] = weights[uid] / total_score
    
    return weights
```

**Note**: Returned weights are raw (non-normalized). The validator handles normalization and residual allocation to `uid=0`.

## Public Endpoints

Expose custom public endpoints:

```python
from fastapi import Request

@challenge.api.public("upload_artefact")
async def upload_artefact(request: Request):
    """Handle artefact uploads."""
    data = await request.body()
    token_info = request.state.token_info
    
    return {
        "artefact_id": f"art-{token_info['job_id']}",
        "size": len(data),
        "uploaded_by": token_info['miner_hotkey'],
    }
```

Access at: `POST /sdk/public/upload_artefact`

Public endpoints are automatically proxied by Platform API with signature verification. The `request.state.token_info` contains:

- `uid`: Miner UID
- `miner_hotkey`: Miner hotkey
- `job_id`: Current job ID
- `challenge_id`: Challenge ID
- `job_type`: Job type

## Database Access

Use the ORM bridge to access the database:

```python
from platform_challenge_sdk.orm import SecureORMClient

# In your job handler or lifecycle hook
async def use_database():
    # ORM client is automatically available via context
    # or you can create one manually
    result = await orm_client.select(
        table="jobs",
        columns=["id", "job_id", "score"],
        filters=[QueryFilter("score", ">", 0.9)],
        limit=10
    )
    
    # Insert data
    await orm_client.insert(
        table="jobs",
        values={
            "job_id": "job-123",
            "score": 0.95
        }
    )
```

See [Database Migrations](database-migrations.md) for more details.

## Context Object

The `Context` object provides access to all SDK services:

```python
@dataclass
class Context:
    validator_base_url: str      # Validator API URL
    session_token: str           # Session token
    job_id: str                  # Current job ID
    challenge_id: str            # Challenge ID
    validator_hotkey: str        # Validator hotkey
    client: SigningHttpClient    # Signed HTTP client
    cvm: CVMClient              # CVM client
    values: ValuesClient        # Key-value storage
    results: ResultsClient      # Result submission
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VALIDATOR_BASE_URL` | Validator API URL | `http://validator:8080` |
| `SESSION_TOKEN` | Session token | `""` |
| `JOB_ID` | Current job ID | `""` |
| `CHALLENGE_ID` | Challenge ID | `""` |
| `VALIDATOR_HOTKEY` | Validator hotkey | `"validator"` |
| `SDK_RUN_SERVER` | Enable SDK server | `"false"` |
| `SDK_DB_DSN` | Database DSN (decrypted) | - |
| `SDK_EPHEMERAL_SK_B64` | Ephemeral secret key (auto-set) | - |
| `CHALLENGE_ADMIN` | Admin mode (Platform API) | `"false"` |
| `SDK_DEV_MODE` | Development mode | `"false"` |

## Examples

Check out the `examples/` directory for complete challenge implementations:

- `minimal_challenge.py` - Minimal example to get started
- `advanced_challenge.py` - Advanced features demonstration

## See Also

- [API Reference](api-reference.md) - Complete API documentation
- [Database Migrations](database-migrations.md) - Database setup and migrations
- [Security](security.md) - Security best practices

