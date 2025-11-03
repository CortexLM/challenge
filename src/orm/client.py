"""ORM Client for secure queries via WebSocket (read and write)."""

from dataclasses import dataclass, field
from typing import Any

from ..websocket import SecureWebSocketClient
from .permissions import ORMPermissions


@dataclass
class QueryFilter:
    """Filter condition for ORM queries."""

    column: str
    operator: str
    value: Any

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "column": self.column,
            "operator": self.operator,
            "value": self.value,
        }


@dataclass
class OrderBy:
    """Order by clause for ORM queries."""

    column: str
    direction: str = "ASC"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "column": self.column,
            "direction": self.direction,
        }


@dataclass
class Aggregation:
    """Aggregation function for ORM queries."""

    function: str  # COUNT, SUM, AVG, MIN, MAX
    column: str
    alias: str

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "function": self.function,
            "column": self.column,
            "alias": self.alias,
        }


@dataclass
class ColumnValue:
    """Column-value pair for INSERT/UPDATE operations."""

    column: str
    value: Any

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "column": self.column,
            "value": self.value,
        }


@dataclass
class ORMQuery:
    """ORM query structure."""

    operation: str  # "select", "count", "insert", "update", "delete"
    table: str
    schema: str | None = None
    columns: list[str] | None = None
    filters: list[QueryFilter] = field(default_factory=list)
    order_by: list[OrderBy] = field(default_factory=list)
    limit: int | None = None
    offset: int | None = None
    aggregations: list[Aggregation] = field(default_factory=list)
    # For INSERT/UPDATE operations
    values: list[ColumnValue] | None = None  # For INSERT: column -> value mapping
    set_values: list[ColumnValue] | None = None  # For UPDATE: column -> value mapping

    def add_filter(self, column: str, operator: str, value: Any) -> "ORMQuery":
        """Add a filter to the query."""
        self.filters.append(QueryFilter(column, operator, value))
        return self

    def add_order(self, column: str, direction: str = "ASC") -> "ORMQuery":
        """Add order by clause."""
        self.order_by.append(OrderBy(column, direction))
        return self

    def add_aggregation(self, function: str, column: str, alias: str) -> "ORMQuery":
        """Add aggregation function."""
        self.aggregations.append(Aggregation(function, column, alias))
        return self

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        data = {
            "operation": self.operation,
            "table": self.table,
        }

        if self.schema:
            data["schema"] = self.schema
        if self.columns:
            data["columns"] = self.columns
        if self.filters:
            data["filters"] = [f.to_dict() for f in self.filters]
        if self.order_by:
            data["order_by"] = [o.to_dict() for o in self.order_by]
        if self.limit is not None:
            data["limit"] = self.limit
        if self.offset is not None:
            data["offset"] = self.offset
        if self.aggregations:
            data["aggregations"] = [a.to_dict() for a in self.aggregations]
        if self.values:
            data["values"] = [v.to_dict() for v in self.values]
        if self.set_values:
            data["set_values"] = [v.to_dict() for v in self.set_values]

        return data


@dataclass
class QueryResult:
    """Result of an ORM query."""

    rows: list[dict[str, Any]]
    row_count: int
    execution_time_ms: int

    @classmethod
    def from_dict(cls, data: dict) -> "QueryResult":
        """Create from dictionary."""
        return cls(
            rows=data.get("rows", []),
            row_count=data.get("row_count", 0),
            execution_time_ms=data.get("execution_time_ms", 0),
        )


