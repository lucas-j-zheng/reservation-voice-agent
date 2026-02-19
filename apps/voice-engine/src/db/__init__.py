"""Database module — supports direct Postgres or Supabase."""

from .client import PostgresClient, SupabaseClientWrapper, get_db_client

__all__ = ["PostgresClient", "SupabaseClientWrapper", "get_db_client"]
