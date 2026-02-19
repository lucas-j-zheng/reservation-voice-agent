"""
Shared call-context persistence helpers for outbound Twilio calls.
"""

import json
import logging

import redis.asyncio as redis

logger = logging.getLogger(__name__)

# In-memory fallback for when Redis is unavailable.
_call_context_store: dict[str, dict] = {}


async def get_call_context(redis_client: redis.Redis | None, context_id: str) -> dict | None:
    """Retrieve call context from Redis or in-memory fallback."""
    if redis_client:
        try:
            data = await redis_client.get(f"call_context:{context_id}")
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"Failed to get context from Redis: {e}")

    return _call_context_store.get(context_id)


async def store_call_context(
    redis_client: redis.Redis | None,
    context_id: str,
    context: dict,
) -> None:
    """Store call context in Redis or in-memory fallback."""
    if redis_client:
        try:
            await redis_client.setex(
                f"call_context:{context_id}",
                300,  # 5 minute TTL
                json.dumps(context),
            )
            return
        except Exception as e:
            logger.warning(f"Failed to store context in Redis: {e}")

    _call_context_store[context_id] = context
