"""Tests for database migration runner."""

import pytest
import tempfile
import os
from unittest.mock import MagicMock, patch, call
from datetime import datetime
import hashlib

from platform_challenge_sdk.db.migrations import MigrationRunner, Migration


class TestMigration:
    """Tests for Migration class."""

    def test_migration_creation(self):
        """Test creating a migration."""
        migration = Migration(
            version="001",
            description="Create users table",
            sql="CREATE TABLE users (id SERIAL PRIMARY KEY);",
        )

        assert migration.version == "001"
        assert migration.description == "Create users table"
        assert migration.sql == "CREATE TABLE users (id SERIAL PRIMARY KEY);"
        assert migration.checksum is not None

    def test_migration_checksum(self):
        """Test migration checksum calculation."""
        sql = "CREATE TABLE test (id INT);"
        migration = Migration("001", "test", sql)

        # Checksum should be SHA256 of SQL
        expected = hashlib.sha256(sql.encode()).hexdigest()
        assert migration.checksum == expected

    def test_migration_from_file(self):
        """Test loading migration from file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write("-- Migration: Create users table\n")
            f.write("CREATE TABLE users (\n")
            f.write("    id SERIAL PRIMARY KEY,\n")
            f.write("    name VARCHAR(100)\n")
            f.write(");")
            f.flush()

            migration = Migration.from_file(f.name, "001")

        os.unlink(f.name)

        assert migration.version == "001"
        assert "CREATE TABLE users" in migration.sql
        assert migration.checksum is not None


class TestMigrationRunner:
    """Tests for MigrationRunner."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database connection."""
        db = MagicMock()
        db.execute = MagicMock()
        db.fetchone = MagicMock()
        db.fetchall = MagicMock()
        db.begin = MagicMock()
        db.commit = MagicMock()
        db.rollback = MagicMock()
        return db

    def test_runner_initialization(self, mock_db):
        """Test migration runner initialization."""
        runner = MigrationRunner(mock_db)

        assert runner.db == mock_db
        assert runner.migrations == []
        assert runner.applied_migrations == {}

    def test_ensure_migrations_table(self, mock_db):
        """Test ensuring migrations table exists."""
        runner = MigrationRunner(mock_db)
        runner.ensure_migrations_table()

        # Should create table
        mock_db.execute.assert_called()
        call_args = mock_db.execute.call_args[0][0]
        assert "CREATE TABLE IF NOT EXISTS _migrations" in call_args
        assert "version" in call_args
        assert "description" in call_args
        assert "checksum" in call_args
        assert "applied_at" in call_args

    def test_load_applied_migrations(self, mock_db):
        """Test loading already applied migrations."""
        # Mock database response
        mock_db.fetchall.return_value = [
            {
                "version": "001",
                "description": "Create users",
                "checksum": "abc123",
                "applied_at": datetime.now(),
            },
            {
                "version": "002",
                "description": "Add email",
                "checksum": "def456",
                "applied_at": datetime.now(),
            },
        ]

        runner = MigrationRunner(mock_db)
        runner.load_applied_migrations()

        assert len(runner.applied_migrations) == 2
        assert "001" in runner.applied_migrations
        assert "002" in runner.applied_migrations
        assert runner.applied_migrations["001"]["checksum"] == "abc123"

    def test_add_migration(self, mock_db):
        """Test adding migrations to runner."""
        runner = MigrationRunner(mock_db)

        migration1 = Migration("001", "Create users", "CREATE TABLE users;")
        migration2 = Migration("002", "Add email", "ALTER TABLE users ADD email;")

        runner.add_migration(migration1)
        runner.add_migration(migration2)

        assert len(runner.migrations) == 2
        assert runner.migrations[0].version == "001"
        assert runner.migrations[1].version == "002"

    def test_migrations_sorted_by_version(self, mock_db):
        """Test migrations are sorted by version."""
        runner = MigrationRunner(mock_db)

        # Add out of order
        runner.add_migration(Migration("003", "test", "sql"))
        runner.add_migration(Migration("001", "test", "sql"))
        runner.add_migration(Migration("002", "test", "sql"))

        # Should be sorted
        versions = [m.version for m in runner.migrations]
        assert versions == ["001", "002", "003"]

    def test_run_migrations(self, mock_db):
        """Test running migrations."""
        # No migrations applied yet
        mock_db.fetchall.return_value = []

        runner = MigrationRunner(mock_db)
        runner.add_migration(Migration("001", "Create users", "CREATE TABLE users;"))
        runner.add_migration(Migration("002", "Add email", "ALTER TABLE users ADD email;"))

        # Run migrations
        runner.run()

        # Should execute in transaction
        mock_db.begin.assert_called()

        # Should execute each migration
        execute_calls = mock_db.execute.call_args_list
        sql_calls = [
            call[0][0]
            for call in execute_calls
            if "CREATE TABLE users" in call[0][0] or "ALTER TABLE users" in call[0][0]
        ]
        assert len(sql_calls) >= 2

        # Should commit
        mock_db.commit.assert_called()

    def test_skip_applied_migrations(self, mock_db):
        """Test skipping already applied migrations."""
        # Mock that version 001 is already applied
        mock_db.fetchall.return_value = [
            {
                "version": "001",
                "description": "Create users",
                "checksum": Migration("001", "Create users", "CREATE TABLE users;").checksum,
                "applied_at": datetime.now(),
            }
        ]

        runner = MigrationRunner(mock_db)
        runner.add_migration(Migration("001", "Create users", "CREATE TABLE users;"))
        runner.add_migration(Migration("002", "Add email", "ALTER TABLE users ADD email;"))

        # Run migrations
        runner.run()

        # Should only execute migration 002
        sql_executions = [
            call[0][0]
            for call in mock_db.execute.call_args_list
            if "ALTER TABLE users ADD email" in call[0][0]
        ]
        assert len(sql_executions) == 1

        # Should not re-run migration 001
        create_table_calls = [
            call for call in mock_db.execute.call_args_list if "CREATE TABLE users;" in str(call)
        ]
        assert len(create_table_calls) == 0

    def test_checksum_mismatch_error(self, mock_db):
        """Test error on checksum mismatch."""
        # Mock that version 001 is applied with different checksum
        mock_db.fetchall.return_value = [
            {
                "version": "001",
                "description": "Create users",
                "checksum": "wrong_checksum",
                "applied_at": datetime.now(),
            }
        ]

        runner = MigrationRunner(mock_db)
        runner.add_migration(Migration("001", "Create users", "CREATE TABLE users;"))

        # Should raise error
        with pytest.raises(Exception) as exc_info:
            runner.run()

        assert "checksum mismatch" in str(exc_info.value).lower()

    def test_migration_rollback_on_error(self, mock_db):
        """Test rollback on migration error."""
        # No migrations applied
        mock_db.fetchall.return_value = []

        # Make second migration fail
        def execute_side_effect(sql, *args):
            if "ALTER TABLE" in sql:
                raise Exception("Migration failed")
            return MagicMock()

        mock_db.execute.side_effect = execute_side_effect

        runner = MigrationRunner(mock_db)
        runner.add_migration(Migration("001", "Create users", "CREATE TABLE users;"))
        runner.add_migration(Migration("002", "Bad migration", "ALTER TABLE fail;"))

        # Should raise error
        with pytest.raises(Exception):
            runner.run()

        # Should rollback
        mock_db.rollback.assert_called()

    def test_record_migration_application(self, mock_db):
        """Test recording migration application."""
        mock_db.fetchall.return_value = []

        runner = MigrationRunner(mock_db)
        migration = Migration("001", "Create users", "CREATE TABLE users;")
        runner.add_migration(migration)

        runner.run()

        # Should record migration
        insert_calls = [
            call
            for call in mock_db.execute.call_args_list
            if "INSERT INTO _migrations" in str(call)
        ]
        assert len(insert_calls) > 0

        # Should include migration details
        insert_sql = str(insert_calls[0])
        assert "001" in insert_sql
        assert "Create users" in insert_sql
        assert migration.checksum in insert_sql

    def test_dry_run_mode(self, mock_db):
        """Test dry run mode doesn't apply migrations."""
        mock_db.fetchall.return_value = []

        runner = MigrationRunner(mock_db)
        runner.add_migration(Migration("001", "Create users", "CREATE TABLE users;"))

        # Run in dry mode
        runner.run(dry_run=True)

        # Should not execute migrations
        create_calls = [
            call for call in mock_db.execute.call_args_list if "CREATE TABLE users" in str(call)
        ]
        assert len(create_calls) == 0

        # Should not commit
        mock_db.commit.assert_not_called()

    def test_migration_status_report(self, mock_db):
        """Test getting migration status."""
        # One migration applied
        mock_db.fetchall.return_value = [
            {
                "version": "001",
                "description": "Create users",
                "checksum": Migration("001", "Create users", "CREATE TABLE users;").checksum,
                "applied_at": datetime.now(),
            }
        ]

        runner = MigrationRunner(mock_db)
        runner.add_migration(Migration("001", "Create users", "CREATE TABLE users;"))
        runner.add_migration(Migration("002", "Add email", "ALTER TABLE users ADD email;"))
        runner.add_migration(Migration("003", "Add avatar", "ALTER TABLE users ADD avatar;"))

        status = runner.get_status()

        assert status["total"] == 3
        assert status["applied"] == 1
        assert status["pending"] == 2
        assert "001" in status["applied_versions"]
        assert "002" in status["pending_versions"]
        assert "003" in status["pending_versions"]


