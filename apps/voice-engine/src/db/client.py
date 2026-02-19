"""
Direct Postgres Client
Provides a Supabase-like interface for direct Postgres connections.
Used for local development with sam-postgres container.
"""

import os
import logging
from typing import Any
from urllib.parse import urlparse

import psycopg2
import psycopg2.extensions
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class QueryResult:
    """Wrapper for query results to mimic Supabase response."""

    def __init__(self, data: list[dict] | None = None):
        self.data = data or []


class TableQuery:
    """Fluent query builder that mimics Supabase table operations."""

    def __init__(self, client: "PostgresClient", table_name: str):
        self._client = client
        self._table = table_name
        self._operation: str | None = None
        self._data: dict | None = None
        self._select_columns: str = "*"
        self._filters: list[tuple[str, str, Any]] = []
        self._order_by: list[tuple[str, bool]] = []  # (column, ascending)

    def select(self, columns: str = "*") -> "TableQuery":
        """Select columns (starts a SELECT query)."""
        self._operation = "select"
        self._select_columns = columns
        return self

    def insert(self, data: dict) -> "TableQuery":
        """Insert a row."""
        self._operation = "insert"
        self._data = data
        return self

    def update(self, data: dict) -> "TableQuery":
        """Update rows."""
        self._operation = "update"
        self._data = data
        return self

    def eq(self, column: str, value: Any) -> "TableQuery":
        """Add equality filter."""
        self._filters.append((column, "=", value))
        return self

    def order(self, column: str, ascending: bool = True) -> "TableQuery":
        """Add ORDER BY clause."""
        self._order_by.append((column, ascending))
        return self

    def execute(self) -> QueryResult:
        """Execute the query."""
        conn = self._client._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if self._operation == "select":
                    return self._execute_select(cur)
                elif self._operation == "insert":
                    return self._execute_insert(cur)
                elif self._operation == "update":
                    return self._execute_update(cur)
                else:
                    raise ValueError(f"Unknown operation: {self._operation}")
        finally:
            conn.commit()

    def _execute_select(self, cur) -> QueryResult:
        """Execute SELECT and return matching rows."""
        where_clause = ""
        values = []

        if self._filters:
            conditions = [f"{col} {op} %s" for col, op, _ in self._filters]
            where_clause = "WHERE " + " AND ".join(conditions)
            values = [val for _, _, val in self._filters]

        order_clause = ""
        if self._order_by:
            parts = []
            for col, asc in self._order_by:
                parts.append(f"{col} {'ASC' if asc else 'DESC'}")
            order_clause = "ORDER BY " + ", ".join(parts)

        query = f"""
            SELECT {self._select_columns}
            FROM {self._table}
            {where_clause}
            {order_clause}
        """
        cur.execute(query, values)
        rows = cur.fetchall()
        return QueryResult([dict(row) for row in rows] if rows else [])

    def _execute_insert(self, cur) -> QueryResult:
        """Execute INSERT and return the inserted row."""
        columns = list(self._data.keys())
        values = list(self._data.values())
        placeholders = ", ".join(["%s"] * len(values))
        col_names = ", ".join(columns)

        query = f"""
            INSERT INTO {self._table} ({col_names})
            VALUES ({placeholders})
            RETURNING *
        """
        cur.execute(query, values)
        row = cur.fetchone()
        return QueryResult([dict(row)] if row else [])

    def _execute_update(self, cur) -> QueryResult:
        """Execute UPDATE and return the updated row."""
        set_clause = ", ".join([f"{k} = %s" for k in self._data.keys()])
        values = list(self._data.values())

        where_clause = ""
        if self._filters:
            conditions = [f"{col} {op} %s" for col, op, _ in self._filters]
            where_clause = "WHERE " + " AND ".join(conditions)
            values.extend([val for _, _, val in self._filters])

        query = f"""
            UPDATE {self._table}
            SET {set_clause}
            {where_clause}
            RETURNING *
        """
        cur.execute(query, values)
        row = cur.fetchone()
        return QueryResult([dict(row)] if row else [])

    def _execute_select(self, cur) -> QueryResult:
        """Execute SELECT and return matching rows."""
        values = []

        where_clause = ""
        if self._filters:
            conditions = [f"{col} {op} %s" for col, op, _ in self._filters]
            where_clause = "WHERE " + " AND ".join(conditions)
            values.extend([val for _, _, val in self._filters])

        order_clause = ""
        if self._order_by:
            parts = [f"{col} {'ASC' if asc else 'DESC'}" for col, asc in self._order_by]
            order_clause = "ORDER BY " + ", ".join(parts)

        query = f"""
            SELECT {self._select_columns}
            FROM {self._table}
            {where_clause}
            {order_clause}
        """
        cur.execute(query, values)
        rows = cur.fetchall()
        return QueryResult([dict(row) for row in rows])


