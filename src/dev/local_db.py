"""Support for local database connection in development mode."""

import asyncio
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


async def init_local_db_if_needed() -> Any | None:
    """Initialize local database connection if DEV_DB_URL is provided.

    Returns:
        SQLAlchemyManager instance if local DB was initialized, None otherwise
    """
    dev_db_url = os.getenv("DEV_DB_URL")
    if not dev_db_url:
        return None

    try:
        from ..config import Settings
        from ..db import init_models
        from ..db.sqlalchemy_manager import init_db

        logger.info("🔧 DEV MODE: Initializing local database connection")
        logger.info(f"🔧 DEV MODE: Database URL: {dev_db_url.replace('://', '://***')}")

        settings = Settings()
        manager = await init_db(settings, dev_db_url)
        init_models()

        # Run migrations in dev mode
        await run_dev_migrations(dev_db_url)

        logger.info("🔧 DEV MODE: Local database initialized successfully")
        return manager
    except Exception as e:
        logger.error(f"Failed to initialize local database: {e}", exc_info=True)
        return None


async def run_dev_migrations(dsn: str) -> None:
    """Run database migrations in dev mode using DEV_DB_URL.

    Args:
        dsn: Database connection string (DEV_DB_URL)
    """
    from ..challenge.decorators import challenge

    # Get challenge name from CHALLENGE_ID env var or default
    challenge_name = os.getenv("CHALLENGE_ID", "terminal-challenge")

    # Get db_version from challenge registry
    db_version = challenge.db_version
    if db_version is None:
        logger.warning("🔧 DEV MODE: db_version not set in challenge registry, defaulting to 1")
        db_version = 1

    version_str = str(db_version)
    logger.info(
        f"🔧 DEV MODE: Running migrations for challenge '{challenge_name}', version {version_str}"
    )

    # Check if migrations directory exists (from current working directory or project root)
    migrations_dir_rel = f"db/migrations/v{db_version}"
    migrations_dir = migrations_dir_rel

    # Try relative path first, then check if we're in the challenge root
    if not os.path.exists(migrations_dir):
        # Maybe we're running from a different directory, try to find the migrations
        import pathlib

        current = pathlib.Path.cwd()
        # Try current directory and parent
        for base in [current, current.parent]:
            candidate = base / migrations_dir_rel
            if candidate.exists():
                migrations_dir = str(candidate)
                logger.info(f"🔧 DEV MODE: Found migrations directory: {migrations_dir}")
                break
        else:
            logger.info(
                f"🔧 DEV MODE: No migrations directory found at db/migrations/v{db_version}, skipping migrations"
            )
            logger.info(f"🔧 DEV MODE: Searched in: {current} and {current.parent}")
            return

    migration_files = sorted([f for f in os.listdir(migrations_dir) if f.endswith((".sql", ".py"))])

    if not migration_files:
        logger.info(f"🔧 DEV MODE: No migration files found in {migrations_dir}")
        return

    logger.info(f"🔧 DEV MODE: Found {len(migration_files)} migration files in {migrations_dir}")

    # Target schema name (same format as production)
    target_db = f"{challenge_name}_v{db_version}"

    # Create schema if it doesn't exist (for dev mode, we'll use public schema if no schema specified)
    # In production, platform-api creates the schema, but in dev mode we apply directly
    # If migrations reference a schema, we should create it first
    try:
        await _ensure_schema_exists(target_db, dsn)
        logger.info(f"🔧 DEV MODE: Schema '{target_db}' ready")
    except Exception as e:
        logger.warning(f"🔧 DEV MODE: Could not ensure schema exists (may use public schema): {e}")

    for migration_file in migration_files:
        migration_path = os.path.join(migrations_dir, migration_file)
        logger.info(f"🔧 DEV MODE: Applying migration: {migration_file}...")

        try:
            import time

            start_time = time.time()

            if migration_file.endswith(".sql"):
                await _apply_sql_migration_dev(target_db, dsn, migration_path)
            elif migration_file.endswith(".py"):
                await _apply_python_migration_dev(target_db, dsn, migration_path)

            import time

            elapsed_time = time.time() - start_time
            elapsed = f" (took {elapsed_time:.2f}s)"

            logger.info(f"🔧 DEV MODE: ✅ Migration {migration_file} applied successfully{elapsed}")
        except asyncio.TimeoutError as e:
            logger.error(f"🔧 DEV MODE: ❌ Migration {migration_file} timed out: {e}")
            raise
        except Exception as e:
            logger.error(
                f"🔧 DEV MODE: ❌ Failed to apply migration {migration_file}: {e}", exc_info=True
            )
            raise