class TestMigrationDirectoryLoader:
    """Tests for loading migrations from directory."""

    def test_load_from_directory(self, mock_db):
        """Test loading migrations from directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create migration files
            with open(os.path.join(tmpdir, "001_create_users.sql"), "w") as f:
                f.write("CREATE TABLE users (id SERIAL PRIMARY KEY);")

            with open(os.path.join(tmpdir, "002_add_email.sql"), "w") as f:
                f.write("ALTER TABLE users ADD COLUMN email VARCHAR(255);")

            # Also create a non-migration file
            with open(os.path.join(tmpdir, "README.md"), "w") as f:
                f.write("Migration notes")

            runner = MigrationRunner(mock_db)
            runner.load_from_directory(tmpdir)

            # Should load only SQL files
            assert len(runner.migrations) == 2
            assert runner.migrations[0].version == "001"
            assert runner.migrations[1].version == "002"

    def test_version_extraction_from_filename(self, mock_db):
        """Test extracting version from filename."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Different naming patterns
            files = {
                "001_initial.sql": "001",
                "002-add-users.sql": "002",
                "V003__add_email.sql": "003",
                "004.sql": "004",
            }

            for filename, expected_version in files.items():
                with open(os.path.join(tmpdir, filename), "w") as f:
                    f.write("SELECT 1;")

            runner = MigrationRunner(mock_db)
            runner.load_from_directory(tmpdir)

            versions = [m.version for m in runner.migrations]
            assert sorted(versions) == ["001", "002", "003", "004"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
