"""Secure WebSocket client for encrypted communication with platform-api."""

import asyncio
import base64
import hashlib
import json
import secrets
from collections.abc import Awaitable, Callable
from typing import Any

from nacl.bindings import crypto_scalarmult, crypto_scalarmult_base

from ..client.mtls import derive_aead_key

try:
    import websockets
    from websockets.client import WebSocketClientProtocol
except ImportError:
    websockets = None
    WebSocketClientProtocol = None


class AeadSession:
    """AEAD session for encrypting/decrypting messages."""

    def __init__(self, aead_key: bytes):
        self._key = aead_key

    def encrypt(self, obj: Any) -> dict[str, str]:
        """Encrypt an object using ChaCha20-Poly1305."""
        from Crypto.Cipher import ChaCha20_Poly1305

        nonce = secrets.token_bytes(12)
        cipher = ChaCha20_Poly1305.new(key=self._key, nonce=nonce)
        plaintext = json.dumps(obj).encode("utf-8")
        ciphertext, tag = cipher.encrypt_and_digest(plaintext)
        return {
            "enc": "chacha20poly1305",
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext + tag).decode("ascii"),
        }

    def decrypt(self, env: dict[str, Any]) -> Any:
        """Decrypt an encrypted envelope."""
        from Crypto.Cipher import ChaCha20_Poly1305

        if env.get("enc") != "chacha20poly1305":
            raise ValueError("unsupported enc")
        nonce = base64.b64decode(env["nonce"])  # 12B
        data = base64.b64decode(env["ciphertext"])  # ct||tag
        if len(nonce) != 12 or len(data) < 16:
            raise ValueError("invalid envelope")
        ct, tag = data[:-16], data[-16:]
        cipher = ChaCha20_Poly1305.new(key=self._key, nonce=nonce)
        pt = cipher.decrypt_and_verify(ct, tag)
        return json.loads(pt.decode("utf-8"))


class SecureWebSocketClient:
    """Secure WebSocket client with TDX attestation and encrypted messaging."""

    def __init__(self, url: str, platform_api_id: str = "platform-api"):
        """Initialize secure WebSocket client.

        Args:
            url: WebSocket URL (e.g., "wss://host:port/sdk/ws")
            platform_api_id: Platform API identifier
        """
        if websockets is None:
            raise ImportError("websockets package is required")

        self.url = url
        self.platform_api_id = platform_api_id
        self.websocket: WebSocketClientProtocol | None = None
        self.session: AeadSession | None = None
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._response_handlers: dict[str, asyncio.Future] = {}
        self._running = False

    async def connect(
        self, quote_provider: Callable[[bytes], Awaitable[tuple]] | None = None
    ) -> None:
        """Connect to WebSocket and perform TDX attestation.

        Args:
            quote_provider: Optional async function to get TDX quote (report_data) -> (quote, event_log, rtmrs)
        """
        # Connect WebSocket
        self.websocket = await websockets.connect(self.url)

        # Generate nonce for attestation
        nonce_bytes = secrets.token_bytes(32)
        nonce_hex = nonce_bytes.hex()

        # Generate challenge X25519 keypair
        chal_sk = secrets.token_bytes(32)
        chal_pub = crypto_scalarmult_base(chal_sk)
        chal_pub_b64 = base64.b64encode(chal_pub).decode("ascii")

        # Get TDX quote if provider available
        quote = None
        event_log = None
        rtmrs = None
        if quote_provider:
            report_data = hashlib.sha256(nonce_bytes).digest()[:32]
            quote, event_log, rtmrs = await quote_provider(report_data)

        # Send attestation_begin
        await self.websocket.send(
            json.dumps(
                {
                    "type": "attestation_begin",
                    "nonce": nonce_hex,
                    "platform_api_id": self.platform_api_id,
                    "val_x25519_pub": chal_pub_b64,
                }
            )
        )

        # Wait for attestation_response
        response_raw = await self.websocket.recv()
        response = json.loads(response_raw)

        if response.get("type") != "attestation_response":
            raise Exception("Invalid attestation response")

        # Extract platform API public key (can be api_x25519_pub or val_x25519_pub)
        api_pub_b64 = response.get("api_x25519_pub") or response.get("val_x25519_pub")
        if not api_pub_b64:
            raise Exception("Missing platform API public key in attestation_response")

        api_pub = base64.b64decode(api_pub_b64)
        if len(api_pub) != 32:
            raise Exception("Invalid platform API public key length")

        # Derive shared secret
        shared = crypto_scalarmult(chal_sk, api_pub)

        # Wait for attestation_ok
        ok_raw = await self.websocket.recv()
        ok = json.loads(ok_raw)

        if ok.get("type") != "attestation_ok":
            raise Exception("Invalid attestation_ok response")

        # Get HKDF salt
        hkdf_salt_b64 = ok.get("hkdf_salt") or ok.get("hkdf_salt_b64", "")
        if not hkdf_salt_b64:
            raise Exception("Missing HKDF salt")

        # Derive AEAD key
        aead_key = derive_aead_key(shared, hkdf_salt_b64)
        self.session = AeadSession(aead_key)

        # Start message handler loop
        self._running = True
        asyncio.create_task(self._message_handler())

    async def _message_handler(self) -> None:
        """Background task to handle incoming WebSocket messages."""
        try:
            while self._running and self.websocket:
                try:
                    msg_raw = await self.websocket.recv()
                    env = json.loads(msg_raw)
                    msg = self.session.decrypt(env) if self.session else json.loads(msg_raw)

                    # Handle ORM responses
                    msg_type = msg.get("type")
                    if msg_type in ("orm_result", "error"):
                        # Find pending handler
                        if "query_id" in msg:
                            future = self._response_handlers.pop(msg.get("query_id"), None)
                            if future and not future.done():
                                future.set_result(msg)

                    # Put in queue for general handlers
                    await self._message_queue.put(msg)
                except asyncio.CancelledError:
                    break
                except Exception:
                    if self._running:
                        await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass

    async def send_message(self, message: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
        """Send a message and wait for response.

        Args:
            message: Message to send (will be encrypted if session is established)
            timeout: Timeout in seconds

        Returns:
            Response message (decrypted if encrypted)
        """
        if not self.websocket:
            raise Exception("WebSocket not connected")

        # Generate query_id for request/response matching
        query_id = secrets.token_hex(16)
        message["query_id"] = query_id

        # Create future for response
        future = asyncio.Future()
        self._response_handlers[query_id] = future

        # Encrypt and send
        if self.session:
            env = self.session.encrypt(message)
            await self.websocket.send(json.dumps(env))
        else:
            await self.websocket.send(json.dumps(message))

        # Wait for response
        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            self._response_handlers.pop(query_id, None)
            raise Exception(f"Request timeout after {timeout}s") from None

    async def close(self) -> None:
        """Close WebSocket connection."""
        self._running = False
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
