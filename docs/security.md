# Security

## End-to-End Security Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Security Flow                        │
│                                                             │
│  1. Bootstrap (HTTP):                                       │
│     ├─ Request nonce from validator                         │
│     ├─ Generate Ed25519 keypair (CSPRNG)                    │
│     ├─ Generate X25519 keypair for encryption              │
│     ├─ Get TDX quote with nonce in report_data               │
│     └─ Submit attestation with public keys                │
│                                                             │
│  2. WebSocket Connection:                                    │
│     ├─ Establish WebSocket connection                      │
│     ├─ TDX attestation via WebSocket                        │
│     ├─ X25519 key exchange                                  │
│     └─ Derive AEAD key using HKDF                          │
│                                                             │
│  3. Encrypted Communication:                                 │
│     ├─ All messages encrypted with ChaCha20-Poly1305        │
│     ├─ Nonce unique per message (12 bytes)                 │
│     └─ Forward secrecy via ephemeral keys                  │
│                                                             │
│  4. Signed HTTP Requests:                                    │
│     ├─ Canonical string: METHOD+PATH+SHA256(body)+...       │
│     ├─ Sign with Ed25519 secret key                         │
│     └─ Include headers: X-Signature, X-Timestamp, etc.       │
│                                                             │
│  5. Credential Decryption:                                   │
│     ├─ Receive sealed credentials (X25519 SealedBox)        │
│     ├─ Convert Ed25519 SK → Curve25519 SK                   │
│     └─ Decrypt DSN and store in env                         │
└─────────────────────────────────────────────────────────────┘
```

## Security Features

### TDX Attestation

Hardware-backed attestation for TEE (Trusted Execution Environment) deployment via WebSocket:

- **Intel TDX**: Uses Intel Trust Domain Extensions for hardware-level isolation
- **Quote Generation**: Generates TDX quotes containing platform measurements
- **Nonce Verification**: Includes nonce in report_data to prevent replay attacks
- **Event Log**: Includes event log for measurement verification

### Encrypted WebSocket

X25519 key exchange with ChaCha20-Poly1305 AEAD encryption for all messages:

- **Key Exchange**: X25519 Diffie-Hellman key exchange for forward secrecy
- **AEAD Encryption**: ChaCha20-Poly1305 authenticated encryption
- **Unique Nonces**: 12-byte nonce per message to prevent reuse
- **HKDF**: HKDF-SHA256 for secure key derivation

### Ed25519 Signing

Canonical request signing with anti-replay protection for HTTP requests:

- **Ed25519**: Uses Ed25519 digital signatures for request authentication
- **Canonical Format**: Standardized string format: `METHOD+PATH+SHA256(body)+timestamp+nonce`
- **Anti-Replay**: Timestamp and nonce prevent replay attacks
- **Header-Based**: Includes `X-Signature`, `X-Timestamp`, `X-Nonce`, `X-Public-Key`

### Sealed Credentials

X25519 SealedBox encryption for database credentials:

- **SealedBox**: Uses NaCl SealedBox for public-key encryption
- **Key Conversion**: Converts Ed25519 secret key to Curve25519 for encryption
- **Credential Isolation**: Database credentials encrypted and only decrypted when needed
- **Environment Storage**: Decrypted DSN stored in environment variables (never in code)

### MinerToken

Ed25519 signed JWT-like tokens for public endpoints:

- **Token Format**: JSON Web Token-like structure with Ed25519 signature
- **Miner Authentication**: Verifies miner identity and permissions
- **Proxy Verification**: Platform API proxies and verifies tokens before forwarding
- **Header Injection**: Platform API injects verified miner information in headers

### Forward Secrecy

Ephemeral keys for each session:

- **Ephemeral Keys**: New X25519 keypair generated for each WebSocket session
- **Session Isolation**: Each session has independent encryption keys
- **Key Derivation**: HKDF with random salt ensures unique keys per session

### Nonce Management

Unique nonce per encrypted message:

- **12-Byte Nonces**: Each encrypted message uses a unique 12-byte nonce
- **CSPRNG**: Nonces generated using `os.urandom()` for cryptographic security
- **No Reuse**: Nonces are never reused within a session

## CSPRNG Key Generation

Keys are generated using `secrets.token_bytes()` which calls `os.urandom()`:

```python
import secrets
from nacl import signing

seed = secrets.token_bytes(32)  # CSPRNG from system entropy
signer = signing.SigningKey(seed)
```

This ensures cryptographically secure random number generation from system entropy.

## Security Best Practices

1. **Never commit secrets**: Database credentials and ephemeral keys are never committed to version control
2. **Use sealed credentials**: Always use sealed credentials for database access
3. **Verify signatures**: Always verify Ed25519 signatures on HTTP requests
4. **Validate attestation**: Verify TDX quotes before trusting the challenge environment
5. **Secure nonces**: Use cryptographically secure random number generators for nonces
6. **Forward secrecy**: Use ephemeral keys for each session
7. **Unique nonces**: Never reuse nonces for encryption

## Threat Model

The Challenge SDK is designed to protect against:

- **Eavesdropping**: All communication is encrypted end-to-end
- **Tampering**: Message authentication prevents tampering
- **Replay Attacks**: Nonces and timestamps prevent replay attacks
- **Man-in-the-Middle**: TDX attestation and mutual authentication prevent MITM
- **Credential Theft**: Sealed credentials prevent credential exposure
- **Unauthorized Access**: MinerToken and signature verification prevent unauthorized access

## See Also

- [Architecture](architecture.md) - System architecture overview
- [API Reference](api-reference.md) - Security-related API methods
- [Troubleshooting](troubleshooting.md) - Security-related troubleshooting

