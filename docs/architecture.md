# Architecture

## System Overview

The Challenge SDK operates as a bridge between two main components of the Platform Network, enabling secure and verifiable challenge execution in a confidential computing environment.

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                    Platform Network                          │
│                                                              │
│  ┌──────────────┐                                           │
│  │   Miner 1    │──────┐                                    │
│  └──────────────┘      │                                    │
│                        │  Agent code/model upload          │
│  ┌──────────────┐      │                                    │
│  │   Miner N    │──────┘                                    │
│  └──────┬───────┘                                           │
│         │                                                    │
│         │ HTTP (Signed requests)                             │
│         ▼                                                    │
│  ┌────────────────────────────┐                             │
│  │     Platform API           │                             │
│  │                            │                             │
│  │  - Receive agent uploads   │                             │
│  │  - Store agent code/model  │                             │
│  │  - Database management     │                             │
│  │  - Schema isolation        │                             │
│  │  - Public request proxy    │                             │
│  │  - Credential decryption   │                             │
│  └──────┬─────────────────────┘                             │
│         │                                                    │
│         │ WebSocket (CHALLENGE_ADMIN=true)                  │
│         │  - ORM read/write                                  │
│         │  - Database migrations                            │
│         │  - Send agent code to Challenge SDK               │
│         │  - Forward job execution requests                 │
│         ▼                                                    │
│  ┌────────────────────────────┐                             │
│  │  Challenge SDK             │                             │
│  │                            │                             │
│  │  ┌──────────────────────┐  │                             │
│  │  │  WebSocket Server   │  │                             │
│  │  │  (X25519/ChaCha20)  │  │                             │
│  │  └──────────────────────┘  │                             │
│  │                            │                             │
│  │  ┌──────────────────────┐  │                             │
│  │  │  Job Handlers        │  │                             │
│  │  │  - evaluate_agent   │  │                             │
│  │  │  - Custom jobs       │  │                             │
│  │  └──────────────────────┘  │                             │
│  │                            │                             │
│  │  ┌──────────────────────┐  │                             │
│  │  │  ORM Bridge          │  │                             │
│  │  │  - Database access  │  │                             │
│  │  └──────────────────────┘  │                             │
│  │                            │                             │
│  │  ┌──────────────────────┐  │                             │
│  │  │  Public Endpoints    │  │                             │
│  │  │  - Upload agents     │  │                             │
│  │  │  - Custom APIs       │  │                             │
│  │  └──────────────────────┘  │                             │
│  └──────┬─────────────────────┘                             │
│         │                                                    │
│         │ WebSocket (CHALLENGE_ADMIN=false)                 │
│         │  - ORM read-only                                   │
│         │  - Job execution requests                         │
│         │  - Results retrieval                              │
│         ▼                                                    │
│  ┌────────────────────────────┐                             │
│  │     Platform Validator     │                             │
│  │                            │                             │
│  │  - Request agent evaluation│                             │
│  │  - Receive job results     │                             │
│  │  - Calculate weights       │                             │
│  └────────────────────────────┘                             │
└──────────────────────────────────────────────────────────────┘
```

## Components

### Platform API (`CHALLENGE_ADMIN=true`)

The Platform API manages the challenge infrastructure and acts as intermediary between miners and the Challenge SDK:

- **Agent Reception**: Receives agent code/model uploads from miners via HTTP signed requests
- **Agent Storage**: Stores and manages agent code/models securely
- **Connection**: Encrypted WebSocket connection with TDX attestation to Challenge SDK
- **Agent Delivery**: Forwards agent code/models to Challenge SDK for evaluation
- **Database Management**: Manages database schemas and migrations
- **ORM Bridge**: Provides ORM bridge with read/write permissions
- **Request Proxy**: Proxies public endpoint requests with signature verification
- **Credential Management**: Handles credential decryption and database access control
- **Schema Isolation**: Isolates challenge schemas for multi-tenant security

### Challenge SDK

The Challenge SDK serves as the core runtime for agent evaluation:

- **WebSocket Server**: Accepts connections from both Platform API and Platform Validator
- **Agent Evaluation**: Receives agent code/models from Platform API and evaluates them
- **Job Execution**: Executes job handlers for agent evaluation with provided agent code
- **Lifecycle Management**: Manages challenge lifecycle (startup, ready, cleanup)
- **ORM Bridge**: Provides database operations (read-only for validator, read/write for API)
- **Public Endpoints**: Exposes public endpoints for custom challenge functionality (proxied via Platform API)
- **Results**: Returns evaluation results to Platform Validator via WebSocket

### Platform Validator (`CHALLENGE_ADMIN=false`)

The Platform Validator coordinates agent evaluation and mining:

- **Connection**: Encrypted WebSocket connection with TDX attestation to Challenge SDK
- **Job Requests**: Sends job execution requests to Challenge SDK (agent code is provided by Platform API)
- **Results**: Receives job results from Challenge SDK and calculates mining weights
- **Database Access**: Uses ORM bridge in read-only mode for database queries
- **Weights Calculation**: Requests weights calculation via HTTP signed requests

## Core Components

- **`api/`**: FastAPI server with SDK endpoints (weights, public, admin, health)
- **`client/`**: Signed HTTP client with attestation and X25519 key exchange
- **`challenge/`**: Decorator registry and context management
- **`runtime/`**: Main runtime executor and lifecycle orchestration
- **`db/`**: Automatic database migrations with credential decryption
- **`cvm/`**: CVM client for heartbeat and quota management
- **`values/`**: Key-value storage client
- **`results/`**: Result submission client
- **`weights/`**: Default weights calculator
- **`transport/`**: WebSocket transport with X25519/ChaCha20-Poly1305 encryption
- **`websocket/`**: WebSocket client utilities

## Communication Flow

1. **Agent Upload**: Miners upload agent code/models to Platform API via HTTP signed requests
2. **Agent Storage**: Platform API stores agent code/models securely
3. **Bootstrap**: Challenge SDK boots and waits for WebSocket connections
4. **Connection**: Platform API and Platform Validator establish encrypted WebSocket connections
5. **Attestation**: TDX attestation occurs to verify the challenge's integrity
6. **Key Exchange**: X25519 key exchange establishes encrypted communication channels
7. **Job Request**: Platform Validator requests agent evaluation via WebSocket
8. **Agent Delivery**: Platform API forwards stored agent code to Challenge SDK via WebSocket
9. **Job Execution**: Challenge SDK executes job handlers with the agent code received from Platform API
10. **Results**: Results are returned via WebSocket to Platform Validator for weights calculation

## See Also

- [Usage Guide](usage.md) - Learn how to use the SDK
- [Security](security.md) - Understand the security architecture
- [API Reference](api-reference.md) - Complete API documentation

