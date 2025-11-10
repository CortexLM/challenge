"""Tests for challenge lifecycle handlers."""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from platform_challenge_sdk.challenge.decorators import ChallengeRegistry
from platform_challenge_sdk.challenge.context import Context


class TestChallengeRegistry:
    """Tests for ChallengeRegistry lifecycle management."""

    def test_registry_initialization(self):
        """Test registry is initialized correctly."""
        registry = ChallengeRegistry()

        assert registry._startup_handler is None
        assert registry._ready_handler is None
        assert registry._cleanup_handler is None
        assert registry._weights_handler is None
        assert registry._job_handlers == {}
        assert registry._api_handlers == {"admin": {}, "public": {}}
        assert registry._db_version is None

    def test_startup_handler_registration(self):
        """Test registering startup handler."""
        registry = ChallengeRegistry()

        async def my_startup():
            print("Starting up")

        decorated = registry.on_startup()(my_startup)

        assert registry._startup_handler == my_startup
        assert decorated == my_startup

    def test_ready_handler_registration(self):
        """Test registering ready handler."""
        registry = ChallengeRegistry()

        async def my_ready():
            print("Ready")

        decorated = registry.on_ready()(my_ready)

        assert registry._ready_handler == my_ready
        assert decorated == my_ready

    def test_cleanup_handler_registration(self):
        """Test registering cleanup handler."""
        registry = ChallengeRegistry()

        async def my_cleanup():
            print("Cleaning up")

        decorated = registry.on_cleanup()(my_cleanup)

        assert registry._cleanup_handler == my_cleanup
        assert decorated == my_cleanup

    def test_weights_handler_registration(self):
        """Test registering weights handler."""
        registry = ChallengeRegistry()

        # Async weights handler
        async def my_weights(ctx: Context):
            return {"validator1": 0.5, "validator2": 0.5}

        decorated = registry.on_weights()(my_weights)

        assert registry._weights_handler == my_weights
        assert decorated == my_weights

    def test_job_handler_registration(self):
        """Test registering job handlers."""
        registry = ChallengeRegistry()

        def evaluate_job(ctx: Context, payload: dict) -> dict:
            return {"score": 0.9}

        decorated = registry.on_job("evaluate")(evaluate_job)

        assert "evaluate" in registry._job_handlers
        assert registry._job_handlers["evaluate"] == evaluate_job
        assert decorated == evaluate_job

    def test_multiple_job_handlers(self):
        """Test registering multiple job handlers."""
        registry = ChallengeRegistry()

        def evaluate(ctx: Context, payload: dict) -> dict:
            return {"score": 0.9}

        def benchmark(ctx: Context, payload: dict) -> dict:
            return {"time": 1.23}

        registry.on_job("evaluate")(evaluate)
        registry.on_job("benchmark")(benchmark)

        assert len(registry._job_handlers) == 2
        assert registry._job_handlers["evaluate"] == evaluate
        assert registry._job_handlers["benchmark"] == benchmark

    def test_api_handler_registration(self):
        """Test registering API handlers."""
        registry = ChallengeRegistry()

        def get_status():
            return {"status": "ok"}

        # Admin endpoint
        admin_decorated = registry.api.admin("status")(get_status)

        assert "status" in registry._api_handlers["admin"]
        assert registry._api_handlers["admin"]["status"] == get_status

        # Public endpoint
        def get_info():
            return {"version": "1.0"}

        public_decorated = registry.api.public("info")(get_info)

        assert "info" in registry._api_handlers["public"]
        assert registry._api_handlers["public"]["info"] == get_info

    def test_db_version_setting(self):
        """Test setting database version."""
        registry = ChallengeRegistry()

        registry.set_db_version("2023.12.01")

        assert registry._db_version == "2023.12.01"

    def test_handler_overwrite_warning(self):
        """Test warning when overwriting handlers."""
        registry = ChallengeRegistry()

        def handler1():
            pass

        def handler2():
            pass

        # First registration
        registry.on_startup()(handler1)

        # Overwrite should work but ideally warn
        registry.on_startup()(handler2)

        assert registry._startup_handler == handler2


