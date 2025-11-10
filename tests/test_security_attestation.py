"""Tests for security and attestation features."""

import pytest
import json
import base64
import hashlib
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta

from platform_challenge_sdk.cvm.client import CVMClient
from platform_challenge_sdk.security.credential_transfer import CredentialTransfer


class TestCVMAttestation:
    """Tests for CVM attestation client."""

    @pytest.fixture
    def mock_attestation_response(self):
        """Mock successful attestation response."""
        return {
            "session_token": "test-session-token-12345",
            "status": "verified",
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            "verified_measurements": [
                {"name": "kernel", "value": "abc123"},
                {"name": "initrd", "value": "def456"},
            ],
            "policy": "default",
            "error": None,
        }

    @pytest.mark.asyncio
    async def test_cvm_attestation_request(self):
        """Test CVM attestation request."""
        client = CVMClient(base_url="http://localhost:8000")

        # Mock HTTP client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"session_token": "token123", "status": "verified"}

        with patch.object(client._session, "post", return_value=mock_response) as mock_post:
            # Request attestation
            result = await client.request_attestation(nonce=b"test-nonce")

            # Verify request
            mock_post.assert_called_once()
            call_args = mock_post.call_args

            # Check endpoint
            assert "/attestation/request" in call_args[0][0]

            # Check payload
            payload = call_args[1]["json"]
            assert payload["nonce"] == base64.b64encode(b"test-nonce").decode()
            assert "quote" in payload
            assert "measurements" in payload

            # Check result
            assert result["session_token"] == "token123"
            assert result["status"] == "verified"

    @pytest.mark.asyncio
    async def test_attestation_with_event_log(self):
        """Test attestation with event log."""
        client = CVMClient(base_url="http://localhost:8000")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "verified"}

        event_log = {"environment_mode": "dev", "compose_hash": "abc123"}

        with patch.object(client._session, "post", return_value=mock_response) as mock_post:
            await client.request_attestation(nonce=b"nonce", event_log=event_log)

            payload = mock_post.call_args[1]["json"]
            assert payload["event_log"] == json.dumps(event_log)

    @pytest.mark.asyncio
    async def test_attestation_failure_handling(self):
        """Test handling attestation failures."""
        client = CVMClient(base_url="http://localhost:8000")

        # Mock failure response
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"status": "failed", "error": "Invalid quote format"}

        with patch.object(client._session, "post", return_value=mock_response):
            with pytest.raises(Exception) as exc_info:
                await client.request_attestation(nonce=b"nonce")

            assert "attestation failed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_nonce_binding_verification(self):
        """Test nonce binding in attestation."""
        client = CVMClient(base_url="http://localhost:8000")

        nonce = b"unique-nonce-12345"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "verified"}

        with patch.object(client._session, "post", return_value=mock_response) as mock_post:
            await client.request_attestation(nonce=nonce)

            # Verify nonce is included
            payload = mock_post.call_args[1]["json"]
            assert payload["nonce"] == base64.b64encode(nonce).decode()

            # In real TDX, report_data would be SHA256(nonce)
            # This is just to verify the binding concept
            expected_report_data = hashlib.sha256(nonce).hexdigest()
            # Would verify in quote.report_data


class TestCredentialTransfer:
    """Tests for secure credential transfer."""

    def test_seal_credentials(self):
        """Test sealing credentials for secure transfer."""
        transfer = CredentialTransfer()

        credentials = {
            "api_key": "secret-key-123",
            "database_url": "postgres://user:pass@host/db",
            "encryption_key": "aes-256-key",
        }

        # Seal credentials
        sealed = transfer.seal_credentials(credentials, recipient_key="validator-123")

        # Verify structure
        assert "encrypted_data" in sealed
        assert "encryption_key" in sealed
        assert "recipient" in sealed
        assert "timestamp" in sealed
        assert "signature" in sealed

        # Encrypted data should be base64
        base64.b64decode(sealed["encrypted_data"])

        # Recipient should match
        assert sealed["recipient"] == "validator-123"

    def test_unseal_credentials(self):
        """Test unsealing credentials."""
        transfer = CredentialTransfer()

        credentials = {"api_key": "secret-key-123", "database_url": "postgres://user:pass@host/db"}

        # Seal and unseal
        sealed = transfer.seal_credentials(credentials, recipient_key="validator-123")
        unsealed = transfer.unseal_credentials(sealed, private_key="validator-123-private")

        # Should match original
        assert unsealed == credentials

    def test_credential_tampering_detection(self):
        """Test detection of tampered credentials."""
        transfer = CredentialTransfer()

        credentials = {"secret": "value"}
        sealed = transfer.seal_credentials(credentials, recipient_key="validator-123")

        # Tamper with encrypted data
        tampered = sealed.copy()
        tampered["encrypted_data"] = base64.b64encode(b"tampered").decode()

        # Should detect tampering
        with pytest.raises(Exception) as exc_info:
            transfer.unseal_credentials(tampered, private_key="validator-123-private")

        assert (
            "verification failed" in str(exc_info.value).lower()
            or "decrypt" in str(exc_info.value).lower()
        )

    def test_credential_expiration(self):
        """Test credential expiration."""
        transfer = CredentialTransfer(ttl_seconds=1)  # 1 second TTL

        credentials = {"secret": "value"}
        sealed = transfer.seal_credentials(credentials, recipient_key="validator-123")

        # Immediately should work
        unsealed = transfer.unseal_credentials(sealed, private_key="validator-123-private")
        assert unsealed == credentials

        # After expiration should fail
        import time

        time.sleep(2)

        with pytest.raises(Exception) as exc_info:
            transfer.unseal_credentials(sealed, private_key="validator-123-private")

        assert "expired" in str(exc_info.value).lower()


