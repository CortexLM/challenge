from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChallengeRegistry:
    start_handler: Callable[[], Awaitable[None] | None] | None = None
    ready_handler: Callable[[], Awaitable[None] | None] | None = None
    orm_ready_handler: Callable[[], Awaitable[None] | None] | None = None
    job_handler: (
        Callable[[Any, dict[str, Any]], dict[str, Any] | Awaitable[dict[str, Any]]] | None
    ) = None
    job_handlers: dict[
        str, Callable[[Any, dict[str, Any]], dict[str, Any] | Awaitable[dict[str, Any]]]
    ] = field(default_factory=dict)
    cleanup_handler: Callable[[Any], None] | None = None
    weights_handler: Callable[[list[dict]], Awaitable[dict] | dict] | None = None
    public_handlers: dict[str, Callable[..., Awaitable[Any] | Any]] = field(default_factory=dict)
    admin_handlers: dict[str, Callable[..., Awaitable[Any] | Any]] = field(default_factory=dict)
    db_version: int | None = None  # Database version set via set_db_version()
    orm_permissions: Any | None = None  # ORMPermissions instance to send to platform-api
    _server_orm_adapter: Any | None = None  # Server-side ORM adapter (internal use)
    message_router: Any | None = None  # MessageRouter instance for global message handling

    def on_startup(
        self,
    ) -> Callable[[Callable[[], Awaitable[None] | None]], Callable[[], Awaitable[None] | None]]:
        def decorator(
            fn: Callable[[], Awaitable[None] | None],
        ) -> Callable[[], Awaitable[None] | None]:
            self.start_handler = fn
            return fn

        return decorator

    def on_ready(
        self,
    ) -> Callable[[Callable[[], Awaitable[None] | None]], Callable[[], Awaitable[None] | None]]:
        def decorator(
            fn: Callable[[], Awaitable[None] | None],
        ) -> Callable[[], Awaitable[None] | None]:
            self.ready_handler = fn
            return fn

        return decorator

    def on_orm_ready(
        self,
    ) -> Callable[[Callable[[], Awaitable[None] | None]], Callable[[], Awaitable[None] | None]]:
        """Register a handler called when ORM bridge is ready (after migrations).

        This handler is triggered when platform-api sends the 'orm_ready' signal,
        indicating that migrations have been applied and the ORM bridge is ready for use.
        """

        def decorator(
            fn: Callable[[], Awaitable[None] | None],
        ) -> Callable[[], Awaitable[None] | None]:
            self.orm_ready_handler = fn
            return fn

        return decorator

    def on_start(
        self,
    ) -> Callable[
        [Callable[[Any], Awaitable[None] | None]], Callable[[Any], Awaitable[None] | None]
    ]:
        def decorator(
            fn: Callable[[Any], Awaitable[None] | None],
        ) -> Callable[[Any], Awaitable[None] | None]:
            self.start_handler = fn
            return fn

        return decorator

    def on_job(self, job_name: str | None = None) -> Callable:
        """Register a named job handler.

        Usage:
            @challenge.on_job("evaluate_agent")  # Named handler
            def evaluate_agent(ctx, payload): ...

            @challenge.on_job()  # Default handler (backward compatibility)
            def default_job(ctx, payload): ...
        """

        def decorator(
            fn: Callable[[Any, dict[str, Any]], dict[str, Any] | Awaitable[dict[str, Any]]],
        ) -> Callable[[Any, dict[str, Any]], dict[str, Any] | Awaitable[dict[str, Any]]]:
            if job_name:
                self.job_handlers[job_name] = fn
            else:
                # Backward compatibility: assign to default job_handler
                self.job_handler = fn
            return fn

        return decorator

    def on_cleanup(self) -> Callable[[Callable[[Any], None]], Callable[[Any], None]]:
        def decorator(fn: Callable[[Any], None]) -> Callable[[Any], None]:
            self.cleanup_handler = fn
            return fn

        return decorator

    def on_weights(
        self,
    ) -> Callable[
        [Callable[[list[dict]], Awaitable[dict] | dict]],
        Callable[[list[dict]], Awaitable[dict] | dict],
    ]:
        def decorator(
            fn: Callable[[list[dict]], Awaitable[dict] | dict],
        ) -> Callable[[list[dict]], Awaitable[dict] | dict]:
            self.weights_handler = fn
            return fn

        return decorator

    @property
    def api(self) -> PublicApiRegistry:
        return PublicApiRegistry(self)

    def set_db_version(self, version: int) -> None:
        """Set the database version for this challenge.

        This version determines the schema name: {challenge_name}_v{version}
        If the DB version doesn't change but compose_hash changes, the same schema is reused.
        If the DB version changes, a new schema is created and platform-api provides tools
        to migrate data from the previous version if needed.
        """
        self.db_version = version

    def set_orm_permissions(self, permissions: Any) -> None:
        """Set ORM permissions to send to platform-api.

        Permissions will be automatically sent after orm_ready signal.
        This allows platform-api to enforce security on ORM queries.

        Args:
            permissions: ORMPermissions instance
        """
        self.orm_permissions = permissions


class AdminApiRegistry:
    def __init__(self, registry: ChallengeRegistry) -> None:
        self._registry = registry

    def __call__(
        self, name: str
    ) -> Callable[[Callable[..., Awaitable[Any] | Any]], Callable[..., Awaitable[Any] | Any]]:
        def decorator(
            fn: Callable[..., Awaitable[Any] | Any],
        ) -> Callable[..., Awaitable[Any] | Any]:
            self._registry.admin_handlers[name] = fn
            return fn

        return decorator


class PublicApiRegistry:
    def __init__(self, registry: ChallengeRegistry) -> None:
        self._registry = registry

    def public(
        self, name: str
    ) -> Callable[[Callable[..., Awaitable[Any] | Any]], Callable[..., Awaitable[Any] | Any]]:
        """Register a public API endpoint.

        This endpoint is only available when CHALLENGE_ADMIN=true.
        If CHALLENGE_ADMIN=false, the registration will be rejected.
        """

        def decorator(
            fn: Callable[..., Awaitable[Any] | Any],
        ) -> Callable[..., Awaitable[Any] | Any]:
            import os

            challenge_admin = os.getenv("CHALLENGE_ADMIN", "").lower() == "true"

            if not challenge_admin:
                import warnings

                warnings.warn(
                    f"@challenge.api.public('{name}') is only available when CHALLENGE_ADMIN=true. "
                    f"Registration skipped.",
                    UserWarning,
                    stacklevel=2,
                )
                return fn  # Return function unchanged, but don't register it

            self._registry.public_handlers[name] = fn
            return fn

        return decorator

    def get(self, name: str) -> Callable[..., Awaitable[Any] | Any] | None:
        """Get a registered public API handler by name.

        Args:
            name: Handler name

        Returns:
            Handler function if found, None otherwise
        """
        return self._registry.public_handlers.get(name)

    @property
    def admin(self) -> AdminApiRegistry:
        return AdminApiRegistry(self._registry)


challenge = ChallengeRegistry()