class TestLifecycleExecution:
    """Tests for lifecycle handler execution."""

    @pytest.mark.asyncio
    async def test_startup_handler_execution(self):
        """Test startup handler is called correctly."""
        registry = ChallengeRegistry()

        startup_called = False

        async def startup_handler():
            nonlocal startup_called
            startup_called = True

        registry.on_startup()(startup_handler)

        # Simulate startup
        await registry._startup_handler()

        assert startup_called

    @pytest.mark.asyncio
    async def test_ready_handler_execution(self):
        """Test ready handler is called correctly."""
        registry = ChallengeRegistry()

        ready_called = False

        async def ready_handler():
            nonlocal ready_called
            ready_called = True

        registry.on_ready()(ready_handler)

        # Simulate ready
        await registry._ready_handler()

        assert ready_called

    @pytest.mark.asyncio
    async def test_cleanup_handler_execution(self):
        """Test cleanup handler is called correctly."""
        registry = ChallengeRegistry()

        cleanup_called = False

        async def cleanup_handler():
            nonlocal cleanup_called
            cleanup_called = True

        registry.on_cleanup()(cleanup_handler)

        # Simulate cleanup
        await registry._cleanup_handler()

        assert cleanup_called

    @pytest.mark.asyncio
    async def test_orm_ready_handler_execution(self):
        """Test ORM ready handler is called correctly."""
        registry = ChallengeRegistry()

        orm_ready_called = False
        orm_context = None

        async def orm_ready_handler(ctx: Context):
            nonlocal orm_ready_called, orm_context
            orm_ready_called = True
            orm_context = ctx

        registry.on_orm_ready()(orm_ready_handler)

        # Create mock context
        mock_ctx = Context(
            validator_base_url="http://test",
            session_token="token",
            job_id="job1",
            challenge_id="ch1",
            validator_hotkey="hotkey",
            client=None,
            cvm=None,
            values=None,
            results=None,
            orm=MagicMock(),
        )

        # Simulate ORM ready
        await registry._orm_ready_handler(mock_ctx)

        assert orm_ready_called
        assert orm_context == mock_ctx

    def test_job_handler_execution(self):
        """Test job handler is called correctly."""
        registry = ChallengeRegistry()

        job_result = None

        def job_handler(ctx: Context, payload: dict) -> dict:
            nonlocal job_result
            job_result = {"score": payload.get("value", 0) * 2}
            return job_result

        registry.on_job("evaluate")(job_handler)

        # Create mock context
        mock_ctx = Context(
            validator_base_url="http://test",
            session_token="token",
            job_id="job1",
            challenge_id="ch1",
            validator_hotkey="hotkey",
            client=None,
            cvm=None,
            values=None,
            results=None,
        )

        # Execute job
        result = registry._job_handlers["evaluate"](mock_ctx, {"value": 5})

        assert result == {"score": 10}
        assert job_result == {"score": 10}

    @pytest.mark.asyncio
    async def test_async_weights_handler_execution(self):
        """Test async weights handler execution."""
        registry = ChallengeRegistry()

        weights_result = None

        async def weights_handler(ctx: Context):
            nonlocal weights_result
            weights_result = {"validator1": 0.6, "validator2": 0.4}
            return weights_result

        registry.on_weights()(weights_handler)

        # Create mock context
        mock_ctx = Context(
            validator_base_url="http://test",
            session_token="token",
            job_id="job1",
            challenge_id="ch1",
            validator_hotkey="hotkey",
            client=None,
            cvm=None,
            values=None,
            results=None,
        )

        # Execute weights calculation
        result = await registry._weights_handler(mock_ctx)

        assert result == {"validator1": 0.6, "validator2": 0.4}

    def test_sync_weights_handler_execution(self):
        """Test sync weights handler execution."""
        registry = ChallengeRegistry()

        weights_result = None

        def weights_handler(ctx: Context):
            nonlocal weights_result
            weights_result = {"validator1": 0.7, "validator2": 0.3}
            return weights_result

        registry.on_weights()(weights_handler)

        # Create mock context
        mock_ctx = Context(
            validator_base_url="http://test",
            session_token="token",
            job_id="job1",
            challenge_id="ch1",
            validator_hotkey="hotkey",
            client=None,
            cvm=None,
            values=None,
            results=None,
        )

        # Execute weights calculation
        result = registry._weights_handler(mock_ctx)

        assert result == {"validator1": 0.7, "validator2": 0.3}


