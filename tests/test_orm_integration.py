"""Tests for ORM integration and database operations."""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from platform_challenge_sdk.orm.client import ORMClient
from platform_challenge_sdk.orm.permissions import PermissionManager
from platform_challenge_sdk.orm.server_adapter import ORMServerAdapter


Base = declarative_base()


# Test models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Score(Base):
    __tablename__ = "scores"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    value = Column(Float)
    metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class TestORMClient:
    """Tests for ORM client operations."""

    @pytest.fixture
    def orm_client(self):
        """Create ORM client with mocked HTTP."""
        client = ORMClient(base_url="http://localhost:8000", session_token="test-token")
        client._session = MagicMock()
        return client

    @pytest.mark.asyncio
    async def test_query_basic(self, orm_client):
        """Test basic query operation."""
        # Mock response
        orm_client._session.post.return_value.status_code = 200
        orm_client._session.post.return_value.json.return_value = {
            "success": True,
            "data": [
                {"id": 1, "name": "Alice", "email": "alice@example.com"},
                {"id": 2, "name": "Bob", "email": "bob@example.com"},
            ],
            "count": 2,
        }

        # Execute query
        result = await orm_client.query("users").filter("name", "!=", "Charlie").all()

        # Verify request
        orm_client._session.post.assert_called_once()
        call_args = orm_client._session.post.call_args

        assert "/orm/query" in call_args[0][0]
        payload = call_args[1]["json"]
        assert payload["model"] == "users"
        assert payload["filters"] == [{"field": "name", "op": "!=", "value": "Charlie"}]

        # Verify result
        assert len(result["data"]) == 2
        assert result["data"][0]["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_query_with_multiple_filters(self, orm_client):
        """Test query with multiple filters."""
        orm_client._session.post.return_value.status_code = 200
        orm_client._session.post.return_value.json.return_value = {"success": True, "data": []}

        await orm_client.query("scores").filter("user_id", "=", 1).filter("value", ">", 0.5).filter(
            "created_at", ">=", "2024-01-01"
        ).all()

        payload = orm_client._session.post.call_args[1]["json"]
        assert len(payload["filters"]) == 3
        assert payload["filters"][0] == {"field": "user_id", "op": "=", "value": 1}
        assert payload["filters"][1] == {"field": "value", "op": ">", "value": 0.5}
        assert payload["filters"][2] == {"field": "created_at", "op": ">=", "value": "2024-01-01"}

    @pytest.mark.asyncio
    async def test_query_ordering(self, orm_client):
        """Test query with ordering."""
        orm_client._session.post.return_value.status_code = 200
        orm_client._session.post.return_value.json.return_value = {"success": True, "data": []}

        await orm_client.query("scores").order_by("value", desc=True).order_by("created_at").all()

        payload = orm_client._session.post.call_args[1]["json"]
        assert len(payload["order_by"]) == 2
        assert payload["order_by"][0] == {"field": "value", "desc": True}
        assert payload["order_by"][1] == {"field": "created_at", "desc": False}

    @pytest.mark.asyncio
    async def test_query_pagination(self, orm_client):
        """Test query with limit and offset."""
        orm_client._session.post.return_value.status_code = 200
        orm_client._session.post.return_value.json.return_value = {"success": True, "data": []}

        await orm_client.query("users").limit(10).offset(20).all()

        payload = orm_client._session.post.call_args[1]["json"]
        assert payload["limit"] == 10
        assert payload["offset"] == 20

    @pytest.mark.asyncio
    async def test_insert_single(self, orm_client):
        """Test inserting single record."""
        orm_client._session.post.return_value.status_code = 200
        orm_client._session.post.return_value.json.return_value = {
            "success": True,
            "id": 123,
            "data": {"id": 123, "name": "Charlie", "email": "charlie@example.com"},
        }

        result = await orm_client.insert(
            "users", {"name": "Charlie", "email": "charlie@example.com"}
        )

        # Verify request
        call_args = orm_client._session.post.call_args
        assert "/orm/insert" in call_args[0][0]
        payload = call_args[1]["json"]
        assert payload["model"] == "users"
        assert payload["data"]["name"] == "Charlie"

        # Verify result
        assert result["id"] == 123
        assert result["data"]["name"] == "Charlie"

    @pytest.mark.asyncio
    async def test_insert_many(self, orm_client):
        """Test bulk insert."""
        orm_client._session.post.return_value.status_code = 200
        orm_client._session.post.return_value.json.return_value = {
            "success": True,
            "count": 3,
            "ids": [201, 202, 203],
        }

        users = [
            {"name": "User1", "email": "user1@example.com"},
            {"name": "User2", "email": "user2@example.com"},
            {"name": "User3", "email": "user3@example.com"},
        ]

        result = await orm_client.insert_many("users", users)

        payload = orm_client._session.post.call_args[1]["json"]
        assert payload["model"] == "users"
        assert len(payload["data"]) == 3
        assert result["count"] == 3
        assert len(result["ids"]) == 3

    @pytest.mark.asyncio
    async def test_update_records(self, orm_client):
        """Test updating records."""
        orm_client._session.post.return_value.status_code = 200
        orm_client._session.post.return_value.json.return_value = {"success": True, "count": 5}

        result = (
            await orm_client.update("users")
            .filter("created_at", "<", "2024-01-01")
            .set({"status": "inactive"})
            .execute()
        )

        # Verify request
        call_args = orm_client._session.post.call_args
        assert "/orm/update" in call_args[0][0]
        payload = call_args[1]["json"]
        assert payload["model"] == "users"
        assert payload["filters"][0]["field"] == "created_at"
        assert payload["values"] == {"status": "inactive"}

        assert result["count"] == 5

    @pytest.mark.asyncio
    async def test_delete_records(self, orm_client):
        """Test deleting records."""
        orm_client._session.post.return_value.status_code = 200
        orm_client._session.post.return_value.json.return_value = {"success": True, "count": 3}

        result = await orm_client.delete("scores").filter("value", "<", 0.1).execute()

        # Verify request
        call_args = orm_client._session.post.call_args
        assert "/orm/delete" in call_args[0][0]
        payload = call_args[1]["json"]
        assert payload["model"] == "scores"
        assert payload["filters"][0]["value"] == 0.1

        assert result["count"] == 3

    @pytest.mark.asyncio
    async def test_raw_query(self, orm_client):
        """Test executing raw SQL query."""
        orm_client._session.post.return_value.status_code = 200
        orm_client._session.post.return_value.json.return_value = {
            "success": True,
            "data": [{"total": 42, "avg_score": 0.75}],
        }

        result = await orm_client.raw(
            "SELECT COUNT(*) as total, AVG(value) as avg_score FROM scores WHERE user_id = ?", [1]
        )

        # Verify request
        payload = orm_client._session.post.call_args[1]["json"]
        assert (
            payload["query"]
            == "SELECT COUNT(*) as total, AVG(value) as avg_score FROM scores WHERE user_id = ?"
        )
        assert payload["params"] == [1]

        assert result["data"][0]["total"] == 42

    @pytest.mark.asyncio
    async def test_transaction(self, orm_client):
        """Test transaction operations."""
        orm_client._session.post.return_value.status_code = 200
        orm_client._session.post.return_value.json.return_value = {"success": True}

        async with orm_client.transaction() as tx:
            # Operations within transaction
            await tx.insert("users", {"name": "Test"})
            await tx.update("scores").filter("user_id", "=", 1).set({"value": 0.9})

        # Verify begin/commit calls
        calls = orm_client._session.post.call_args_list
        assert any("/orm/transaction/begin" in str(call) for call in calls)
        assert any("/orm/transaction/commit" in str(call) for call in calls)

    @pytest.mark.asyncio
    async def test_error_handling(self, orm_client):
        """Test error handling."""
        orm_client._session.post.return_value.status_code = 400
        orm_client._session.post.return_value.json.return_value = {
            "success": False,
            "error": "Duplicate key violation",
        }

        with pytest.raises(Exception) as exc_info:
            await orm_client.insert("users", {"email": "duplicate@example.com"})

        assert "Duplicate key violation" in str(exc_info.value)


class TestPermissionManager:
    """Tests for ORM permission management."""

    def test_permission_checking(self):
        """Test permission checking logic."""
        permissions = PermissionManager()

        # Set permissions
        permissions.set_permissions(
            {
                "users": ["read", "insert"],
                "scores": ["read", "insert", "update", "delete"],
                "admin_logs": [],  # No permissions
            }
        )

        # Check permissions
        assert permissions.can_read("users")
        assert permissions.can_insert("users")
        assert not permissions.can_update("users")
        assert not permissions.can_delete("users")

        assert permissions.can_read("scores")
        assert permissions.can_insert("scores")
        assert permissions.can_update("scores")
        assert permissions.can_delete("scores")

        assert not permissions.can_read("admin_logs")

    def test_validate_query(self):
        """Test query validation against permissions."""
        permissions = PermissionManager()
        permissions.set_permissions({"users": ["read"], "scores": ["read", "insert"]})

        # Valid queries
        assert permissions.validate_query("users", "read")
        assert permissions.validate_query("scores", "read")
        assert permissions.validate_query("scores", "insert")

        # Invalid queries
        assert not permissions.validate_query("users", "insert")
        assert not permissions.validate_query("users", "delete")
        assert not permissions.validate_query("unknown_table", "read")

    def test_wildcard_permissions(self):
        """Test wildcard permissions."""
        permissions = PermissionManager()
        permissions.set_permissions(
            {
                "*": ["read"],  # Read all tables
                "scores": ["read", "insert", "update", "delete"],  # Full access to scores
            }
        )

        # Wildcard read permission
        assert permissions.can_read("users")
        assert permissions.can_read("products")
        assert permissions.can_read("anything")

        # But not other operations
        assert not permissions.can_insert("users")
        assert not permissions.can_update("products")

        # Specific table overrides
        assert permissions.can_insert("scores")
        assert permissions.can_update("scores")
        assert permissions.can_delete("scores")


class TestORMServerAdapter:
    """Tests for ORM server adapter."""

    @pytest.fixture
    def adapter(self):
        """Create adapter with test database."""
        # In-memory SQLite for testing
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)

        adapter = ORMServerAdapter(Session)
        return adapter, Session

    @pytest.mark.asyncio
    async def test_execute_query(self, adapter):
        """Test executing query through adapter."""
        adapter, Session = adapter

        # Insert test data
        session = Session()
        session.add(User(name="Alice", email="alice@example.com"))
        session.add(User(name="Bob", email="bob@example.com"))
        session.commit()
        session.close()

        # Execute query
        request = {
            "model": "users",
            "filters": [],
            "order_by": [{"field": "name", "desc": False}],
            "limit": 10,
            "offset": 0,
        }

        result = await adapter.execute_query(request)

        assert result["success"]
        assert len(result["data"]) == 2
        assert result["data"][0]["name"] == "Alice"
        assert result["data"][1]["name"] == "Bob"

    @pytest.mark.asyncio
    async def test_execute_insert(self, adapter):
        """Test executing insert through adapter."""
        adapter, Session = adapter

        request = {"model": "users", "data": {"name": "Charlie", "email": "charlie@example.com"}}

        result = await adapter.execute_insert(request)

        assert result["success"]
        assert result["id"] is not None

        # Verify in database
        session = Session()
        user = session.query(User).filter_by(email="charlie@example.com").first()
        assert user is not None
        assert user.name == "Charlie"
        session.close()

    @pytest.mark.asyncio
    async def test_execute_update(self, adapter):
        """Test executing update through adapter."""
        adapter, Session = adapter

        # Insert test data
        session = Session()
        user = User(name="Dave", email="dave@example.com")
        session.add(user)
        session.commit()
        user_id = user.id
        session.close()

        # Update
        request = {
            "model": "users",
            "filters": [{"field": "id", "op": "=", "value": user_id}],
            "values": {"name": "David"},
        }

        result = await adapter.execute_update(request)

        assert result["success"]
        assert result["count"] == 1

        # Verify update
        session = Session()
        user = session.query(User).get(user_id)
        assert user.name == "David"
        session.close()

    @pytest.mark.asyncio
    async def test_execute_delete(self, adapter):
        """Test executing delete through adapter."""
        adapter, Session = adapter

        # Insert test data
        session = Session()
        session.add(User(name="Eve", email="eve@example.com"))
        session.commit()
        session.close()

        # Delete
        request = {
            "model": "users",
            "filters": [{"field": "email", "op": "=", "value": "eve@example.com"}],
        }

        result = await adapter.execute_delete(request)

        assert result["success"]
        assert result["count"] == 1

        # Verify deletion
        session = Session()
        user = session.query(User).filter_by(email="eve@example.com").first()
        assert user is None
        session.close()

    @pytest.mark.asyncio
    async def test_raw_sql_execution(self, adapter):
        """Test raw SQL execution."""
        adapter, Session = adapter

        # Insert test data
        session = Session()
        session.add(User(name="Frank", email="frank@example.com"))
        session.commit()
        session.close()

        # Execute raw SQL
        request = {
            "query": "SELECT COUNT(*) as count FROM users WHERE name LIKE ?",
            "params": ["F%"],
        }

        result = await adapter.execute_raw(request)

        assert result["success"]
        assert result["data"][0]["count"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
