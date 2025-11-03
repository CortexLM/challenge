# API Reference

## Decorators

### `@challenge.on_startup()`

Called before database migrations. Use for initial setup.

**Signature:**
```python
@challenge.on_startup()
async def init() -> None:
    pass
```

**When called**: Before database migrations are applied.

**Use cases**: Initial setup, configuration validation, pre-migration tasks.

**Example:**
```python
@challenge.on_startup()
async def init():
    """Initialize challenge configuration."""
    print("Challenge starting up...")
    # Validate configuration
    # Set up initial state
```

---

### `@challenge.on_ready()`

Called after migrations complete. Challenge is ready to accept jobs.

**Signature:**
```python
@challenge.on_ready()
async def ready() -> None:
    pass
```

**When called**: After database migrations are applied and ORM bridge is ready.

**Use cases**: Post-migration setup, warmup, connection pooling.

**Example:**
```python
@challenge.on_ready()
async def ready():
    """Challenge is ready to accept jobs."""
    print("Challenge ready!")
    # Warmup models
    # Initialize connections
```

---

### `@challenge.on_orm_ready()`

Called when the ORM bridge is ready and migrations have been applied.

**Signature:**
```python
@challenge.on_orm_ready()
async def orm_ready() -> None:
    pass
```

**When called**: After Platform API signals that migrations are complete and ORM is ready.

**Use cases**: ORM-specific initialization, sending ORM permissions.

**Example:**
```python
@challenge.on_orm_ready()
async def orm_ready():
    """ORM bridge is ready."""
    from platform_challenge_sdk.orm import ORMPermissions
    permissions = ORMPermissions()
    # Configure permissions
    challenge.set_orm_permissions(permissions)
```

---

### `@challenge.on_job()`

Process job evaluation. Returns score, metrics, and job type.

**Signature:**
```python
@challenge.on_job(job_name: str | None = None)
def evaluate(ctx: Context, payload: dict) -> dict:
    return {"score": 0.9, "metrics": {}, "job_type": "default"}
```

**Parameters:**
- `job_name` (optional): Name of the job type. If `None`, acts as the default handler.

**Returns:**
- `dict`: Must contain:
  - `score` (float): Job score (0.0 to 1.0)
  - `metrics` (dict): Optional metrics dictionary
  - `job_type` (str): Job type identifier
  - `logs` (list, optional): Log messages
  - `allowed_log_containers` (list, optional): Container names for logs
  - `error` (str, optional): Error message if failed

**Example:**
```python
@challenge.on_job()
def evaluate(ctx: Context, payload: dict) -> dict:
    agent_code = payload.get("agent_code")
    # Evaluate agent
    score = 0.95
    return {
        "score": score,
        "metrics": {"accuracy": 0.95},
        "job_type": "evaluation",
    }

@challenge.on_job("train_model")
def train_model(ctx: Context, payload: dict) -> dict:
    """Handle train_model jobs."""
    return {"score": 0.85, "job_type": "train_model"}
```

---

### `@challenge.on_cleanup()`

Final cleanup when challenge completes.

**Signature:**
```python
@challenge.on_cleanup()
def cleanup(ctx: Context) -> None:
    pass
```

**When called**: When the challenge is shutting down.

**Use cases**: Resource cleanup, final logging, state persistence.

**Example:**
```python
@challenge.on_cleanup()
def cleanup(ctx: Context):
    """Cleanup resources."""
    # Close connections
    # Save state
    # Cleanup temporary files
```

---

### `@challenge.on_weights()`

Calculate mining weights from job scores.

**Signature:**
```python
@challenge.on_weights()
def on_weights(jobs: list[dict]) -> dict[str, float]:
    return {"uid": weight}
```

**Parameters:**
- `jobs` (list[dict]): List of job dictionaries containing:
  - `uid` (str): Miner UID
  - `score` (float): Job score
  - Other job-specific fields

**Returns:**
- `dict[str, float]`: Dictionary mapping UID to weight (0.0 to 1.0)

**Note**: Weights are raw (non-normalized). The validator handles normalization.

**Example:**
```python
@challenge.on_weights()
def on_weights(jobs: list[dict]) -> dict[str, float]:
    """Calculate weights from job scores."""
    weights = {}
    for job in jobs:
        uid = str(job.get("uid"))
        score = float(job.get("score", 0.0))
        weights[uid] = max(score, 0.0)  # Ensure non-negative
    return weights
```

---

### `@challenge.api.public(name)`

Expose public endpoint at `/sdk/public/{name}`.

**Signature:**
```python
@challenge.api.public("endpoint_name")
async def handler(request: Request) -> dict:
    return {"status": "ok"}
```

**Parameters:**
- `name` (str): Endpoint name (used in URL)

**Returns:**
- `FastAPI Request`: Standard FastAPI request object with `request.state.token_info`

**Access**: `POST /sdk/public/{name}`

**Authentication**: Automatically verified by Platform API via MinerToken

**Example:**
```python
from fastapi import Request

@challenge.api.public("upload_agent")
async def upload_agent(request: Request):
    """Handle agent uploads."""
    data = await request.json()
    token_info = request.state.token_info
    
    return {
        "agent_id": f"agent-{token_info['job_id']}",
        "uploaded_by": token_info['miner_hotkey'],
    }
```

---

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

### SigningHttpClient

Signed HTTP client for making authenticated requests to the validator:

```python
# POST request with signed headers
response = await ctx.client.post(
    "/endpoint",
    json={"data": "value"}
)

# GET request
response = await ctx.client.get("/endpoint")

# PUT request
response = await ctx.client.put("/endpoint", json={})
```

### CVMClient

CVM client for heartbeat and quota management:

```python
# Send heartbeat
await ctx.cvm.heartbeat()

# Get quota
quota = await ctx.cvm.get_quota()
```

### ValuesClient

Key-value storage client:

```python
# Set value
await ctx.values.set("key", "value")

# Get value
value = await ctx.values.get("key")

# Delete value
await ctx.values.delete("key")
```

### ResultsClient

Result submission client:

```python
# Submit result
await ctx.results.submit({
    "score": 0.95,
    "metrics": {"accuracy": 0.95}
})
```

---

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
| `SDK_PORT` | SDK server port | `10000` |
| `SDK_HOST` | SDK server host | `0.0.0.0` |

---

## SDK Endpoints

### Health Check

**Endpoint**: `GET /sdk/health`

**Response**:
```json
{
  "status": "starting" | "ready"
}
```

---

### Weights Calculation

**Endpoint**: `POST /sdk/weights`

**Authentication**: Signed request (Ed25519)

**Request**:
```json
{
  "jobs": [
    {
      "uid": "1",
      "score": 0.95,
      "job_id": "job-123"
    }
  ]
}
```

**Response**:
```json
{
  "weights": {
    "1": 0.95,
    "2": 0.85
  }
}
```

---

### Public Endpoints

**Endpoint**: `POST /sdk/public/{name}`

**Authentication**: MinerToken (verified by Platform API)

**Request**: Any JSON payload

**Response**: Handler-dependent

---

### Admin: Database Credentials

**Endpoint**: `POST /sdk/admin/db/credentials`

**Authentication**: Signed request (Ed25519), requires `CHALLENGE_ADMIN=true`

**Request**:
```json
{
  "sealed_credentials": "...",
  "ephemeral_pub_key": "..."
}
```

**Response**: Success or error

---

## See Also

- [Usage Guide](usage.md) - Usage examples
- [Security](security.md) - Security details
- [Getting Started](getting-started.md) - Getting started guide

