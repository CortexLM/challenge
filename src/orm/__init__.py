"""ORM module for secure read-only database queries."""

from .client import (
    Aggregation,
    ColumnValue,
    OrderBy,
    ORMQuery,
    QueryBuilder,
    QueryFilter,
    QueryResult,
    SecureORMClient,
)
from .permissions import (
    ORMPermissions,
    TablePermission,
    extract_permissions_from_models,
    readable_table,
)

__all__ = [
    # Permissions
    "TablePermission",
    "ORMPermissions",
    "readable_table",
    "extract_permissions_from_models",
    # Client
    "QueryFilter",
    "OrderBy",
    "Aggregation",
    "ColumnValue",
    "ORMQuery",
    "QueryResult",
    "SecureORMClient",
    "QueryBuilder",
]