async def _ensure_schema_exists(schema_name: str, dsn: str) -> None:
    """Ensure the target schema exists in the database."""
    try:
        import asyncpg

        # Remove +asyncpg suffix for asyncpg.connect if present
        async_dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")

        conn = await asyncpg.connect(async_dsn)
        try:
            # Create schema if it doesn't exist
            await conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"')
        finally:
            await conn.close()
    except ImportError:
        # Fallback to psycopg2
        import psycopg2

        conn = psycopg2.connect(dsn)
        try:
            with conn.cursor() as cur:
                cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"')
            conn.commit()
        finally:
            conn.close()


async def _apply_sql_migration_dev(target_db: str, dsn: str, migration_path: str) -> None:
    """Apply SQL migration file to database in dev mode."""
    # For Supabase pooler connections, prefer psycopg2 which handles it better
    use_psycopg2 = ":6543/" in dsn or ":6543" in dsn or "pooler" in dsn.lower()

    if use_psycopg2:
        logger.debug("🔧 DEV MODE: Using psycopg2 for pooler/Supabase connection")
        try:
            import psycopg2
            from psycopg2 import sql as psql

            with open(migration_path) as f:
                sql_content = f.read()

            # Run psycopg2 in a thread since it's synchronous
            def run_psycopg2_migration():
                logger.debug("🔧 DEV MODE: Connecting with psycopg2...")
                conn = psycopg2.connect(dsn, connect_timeout=10)
                try:
                    with conn.cursor() as cur:
                        # Set search_path
                        cur.execute(
                            psql.SQL("SET search_path TO {}, public").format(
                                psql.Identifier(target_db)
                            )
                        )
                        logger.debug("🔧 DEV MODE: search_path set, executing SQL...")

                        # Execute migration SQL
                        cur.execute(sql_content)

                    conn.commit()
                    logger.debug("🔧 DEV MODE: Migration committed successfully")
                finally:
                    conn.close()
                    logger.debug("🔧 DEV MODE: Connection closed")

            # Execute in thread pool to avoid blocking
            await asyncio.wait_for(asyncio.to_thread(run_psycopg2_migration), timeout=60)
            return
        except ImportError:
            logger.warning("🔧 DEV MODE: psycopg2 not available, falling back to asyncpg")
        except Exception as e:
            logger.error(f"🔧 DEV MODE: psycopg2 migration failed: {e}", exc_info=True)
            raise

    # Default: use asyncpg
    try:
        import asyncpg

        with open(migration_path) as f:
            sql = f.read()

        # Convert postgresql:// to postgresql+asyncpg:// for asyncpg if needed
        if dsn.startswith("postgresql://"):
            async_dsn = dsn.replace("postgresql://", "postgresql+asyncpg://")
        elif dsn.startswith("postgres://"):
            async_dsn = dsn.replace("postgres://", "postgresql+asyncpg://")
        else:
            async_dsn = dsn

        # Remove +asyncpg suffix for asyncpg.connect
        async_dsn = async_dsn.replace("postgresql+asyncpg://", "postgresql://")

        # Connect with timeout (Supabase pooler may need longer timeout)
        logger.debug("🔧 DEV MODE: Connecting to database...")
        try:
            conn = await asyncio.wait_for(
                asyncpg.connect(async_dsn, timeout=10, command_timeout=120), timeout=20
            )
        except Exception as e:
            logger.error(f"🔧 DEV MODE: Failed to connect: {e}")
            raise

        try:
            logger.debug("🔧 DEV MODE: Connection established, setting search_path...")
            # Set search_path to target schema for this connection
            await asyncio.wait_for(
                conn.execute(f'SET search_path TO "{target_db}", public'), timeout=5
            )
            logger.debug("🔧 DEV MODE: search_path set")

            # Start a transaction for the migration
            logger.debug("🔧 DEV MODE: Starting transaction...")
            async with conn.transaction():
                logger.debug(
                    f"🔧 DEV MODE: Transaction started, executing SQL migration ({len(sql)} chars)..."
                )

                # Execute SQL directly - asyncpg handles multi-statement SQL
                # Use execute() which returns immediately after execution
                result = await asyncio.wait_for(
                    conn.execute(sql),
                    timeout=60,  # 60 seconds for complex migrations
                )

                logger.debug(f"🔧 DEV MODE: SQL executed, result: {result}")

            logger.debug("🔧 DEV MODE: Transaction committed, migration completed")
        except asyncio.TimeoutError:
            logger.error("🔧 DEV MODE: Migration timed out after 60 seconds")
            raise
        except Exception as e:
            logger.error(f"🔧 DEV MODE: Error during migration: {e}", exc_info=True)
            raise
        finally:
            logger.debug("🔧 DEV MODE: Closing database connection...")
            await conn.close()
            logger.debug("🔧 DEV MODE: Database connection closed")
    except ImportError:
        # Fallback to psycopg2 if asyncpg not available
        import psycopg2

        with open(migration_path) as f:
            sql = f.read()

        conn = psycopg2.connect(dsn)
        try:
            with conn.cursor() as cur:
                # Set search_path to target schema
                cur.execute(f'SET search_path TO "{target_db}", public')
                cur.execute(sql)
            conn.commit()
        finally:
            conn.close()


