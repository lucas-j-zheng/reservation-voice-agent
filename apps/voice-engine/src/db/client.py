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
        self._filters: list[tuple[str, str, Any]] = []
        self._select_columns: str = "*"

    def select(self, columns: str = "*") -> "TableQuery":
        """Select columns from the table."""
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

        query = f"""
            SELECT {self._select_columns}
            FROM {self._table}
            {where_clause}
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


def get_db_client() -> PostgresClient | None:
    """
    Get database client from environment.

    Checks for DATABASE_URL first (direct Postgres),
    falls back to SUPABASE_URL if available.
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
            return None

    logger.warning("DATABASE_URL not set - database disabled")
    return None
