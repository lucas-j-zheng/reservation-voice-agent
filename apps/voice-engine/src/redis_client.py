"""
Module-level Redis client accessor.
Initialized during app lifespan, accessed by orchestrator and handlers.
"""

import logging
import redis.asyncio as redis

logger = logging.getLogger(__name__)

_redis_client: redis.Redis | None = None


def set_redis_client(client: redis.Redis | None) -> None:
    """Set the module-level Redis client (called during app startup)."""
    global _redis_client
    _redis_client = client


def get_redis_client() -> redis.Redis | None:
    """Get the module-level Redis client."""
    return _redis_client