class SecureORMClient:
    """Client for executing secure ORM queries via WebSocket (read and write)."""

    def __init__(
        self, ws_client: SecureWebSocketClient, permissions: ORMPermissions, challenge_id: str
    ):
        self.ws_client = ws_client
        self.permissions = permissions
        self.challenge_id = challenge_id
        self.schema = f"challenge_{challenge_id.replace('-', '_')}"

    async def execute_query(self, query: ORMQuery) -> QueryResult:
        """Execute a query (read or write).

        The query is automatically encrypted and sent via secure WebSocket.
        All values are binded server-side - no SQL injection possible.
        """
        # Set schema if not provided
        if not query.schema:
            query.schema = self.schema

        # Send ORM query message (query_id will be added automatically by SecureWebSocketClient)
        response = await self.ws_client.send_message({
            "type": "orm_query",
            "query": query.to_dict(),
        })

        if response.get("type") == "orm_result":
            return QueryResult.from_dict(response.get("result", {}))
        elif response.get("type") == "error":
            error_msg = response.get("message", "Unknown error")
            raise Exception(f"ORM query error: {error_msg}")
        else:
            raise Exception(f"Unexpected response type: {response.get('type')}")

    async def select(
        self,
        table: str,
        columns: list[str] | None = None,
        filters: list[QueryFilter] | None = None,
        order_by: list[OrderBy] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> QueryResult:
        """Execute a SELECT query."""
        query = ORMQuery(
            operation="select",
            table=table,
            columns=columns,
            filters=filters or [],
            order_by=order_by or [],
            limit=limit,
            offset=offset,
        )
        return await self.execute_query(query)

    async def count(self, table: str, filters: list[QueryFilter] | None = None) -> int:
        """Execute a COUNT query."""
        query = ORMQuery(
            operation="count",
            table=table,
            filters=filters or [],
        )
        result = await self.execute_query(query)
        if result.rows and "count" in result.rows[0]:
            return result.rows[0]["count"]
        return 0

    async def aggregate(
        self,
        table: str,
        aggregations: list[Aggregation],
        filters: list[QueryFilter] | None = None,
        group_by: list[str] | None = None,
    ) -> QueryResult:
        """Execute an aggregation query."""
        query = ORMQuery(
            operation="select",
            table=table,
            columns=group_by,
            filters=filters or [],
            aggregations=aggregations,
        )
        return await self.execute_query(query)

    async def insert(
        self,
        table: str,
        values: dict[str, Any],
    ) -> QueryResult:
        """Execute an INSERT query.

        Args:
            table: Table name
            values: Dictionary of column -> value mappings

        Returns:
            QueryResult with inserted row(s)
        """
        column_values = [ColumnValue(column=col, value=val) for col, val in values.items()]
        query = ORMQuery(
            operation="insert",
            table=table,
            values=column_values,
        )
        return await self.execute_query(query)

    async def update(
        self,
        table: str,
        set_values: dict[str, Any],
        filters: list[QueryFilter] | None = None,
    ) -> QueryResult:
        """Execute an UPDATE query.

        Args:
            table: Table name
            set_values: Dictionary of column -> value mappings to update
            filters: WHERE clause filters (required)

        Returns:
            QueryResult with updated row(s)
        """
        if not filters:
            raise ValueError("UPDATE requires filters (WHERE clause)")

        column_values = [ColumnValue(column=col, value=val) for col, val in set_values.items()]
        query = ORMQuery(
            operation="update",
            table=table,
            set_values=column_values,
            filters=filters or [],
        )
        return await self.execute_query(query)

    async def delete(
        self,
        table: str,
        filters: list[QueryFilter],
    ) -> QueryResult:
        """Execute a DELETE query.

        Args:
            table: Table name
            filters: WHERE clause filters (required)

        Returns:
            QueryResult with deleted row(s)
        """
        if not filters:
            raise ValueError("DELETE requires filters (WHERE clause)")

        query = ORMQuery(
            operation="delete",
            table=table,
            filters=filters,
        )
        return await self.execute_query(query)

    def get_readable_tables(self) -> list[str]:
        """Get list of readable tables."""
        return self.permissions.get_readable_tables()

    def get_readable_columns(self, table: str) -> list[str]:
        """Get list of readable columns for a table."""
        return self.permissions.get_readable_columns(table)


class QueryBuilder:
    """Fluent interface for building ORM queries."""

    def __init__(self, client: SecureORMClient):
        self.client = client
        self._query = ORMQuery(operation="select", table="")

    def select(self, *columns: str) -> "QueryBuilder":
        """Select specific columns."""
        self._query.columns = list(columns) if columns else None
        return self

    def from_table(self, table: str) -> "QueryBuilder":
        """Set the table to query from."""
        self._query.table = table
        return self

    def where(self, column: str, operator: str, value: Any) -> "QueryBuilder":
        """Add a WHERE condition."""
        self._query.add_filter(column, operator, value)
        return self

    def order_by(self, column: str, direction: str = "ASC") -> "QueryBuilder":
        """Add ORDER BY clause."""
        self._query.add_order(column, direction)
        return self

    def limit(self, limit: int) -> "QueryBuilder":
        """Set result limit."""
        self._query.limit = limit
        return self

    def offset(self, offset: int) -> "QueryBuilder":
        """Set result offset."""
        self._query.offset = offset
        return self

    def count(self) -> "QueryBuilder":
        """Change to COUNT operation."""
        self._query.operation = "count"
        return self

    def sum(self, column: str, alias: str = "sum") -> "QueryBuilder":
        """Add SUM aggregation."""
        self._query.add_aggregation("SUM", column, alias)
        return self

    def avg(self, column: str, alias: str = "avg") -> "QueryBuilder":
        """Add AVG aggregation."""
        self._query.add_aggregation("AVG", column, alias)
        return self

    def min(self, column: str, alias: str = "min") -> "QueryBuilder":
        """Add MIN aggregation."""
        self._query.add_aggregation("MIN", column, alias)
        return self

    def max(self, column: str, alias: str = "max") -> "QueryBuilder":
        """Add MAX aggregation."""
        self._query.add_aggregation("MAX", column, alias)
        return self

    def insert_values(self, values: dict[str, Any]) -> "QueryBuilder":
        """Set values for INSERT operation."""
        self._query.operation = "insert"
        self._query.values = [ColumnValue(column=col, value=val) for col, val in values.items()]
        return self

    def update_values(self, set_values: dict[str, Any]) -> "QueryBuilder":
        """Set values for UPDATE operation."""
        self._query.operation = "update"
        self._query.set_values = [
            ColumnValue(column=col, value=val) for col, val in set_values.items()
        ]
        return self

    def delete_op(self) -> "QueryBuilder":
        """Change to DELETE operation."""
        self._query.operation = "delete"
        return self

    async def execute(self) -> QueryResult:
        """Execute the built query."""
        if not self._query.table:
            raise ValueError("Table not specified")
        return await self.client.execute_query(self._query)