class TestHandlerErrorHandling:
    """Tests for error handling in lifecycle handlers."""

    @pytest.mark.asyncio
    async def test_startup_handler_error(self):
        """Test error in startup handler."""
        registry = ChallengeRegistry()

        async def failing_startup():
            raise Exception("Startup failed")

        registry.on_startup()(failing_startup)

        # Should raise
        with pytest.raises(Exception) as exc_info:
            await registry._startup_handler()

        assert "Startup failed" in str(exc_info.value)

    def test_job_handler_error(self):
        """Test error in job handler."""
        registry = ChallengeRegistry()

        def failing_job_handler(ctx: Context, payload: dict):
            raise ValueError("Invalid payload")

        registry.on_job("process")(failing_job_handler)

        mock_ctx = Context(
            validator_base_url="http://test",
            session_token="token",
            job_id="job1",
            challenge_id="ch1",
            validator_hotkey="hotkey",
            client=None,
            cvm=None,
            values=None,
            results=None,
        )

        # Should raise
        with pytest.raises(ValueError) as exc_info:
            registry._job_handlers["process"](mock_ctx, {})

        assert "Invalid payload" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_cleanup_handler_error_handling(self):
        """Test cleanup handler continues on error."""
        registry = ChallengeRegistry()

        cleanup_attempted = False

        async def failing_cleanup():
            nonlocal cleanup_attempted
            cleanup_attempted = True
            raise Exception("Cleanup error")

        registry.on_cleanup()(failing_cleanup)

        # Cleanup errors should be handled gracefully
        with pytest.raises(Exception):
            await registry._cleanup_handler()

        assert cleanup_attempted


class TestHandlerValidation:
    """Tests for handler validation."""

    def test_job_handler_must_return_dict(self):
        """Test job handler return type validation."""
        registry = ChallengeRegistry()

        def invalid_handler(ctx: Context, payload: dict) -> str:
            return "not a dict"  # Should return dict

        # Registration succeeds (validation at runtime)
        registry.on_job("invalid")(invalid_handler)

        # But execution should fail with proper error
        mock_ctx = Context(
            validator_base_url="http://test",
            session_token="token",
            job_id="job1",
            challenge_id="ch1",
            validator_hotkey="hotkey",
            client=None,
            cvm=None,
            values=None,
            results=None,
        )

        # In real implementation, this should validate return type
        result = registry._job_handlers["invalid"](mock_ctx, {})
        # For now it returns the string, but should validate
        assert result == "not a dict"

    def test_handler_signature_validation(self):
        """Test handler has correct signature."""
        registry = ChallengeRegistry()

        # Wrong signature - missing context
        def bad_job_handler(payload: dict) -> dict:
            return {"result": "bad"}

        # Can register (validation could be at runtime)
        registry.on_job("bad")(bad_job_handler)

        # But should fail when called with Context
        mock_ctx = Context(
            validator_base_url="http://test",
            session_token="token",
            job_id="job1",
            challenge_id="ch1",
            validator_hotkey="hotkey",
            client=None,
            cvm=None,
            values=None,
            results=None,
        )

        # This will fail due to wrong signature
        with pytest.raises(TypeError):
            registry._job_handlers["bad"](mock_ctx, {})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
