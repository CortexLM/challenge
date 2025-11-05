"""Security validation tests for challenge SDK.

Tests TDX quote verification, mutual attestation, and environment isolation.
"""

import pytest
import base64
import hashlib
import secrets
import json
from platform_challenge_sdk.transport.ws import verify_validator_quote


@pytest.mark.asyncio
async def test_validator_quote_verification_structure():
    """Test that validator quote structure is validated."""
    # Create a mock quote with correct structure
    mock_quote = secrets.token_bytes(1024)  # Minimum TDX quote size
    quote_b64 = base64.b64encode(mock_quote).decode("ascii")
    
    # Embed report_data at offset 568
    nonce = secrets.token_bytes(32)
    report_data = hashlib.sha256(nonce).digest()[:32]
    mock_quote_bytes = bytearray(mock_quote)
    mock_quote_bytes[568:568+32] = report_data
    quote_b64_valid = base64.b64encode(bytes(mock_quote_bytes)).decode("ascii")
    
    # Test with valid structure
    result = await verify_validator_quote(
        quote_b64_valid,
        json.dumps({"environment_mode": "dev"}),
        None,
        nonce,
        True,  # dev_mode
        "dev",  # challenge_env_mode
    )
    
    assert result["valid"], f"Valid quote should pass: {result.get('error')}"


@pytest.mark.asyncio
async def test_validator_quote_too_short():
    """Test that quote too short is rejected."""
    short_quote = secrets.token_bytes(100)  # Too short
    quote_b64 = base64.b64encode(short_quote).decode("ascii")
    
    nonce = secrets.token_bytes(32)
    result = await verify_validator_quote(
        quote_b64,
        None,
        None,
        nonce,
        True,
        "dev",
    )
    
    assert not result["valid"], "Quote too short should be rejected"
    assert "too short" in result.get("error", "").lower()


@pytest.mark.asyncio
async def test_environment_isolation_dev_prod():
    """Test that dev and prod environments cannot communicate."""
    mock_quote = secrets.token_bytes(1024)
    nonce = secrets.token_bytes(32)
    report_data = hashlib.sha256(nonce).digest()[:32]
    mock_quote_bytes = bytearray(mock_quote)
    mock_quote_bytes[568:568+32] = report_data
    quote_b64 = base64.b64encode(bytes(mock_quote_bytes)).decode("ascii")
    
    # Validator in dev, challenge in prod
    result = await verify_validator_quote(
        quote_b64,
        json.dumps({"environment_mode": "dev"}),
        None,
        nonce,
        False,  # production mode
        "prod",  # challenge in prod
    )
    
    assert not result["valid"], "Dev validator should not connect to prod challenge"
    assert "environment mismatch" in result.get("error", "").lower() or "dev.*prod" in result.get("error", "").lower()


@pytest.mark.asyncio
async def test_nonce_binding_verification():
    """Test that nonce binding is verified."""
    mock_quote = secrets.token_bytes(1024)
    nonce = secrets.token_bytes(32)
    
    # Create quote with wrong report_data
    wrong_report_data = secrets.token_bytes(32)
    mock_quote_bytes = bytearray(mock_quote)
    mock_quote_bytes[568:568+32] = wrong_report_data
    quote_b64 = base64.b64encode(bytes(mock_quote_bytes)).decode("ascii")
    
    result = await verify_validator_quote(
        quote_b64,
        json.dumps({"environment_mode": "dev"}),
        None,
        nonce,
        True,
        "dev",
    )
    
    assert not result["valid"], "Quote with wrong nonce binding should be rejected"
    assert "nonce" in result.get("error", "").lower() or "report_data" in result.get("error", "").lower()


@pytest.mark.asyncio
async def test_environment_match_dev_dev():
    """Test that dev to dev connection is allowed."""
    mock_quote = secrets.token_bytes(1024)
    nonce = secrets.token_bytes(32)
    report_data = hashlib.sha256(nonce).digest()[:32]
    mock_quote_bytes = bytearray(mock_quote)
    mock_quote_bytes[568:568+32] = report_data
    quote_b64 = base64.b64encode(bytes(mock_quote_bytes)).decode("ascii")
    
    result = await verify_validator_quote(
        quote_b64,
        json.dumps({"environment_mode": "dev"}),
        None,
        nonce,
        True,  # dev_mode
        "dev",  # challenge in dev
    )
    
    assert result["valid"], "Dev to dev connection should be allowed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