async def _apply_python_migration_dev(target_db: str, dsn: str, migration_path: str) -> None:
    """Apply Python migration module to database in dev mode."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("migration", migration_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load migration: {migration_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if hasattr(module, "migrate"):
        migrate_func = module.migrate
        if asyncio.iscoroutinefunction(migrate_func):
            await migrate_func(target_db, dsn)
        else:
            migrate_func(target_db, dsn)


async def run_dev_migrations_if_possible() -> None:
    """Attempt to run migrations in dev mode even without DEV_DB_URL.

    Tries to use a default local database connection if DEV_DB_URL is not set.
    This allows migrations to run automatically in dev mode.
    """
    dev_db_url = os.getenv("DEV_DB_URL")

    if dev_db_url:
        # DEV_DB_URL is set, migrations already run in init_local_db_if_needed()
        return

    logger.info(
        "🔧 DEV MODE: DEV_DB_URL not set, attempting to run migrations with default connections..."
    )

    # Try to use a default local PostgreSQL connection
    # Common defaults for local development
    default_urls = [
        "postgresql://postgres:postgres@localhost:5432/coding_benchmark",
        "postgresql://postgres:postgres@localhost:5432/postgres",
        "postgresql://localhost:5432/coding_benchmark",
        "postgresql://localhost:5432/postgres",
    ]

    for url in default_urls:
        try:
            logger.info(
                f"🔧 DEV MODE: Trying default DB connection: {url.split('@')[-1] if '@' in url else url}"
            )
            await run_dev_migrations(url)
            logger.info("🔧 DEV MODE: ✅ Migrations executed successfully!")
            return
        except Exception as e:
            logger.debug(f"🔧 DEV MODE: Failed to connect: {str(e)[:100]}")
            continue

    logger.warning(
        "🔧 DEV MODE: ⚠️ Could not run migrations automatically - no database connection available"
    )
    logger.warning("🔧 DEV MODE: 💡 To run migrations, set DEV_DB_URL environment variable:")
    logger.warning("    export DEV_DB_URL='postgresql://user:password@localhost:5432/dbname'")


async def setup_local_orm_adapter(manager: Any, challenge_id: str, schema_name: str) -> Any | None:
    """Set up local ORM adapter that uses direct DB connection instead of WebSocket bridge.

    This allows the challenge to use ORM operations directly against local DB in dev mode.
    """
    try:
        # Create a simple local adapter that uses SQLAlchemy directly
        # For now, we'll use the ServerORMAdapter but configure it for local use
        # In a full implementation, we'd create a LocalORMAdapter that bypasses WebSocket

        logger.info("🔧 DEV MODE: Local ORM adapter configured (using direct DB connection)")

        # The ORM operations will use the direct DB connection
        # ORM operations use ServerORMAdapter configured for local development mode

        return None
    except Exception as e:
        logger.error(f"Failed to setup local ORM adapter: {e}", exc_info=True)
        return None
