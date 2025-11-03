# Database Migrations

## Overview

The Challenge SDK supports automatic database migrations that are triggered on startup. Migrations are versioned and applied automatically when Platform API connects with `CHALLENGE_ADMIN=true`.

## Migration Structure

### Naming Convention

Migrations follow this naming pattern:
- **Schema Name**: `{challenge_name}.v{version}` (e.g., `mnist-classifier.v1`)
- **Version Range**: 1-16 (set in `platform.toml`)
- **Location**: `db/migrations/v{version}/`
- **File Format**: Sequential numbering with descriptive names

### Directory Structure

```
db/
└── migrations/
    └── v1/
        ├── 001_create_tables.sql
        ├── 002_add_indexes.sql
        └── 003_add_constraints.py
```

## Setting Database Version

Set the database version in your challenge:

```python
from platform_challenge_sdk import challenge

challenge.set_db_version(1)
```

Or set it in `platform.toml`:

```toml
[database]
version = 1
```

## SQL Migrations

Create SQL migration files in `db/migrations/v{version}/`:

**Example**: `db/migrations/v1/001_create_tables.sql`

```sql
CREATE TABLE IF NOT EXISTS jobs (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(255) UNIQUE NOT NULL,
    score FLOAT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS evaluations (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(255) REFERENCES jobs(job_id),
    metric_name VARCHAR(100) NOT NULL,
    metric_value FLOAT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Migration Execution**:
- Migrations are executed in alphabetical order
- Each migration runs in a transaction
- If a migration fails, the transaction is rolled back
- Schema is automatically created by Platform API

## Python Migrations

Create Python migration files for complex operations:

**Example**: `db/migrations/v1/002_add_indexes.py`

```python
async def migrate(target_db: str, dsn: str):
    """Add indexes to improve query performance."""
    import asyncpg
    
    conn = await asyncpg.connect(dsn)
    try:
        # Create indexes
        await conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_job_id 
            ON {target_db}.jobs(job_id)
        """)
        
        await conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_created_at 
            ON {target_db}.jobs(created_at DESC)
        """)
        
        await conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_evaluation_job_id 
            ON {target_db}.evaluations(job_id)
        """)
    finally:
        await conn.close()
```

**Python Migration Function**:
- Must be named `migrate`
- Receives `target_db` (schema name) and `dsn` (database connection string)
- Must be async
- Should handle errors gracefully

## Advanced Migrations

### Data Migrations

Migrate existing data when schema changes:

```python
async def migrate(target_db: str, dsn: str):
    import asyncpg
    
    conn = await asyncpg.connect(dsn)
    try:
        # Migrate existing data
        await conn.execute(f"""
            UPDATE {target_db}.jobs 
            SET status = 'completed' 
            WHERE status IS NULL
        """)
        
        # Add new column with default
        await conn.execute(f"""
            ALTER TABLE {target_db}.jobs 
            ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'pending'
        """)
    finally:
        await conn.close()
```

### Conditional Migrations

Perform migrations based on current state:

```python
async def migrate(target_db: str, dsn: str):
    import asyncpg
    
    conn = await asyncpg.connect(dsn)
    try:
        # Check if column exists
        columns = await conn.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = $1 AND table_name = 'jobs'
        """, target_db)
        
        column_names = [row['column_name'] for row in columns]
        
        if 'metadata' not in column_names:
            await conn.execute(f"""
                ALTER TABLE {target_db}.jobs 
                ADD COLUMN metadata JSONB
            """)
    finally:
        await conn.close()
```

## ORM Permissions

Set ORM permissions to control database access:

```python
from platform_challenge_sdk import challenge
from platform_challenge_sdk.orm import ORMPermissions

# Define permissions
permissions = ORMPermissions()

# Allow read access to jobs table
permissions.allow_read("jobs", ["id", "job_id", "score"])

# Allow write access (insert only)
permissions.allow_insert("evaluations", ["job_id", "metric_name", "metric_value"])

# Set permissions
challenge.set_orm_permissions(permissions)
```

**Permission Types**:
- `allow_read(table, columns)`: Allow SELECT on specified columns
- `allow_insert(table, columns)`: Allow INSERT into specified columns
- `allow_update(table, columns)`: Allow UPDATE on specified columns
- `allow_delete(table)`: Allow DELETE (requires WHERE clause)

## Migration Lifecycle

1. **Startup**: Challenge SDK starts and waits for Platform API connection
2. **Connection**: Platform API connects with `CHALLENGE_ADMIN=true`
3. **Migration Request**: Platform API requests migrations via WebSocket
4. **Migration Execution**: Platform API applies migrations to database
5. **ORM Ready**: Platform API signals that migrations are complete
6. **Ready Handler**: `@challenge.on_ready()` is called

## Best Practices

1. **Version Control**: Keep migrations in version control
2. **Idempotent**: Make migrations idempotent (use `IF NOT EXISTS`, `IF EXISTS`)
3. **Test First**: Test migrations on a development database first
4. **Backup**: Backup database before applying migrations in production
5. **Rollback Plan**: Have a rollback plan for destructive migrations
6. **Sequential**: Use sequential numbering for migration files
7. **Descriptive Names**: Use descriptive names for migration files

## Troubleshooting

### Migration Not Applied

**Issue**: Migrations are not being applied.

**Solutions**:
- Ensure `CHALLENGE_ADMIN=true` is set
- Check that `db/migrations/v{version}/` directory exists
- Verify migration files are properly formatted
- Check Platform API logs for migration errors

### Migration Fails

**Issue**: Migration fails with error.

**Solutions**:
- Check migration syntax (SQL or Python)
- Verify database permissions
- Ensure schema exists (Platform API creates it)
- Review error logs from Platform API

### Wrong Schema Version

**Issue**: Wrong schema version is being used.

**Solutions**:
- Check `challenge.set_db_version()` is called
- Verify `platform.toml` has correct version
- Ensure version is in range 1-16

## See Also

- [Usage Guide](usage.md) - Using the ORM bridge
- [Architecture](architecture.md) - System architecture
- [API Reference](api-reference.md) - ORM API methods

