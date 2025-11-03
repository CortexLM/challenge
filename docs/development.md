# Development

## Project Structure

```
challenge/
├── src/platform_challenge_sdk/  # Main package
│   ├── api/                     # FastAPI endpoints
│   ├── client/                  # HTTP client + attestation
│   ├── challenge/               # Decorators + context
│   ├── runtime/                 # Runtime executor
│   ├── db/                      # Database migrations
│   ├── cvm/                     # CVM client
│   ├── values/                 # Values client
│   ├── results/                 # Results client
│   ├── weights/                 # Weights calculator
│   ├── transport/               # WebSocket transport
│   ├── websocket/               # WebSocket client utilities
│   ├── orm/                     # ORM bridge client
│   ├── security/                # Security utilities
│   └── dev/                     # Development utilities
├── examples/                    # Example challenges
├── tests/                       # Unit tests
├── docs/                        # Documentation
├── scripts/                     # Utility scripts
└── pyproject.toml              # PEP 621 config
```

## Development Setup

### Install Development Dependencies

```bash
pip install -e ".[dev]"
pre-commit install
```

### Development Tools

Available make commands:

```bash
make install-dev      # Install with dev dependencies
make lint             # Run ruff + mypy
make format           # Format with black + isort
make test             # Run pytest
make check            # Check everything (lint + format + test)
make clean            # Clean build artifacts
```

### Pre-commit Hooks

Automatic checks on commit:

- **ruff**: Linting and import sorting
- **black**: Code formatting
- **isort**: Import organization
- **trailing whitespace**: Remove trailing spaces
- **end-of-file**: Ensure newline at EOF

## Code Style

### Formatting

We use:
- **black**: Code formatter (line length: 100)
- **isort**: Import sorter (profile: black)

### Linting

We use:
- **ruff**: Fast Python linter
- **mypy**: Static type checker

### Type Hints

Always use type hints:

```python
from typing import Any, Awaitable

async def handler(ctx: Context, payload: dict[str, Any]) -> dict[str, Any]:
    return {"score": 0.9}
```

## Testing

### Run Tests

```bash
make test
# or
pytest
```

### Test Structure

```
tests/
├── __init__.py
├── test_challenge.py
└── test_*.py
```

### Writing Tests

```python
import pytest
from platform_challenge_sdk import challenge

def test_job_handler():
    @challenge.on_job()
    def handler(ctx, payload):
        return {"score": 0.9}
    
    result = handler(None, {})
    assert result["score"] == 0.9
```

## Adding New Features

### 1. Create Feature Branch

```bash
git checkout -b feature/new-feature
```

### 2. Write Code

Follow the project structure:
- Use type hints
- Add docstrings
- Write tests

### 3. Run Checks

```bash
make check
```

### 4. Commit

```bash
git add .
git commit -m "feat: Add new feature"
```

## Code Review Checklist

- [ ] Code follows style guidelines
- [ ] Type hints added
- [ ] Docstrings added
- [ ] Tests written
- [ ] Tests pass
- [ ] Linting passes
- [ ] No hardcoded secrets
- [ ] Error handling added

## Debugging

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Development Mode

Set `SDK_DEV_MODE=true` to enable:
- Bypass TDX attestation
- Plain text WebSocket (no encryption)
- Local database support
- Detailed logging

```bash
SDK_DEV_MODE=true python my_challenge.py
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run `make check`
5. Submit a pull request

## See Also

- [Getting Started](getting-started.md) - Installation guide
- [API Reference](api-reference.md) - API documentation
- [Troubleshooting](troubleshooting.md) - Common issues

