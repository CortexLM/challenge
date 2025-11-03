"""SQLAlchemy database manager for challenge SDK."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import MetaData, create_engine, pool
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from ..config import Settings


class SQLAlchemyManager:
    """Manages SQLAlchemy database connections and sessions."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._engine: AsyncEngine | None = None
        self._sessionmaker: sessionmaker | None = None
        self._metadata = MetaData()
        self.Base = declarative_base(metadata=self._metadata)

    async def initialize(self, database_url: str) -> None:
        """Initialize the async engine and session factory."""
        # Convert sync URL to async URL for asyncpg
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
        elif database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+asyncpg://")

        self._engine = create_async_engine(
            database_url,
            echo=False,  # Set to True for SQL debugging
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,  # Verify connections before use
            pool_recycle=3600,  # Recycle connections after 1 hour
        )

        self._sessionmaker = sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

    async def close(self) -> None:
        """Close the database engine."""
        if self._engine:
            await self._engine.dispose()

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get an async database session."""
        if not self._sessionmaker:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        async with self._sessionmaker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def create_all_tables(self) -> None:
        """Create all tables defined by models."""
        if not self._engine:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        async with self._engine.begin() as conn:
            await conn.run_sync(self._metadata.create_all)

    async def drop_all_tables(self) -> None:
        """Drop all tables. Use with caution!"""
        if not self._engine:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        async with self._engine.begin() as conn:
            await conn.run_sync(self._metadata.drop_all)

    def get_sync_engine(self, database_url: str):
        """Get a synchronous engine for Alembic migrations."""
        # Convert async URL back to sync URL
        if database_url.startswith("postgresql+asyncpg://"):
            database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

        return create_engine(
            database_url,
            poolclass=pool.NullPool,  # Don't pool connections for migrations
        )


# Global instance
_db_manager: SQLAlchemyManager | None = None


def get_db_manager() -> SQLAlchemyManager:
    """Get the global database manager instance."""
    if _db_manager is None:
        raise RuntimeError("Database manager not initialized")
    return _db_manager


def set_db_manager(manager: SQLAlchemyManager) -> None:
    """Set the global database manager instance."""
    global _db_manager
    _db_manager = manager


async def init_db(settings: Settings, database_url: str) -> SQLAlchemyManager:
    """Initialize the database manager."""
    manager = SQLAlchemyManager(settings)
    await manager.initialize(database_url)
    set_db_manager(manager)
    return manager
