from __future__ import annotations

import asyncio
import os


class MigrationError(Exception):
    pass


async def run_startup_migrations(challenge_name: str, version: str, dsn_encrypted: str) -> None:
    """Run automatic database migrations on startup."""
    dsn = os.getenv("SDK_DB_DSN")
    if not dsn:
        raise MigrationError("Missing decrypted DB DSN")

    if version.isdigit():
        major = int(version)
    else:
        raise MigrationError("Invalid database version")
    if major < 1 or major > 16:
        raise MigrationError("Database version out of range (1..16)")

    target_db = f"{challenge_name}.v{major}"
    migrations_dir = f"db/migrations/v{major}"
    if not os.path.exists(migrations_dir):
        return

    migration_files = sorted([f for f in os.listdir(migrations_dir) if f.endswith((".sql", ".py"))])

    for migration_file in migration_files:
        migration_path = os.path.join(migrations_dir, migration_file)
        if migration_file.endswith(".sql"):
            await _apply_sql_migration(target_db, dsn, migration_path)
        elif migration_file.endswith(".py"):
            await _apply_python_migration(target_db, dsn, migration_path)

    await asyncio.sleep(0)
    return


async def _apply_sql_migration(target_db: str, dsn: str, migration_path: str) -> None:
    """Apply SQL migration file to database."""
    try:
        import asyncpg

        with open(migration_path) as f:
            sql = f.read()
        conn = await asyncpg.connect(dsn)
        try:
            await conn.execute(sql)
        finally:
            await conn.close()
    except ImportError:
        import psycopg2

        with open(migration_path) as f:
            sql = f.read()
        conn = psycopg2.connect(dsn)
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
        finally:
            conn.close()


async def _apply_python_migration(target_db: str, dsn: str, migration_path: str) -> None:
    """Apply Python migration module to database."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("migration", migration_path)
    if spec is None or spec.loader is None:
        raise MigrationError(f"Could not load migration: {migration_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if hasattr(module, "migrate"):
        migrate_func = module.migrate
        if asyncio.iscoroutinefunction(migrate_func):
            await migrate_func(target_db, dsn)
        else:
            migrate_func(target_db, dsn)