class PostgresClient:
    """
    Direct Postgres client with Supabase-like interface.

    Usage:
        client = PostgresClient(database_url)
        result = client.table("calls").insert({"twilio_sid": "CA123"}).execute()
        print(result.data[0]["id"])
    """

    def __init__(self, database_url: str):
        self._database_url = database_url
        self._conn: psycopg2.extensions.connection | None = None
        logger.info(f"PostgresClient initialized for {self._mask_url(database_url)}")

    def _mask_url(self, url: str) -> str:
        """Mask password in URL for logging."""
        parsed = urlparse(url)
        if parsed.password:
            return url.replace(parsed.password, "***")
        return url

    def _get_connection(self) -> psycopg2.extensions.connection:
        """Get or create database connection."""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self._database_url)
        return self._conn

    def table(self, name: str) -> TableQuery:
        """Start a query on a table."""
        return TableQuery(self, name)

    def close(self) -> None:
        """Close the database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()
            logger.info("PostgresClient connection closed")


class SupabaseQueryWrapper:
    """
    Wraps a Supabase postgrest query builder to normalize the
    order() signature to match PostgresClient's (ascending=True).
    """

    def __init__(self, builder):
        self._builder = builder

    def select(self, columns: str = "*") -> "SupabaseQueryWrapper":
        return SupabaseQueryWrapper(self._builder.select(columns))

    def insert(self, data: dict) -> "SupabaseQueryWrapper":
        return SupabaseQueryWrapper(self._builder.insert(data))

    def update(self, data: dict) -> "SupabaseQueryWrapper":
        return SupabaseQueryWrapper(self._builder.update(data))

    def eq(self, column: str, value: Any) -> "SupabaseQueryWrapper":
        return SupabaseQueryWrapper(self._builder.eq(column, value))

    def order(self, column: str, ascending: bool = True) -> "SupabaseQueryWrapper":
        return SupabaseQueryWrapper(self._builder.order(column, desc=not ascending))

    def execute(self):
        return self._builder.execute()


class SupabaseClientWrapper:
    """
    Wraps the Supabase client so .table() returns our normalized
    SupabaseQueryWrapper with a consistent order() signature.
    """

    def __init__(self, client):
        self._client = client

    def table(self, name: str) -> SupabaseQueryWrapper:
        return SupabaseQueryWrapper(self._client.table(name))

    def close(self) -> None:
        # Supabase SDK doesn't need explicit close
        pass


def get_db_client() -> PostgresClient | SupabaseClientWrapper | None:
    """
    Get database client from environment.

    Checks for DATABASE_URL first (direct Postgres),
    falls back to SUPABASE_URL + SUPABASE_SERVICE_KEY.
    """
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        try:
            client = PostgresClient(database_url)
            # Test connection
            client._get_connection()
            logger.info("Connected to Postgres via DATABASE_URL")
            return client
        except Exception as e:
            logger.error(f"Failed to connect to Postgres: {e}")
            # Fall through to try Supabase

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

    if supabase_url and supabase_key:
        try:
            from supabase import create_client
            client = create_client(supabase_url, supabase_key)
            logger.info(f"Connected to Supabase at {supabase_url}")
            return SupabaseClientWrapper(client)
        except Exception as e:
            logger.error(f"Failed to connect to Supabase: {e}")
            return None

    logger.warning("No database credentials set - database disabled")
    return None