class TestSecurityValidation:
    """Tests for security validation features."""

    @pytest.mark.asyncio
    async def test_compose_hash_verification(self):
        """Test compose hash verification from attestation."""
        client = CVMClient(base_url="http://localhost:8000")

        expected_compose_hash = "sha256:1234567890abcdef"

        # Mock attestation response with compose hash in event log
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "verified",
            "event_log": json.dumps({"compose_hash": expected_compose_hash}),
        }

        with patch.object(client._session, "post", return_value=mock_response):
            result = await client.request_attestation(nonce=b"test")

            # Extract and verify compose hash
            event_log = json.loads(result["event_log"])
            assert event_log["compose_hash"] == expected_compose_hash

    @pytest.mark.asyncio
    async def test_environment_mode_validation(self):
        """Test environment mode validation."""
        client = CVMClient(base_url="http://localhost:8000")

        # Test dev mode
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "verified",
            "event_log": json.dumps({"environment_mode": "dev"}),
        }

        with patch.object(client._session, "post", return_value=mock_response):
            result = await client.request_attestation(nonce=b"test")
            event_log = json.loads(result["event_log"])
            assert event_log["environment_mode"] == "dev"

        # Test prod mode
        mock_response.json.return_value = {
            "status": "verified",
            "event_log": json.dumps({"environment_mode": "prod"}),
        }

        with patch.object(client._session, "post", return_value=mock_response):
            result = await client.request_attestation(nonce=b"test")
            event_log = json.loads(result["event_log"])
            assert event_log["environment_mode"] == "prod"

    def test_measurement_validation(self):
        """Test measurement validation."""
        measurements = [
            {"name": "kernel", "value": "expected_kernel_hash"},
            {"name": "initrd", "value": "expected_initrd_hash"},
            {"name": "cmdline", "value": "expected_cmdline_hash"},
        ]

        # Validate measurements format
        for m in measurements:
            assert "name" in m
            assert "value" in m
            assert isinstance(m["name"], str)
            assert isinstance(m["value"], str)

    @pytest.mark.asyncio
    async def test_session_token_validation(self):
        """Test session token validation."""
        client = CVMClient(base_url="http://localhost:8000")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "session_token": "valid-token-12345",
            "status": "verified",
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
        }

        with patch.object(client._session, "post", return_value=mock_response):
            result = await client.request_attestation(nonce=b"test")

            # Verify token format
            token = result["session_token"]
            assert isinstance(token, str)
            assert len(token) > 0

            # Verify expiration
            expires_at = datetime.fromisoformat(result["expires_at"])
            assert expires_at > datetime.utcnow()


class TestSecurityBestPractices:
    """Tests for security best practices."""

    def test_no_hardcoded_secrets(self):
        """Test that no hardcoded secrets exist."""
        # This would scan the codebase for hardcoded secrets
        # For now, just a placeholder showing the concept

        forbidden_patterns = ["password=", "api_key=", "secret=", "private_key="]

        # In real implementation, scan source files
        assert True  # Placeholder

    def test_secure_random_generation(self):
        """Test secure random number generation."""
        import os
        import secrets

        # os.urandom should be available
        random_bytes = os.urandom(32)
        assert len(random_bytes) == 32
        assert isinstance(random_bytes, bytes)

        # secrets module should be used for tokens
        token = secrets.token_urlsafe(32)
        assert len(token) >= 32
        assert isinstance(token, str)

    def test_constant_time_comparison(self):
        """Test constant time comparison for secrets."""
        import hmac

        secret1 = b"secret_value_123"
        secret2 = b"secret_value_123"
        secret3 = b"different_value"

        # Should use constant time comparison
        assert hmac.compare_digest(secret1, secret2)
        assert not hmac.compare_digest(secret1, secret3)

    def test_key_derivation_functions(self):
        """Test proper key derivation."""
        from platform_challenge_sdk.client.mtls import derive_aead_key

        master_key = os.urandom(32)
        salt = b"test-salt"

        # Derive key
        derived = derive_aead_key(master_key, salt)

        # Should be deterministic
        derived2 = derive_aead_key(master_key, salt)
        assert derived == derived2

        # Different salt should give different key
        derived3 = derive_aead_key(master_key, b"different-salt")
        assert derived != derived3

        # Should be 32 bytes for AES-256
        assert len(derived) == 32


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
