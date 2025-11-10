"""Tests for WebSocket encryption using X25519/XChaCha20-Poly1305."""

import pytest
import asyncio
import json
import base64
import os
from unittest.mock import AsyncMock, MagicMock, patch
from nacl.public import PrivateKey, PublicKey
from nacl.bindings import crypto_scalarmult, crypto_scalarmult_base
from Crypto.Cipher import ChaCha20_Poly1305

from platform_challenge_sdk.transport.ws import AeadSession, SecureWebSocketTransport


class TestAeadSession:
    """Tests for AEAD encryption/decryption."""

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encryption and decryption work correctly."""
        # Generate a random key
        key = os.urandom(32)
        session = AeadSession(key)

        # Test data
        test_obj = {
            "type": "test",
            "data": "Hello, world!",
            "nested": {"value": 42, "array": [1, 2, 3]},
        }

        # Encrypt
        envelope = session.encrypt(test_obj)

        # Verify envelope structure
        assert envelope["enc"] == "chacha20poly1305"
        assert "nonce" in envelope
        assert "ciphertext" in envelope

        # Decrypt
        decrypted = session.decrypt(envelope)

        # Verify data matches
        assert decrypted == test_obj

    def test_encrypt_creates_unique_nonces(self):
        """Test that each encryption uses a unique nonce."""
        key = os.urandom(32)
        session = AeadSession(key)

        data = {"test": "data"}

        # Encrypt same data multiple times
        envelopes = [session.encrypt(data) for _ in range(10)]

        # Extract nonces
        nonces = [env["nonce"] for env in envelopes]

        # Verify all nonces are unique
        assert len(set(nonces)) == len(nonces)

    def test_decrypt_with_invalid_data_fails(self):
        """Test that decryption fails with tampered data."""
        key = os.urandom(32)
        session = AeadSession(key)

        # Create valid envelope
        envelope = session.encrypt({"test": "data"})

        # Tamper with ciphertext
        ct_bytes = base64.b64decode(envelope["ciphertext"])
        tampered_bytes = bytes(b ^ 1 for b in ct_bytes)  # Flip all bits
        envelope["ciphertext"] = base64.b64encode(tampered_bytes).decode("ascii")

        # Decryption should fail
        with pytest.raises(Exception):
            session.decrypt(envelope)

    def test_decrypt_with_wrong_key_fails(self):
        """Test that decryption fails with wrong key."""
        key1 = os.urandom(32)
        key2 = os.urandom(32)

        session1 = AeadSession(key1)
        session2 = AeadSession(key2)

        # Encrypt with key1
        envelope = session1.encrypt({"test": "data"})

        # Try to decrypt with key2
        with pytest.raises(Exception):
            session2.decrypt(envelope)


class TestKeyExchange:
    """Tests for X25519 key exchange."""

    def test_x25519_key_derivation(self):
        """Test X25519 ECDH key derivation."""
        # Generate key pairs
        alice_secret = os.urandom(32)
        bob_secret = os.urandom(32)

        alice_public = crypto_scalarmult_base(alice_secret)
        bob_public = crypto_scalarmult_base(bob_secret)

        # Derive shared secrets
        alice_shared = crypto_scalarmult(alice_secret, bob_public)
        bob_shared = crypto_scalarmult(bob_secret, alice_public)

        # Shared secrets should match
        assert alice_shared == bob_shared

    def test_hkdf_key_derivation(self):
        """Test HKDF key derivation from shared secret."""
        from platform_challenge_sdk.client.mtls import derive_aead_key

        shared_secret = os.urandom(32)
        salt = b"platform-challenge-v1"

        # Derive key
        key = derive_aead_key(shared_secret, salt)

        # Key should be 32 bytes
        assert len(key) == 32

        # Same inputs should produce same key
        key2 = derive_aead_key(shared_secret, salt)
        assert key == key2

        # Different salt should produce different key
        key3 = derive_aead_key(shared_secret, b"different-salt")
        assert key != key3


class TestSecureWebSocketTransport:
    """Tests for secure WebSocket transport."""

    @pytest.mark.asyncio
    async def test_handshake_establishes_encryption(self):
        """Test that handshake establishes encrypted session."""
        transport = SecureWebSocketTransport()

        # Mock WebSocket
        mock_ws = AsyncMock()
        mock_ws.recv = AsyncMock()
        mock_ws.send = AsyncMock()

        # Simulate server handshake response
        server_secret = os.urandom(32)
        server_public = base64.b64encode(crypto_scalarmult_base(server_secret)).decode()

        mock_ws.recv.side_effect = [
            json.dumps({"type": "handshake", "server_public_key": server_public})
        ]

        transport._ws = mock_ws

        # Perform handshake
        session = await transport._perform_handshake()

        # Session should be established
        assert isinstance(session, AeadSession)
        assert session._key is not None

        # Client should have sent its public key
        mock_ws.send.assert_called_once()
        sent_data = json.loads(mock_ws.send.call_args[0][0])
        assert sent_data["type"] == "handshake_init"
        assert "client_public_key" in sent_data

    @pytest.mark.asyncio
    async def test_send_encrypts_messages(self):
        """Test that send encrypts messages."""
        transport = SecureWebSocketTransport()

        # Mock WebSocket and session
        mock_ws = AsyncMock()
        transport._ws = mock_ws

        # Create session with known key
        key = os.urandom(32)
        transport._session = AeadSession(key)

        # Send message
        test_msg = {"type": "test", "data": "secret"}
        await transport.send(test_msg)

        # Message should be encrypted
        mock_ws.send.assert_called_once()
        sent_data = json.loads(mock_ws.send.call_args[0][0])

        # Should be encrypted envelope
        assert "enc" in sent_data
        assert sent_data["enc"] == "chacha20poly1305"
        assert "nonce" in sent_data
        assert "ciphertext" in sent_data

        # Decrypt to verify
        session = AeadSession(key)
        decrypted = session.decrypt(sent_data)
        assert decrypted == test_msg

    @pytest.mark.asyncio
    async def test_receive_decrypts_messages(self):
        """Test that receive decrypts messages."""
        transport = SecureWebSocketTransport()

        # Mock WebSocket
        mock_ws = AsyncMock()
        transport._ws = mock_ws

        # Create session with known key
        key = os.urandom(32)
        transport._session = AeadSession(key)

        # Create encrypted message
        session = AeadSession(key)
        test_msg = {"type": "test", "data": "secret"}
        encrypted = session.encrypt(test_msg)

        # Mock receiving encrypted message
        mock_ws.recv.return_value = json.dumps(encrypted)

        # Receive message
        received = await transport.receive()

        # Should decrypt correctly
        assert received == test_msg

    @pytest.mark.asyncio
    async def test_unencrypted_system_messages_pass_through(self):
        """Test that system messages are not encrypted."""
        transport = SecureWebSocketTransport()

        # Mock WebSocket
        mock_ws = AsyncMock()
        transport._ws = mock_ws
        transport._session = AeadSession(os.urandom(32))

        # System messages that should pass through
        system_msgs = [
            {"type": "ping"},
            {"type": "pong"},
            {"type": "handshake", "data": "test"},
            {"type": "handshake_init", "data": "test"},
        ]

        for msg in system_msgs:
            # Clear mock
            mock_ws.send.reset_mock()

            # Send system message
            await transport.send(msg)

            # Should not be encrypted
            mock_ws.send.assert_called_once()
            sent_data = json.loads(mock_ws.send.call_args[0][0])
            assert sent_data == msg  # Should be unchanged

    @pytest.mark.asyncio
    async def test_connection_retry_logic(self):
        """Test connection retry with backoff."""
        transport = SecureWebSocketTransport()

        # Mock connect to fail initially
        attempt_count = 0

        async def mock_connect(uri):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise Exception("Connection failed")
            # Return mock WebSocket on 3rd attempt
            mock_ws = AsyncMock()
            mock_ws.recv = AsyncMock(
                side_effect=[
                    json.dumps(
                        {
                            "type": "handshake",
                            "server_public_key": base64.b64encode(os.urandom(32)).decode(),
                        }
                    )
                ]
            )
            return mock_ws

        with patch("websockets.connect", mock_connect):
            # Connect with retry
            await transport.connect("ws://test", max_retries=5)

            # Should have retried
            assert attempt_count == 3
            assert transport._ws is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
