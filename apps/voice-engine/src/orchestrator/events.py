"""
Cascade event bus — persists events to DB and publishes via Redis pub/sub.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from src.db import PostgresClient
from src.redis_client import get_redis_client

logger = logging.getLogger(__name__)

# Redis channel for SSE consumers
CASCADE_EVENTS_CHANNEL = "cascade_events:{request_id}"


class EventBus:
    """Persist cascade events and broadcast to SSE listeners."""

    def __init__(self, db: PostgresClient):
        self._db = db

    async def emit(
        self,
        request_id: str,
        event_type: str,
        *,
        restaurant_id: str | None = None,
        restaurant_name: str | None = None,
        call_id: str | None = None,
        data: dict[str, Any] | None = None,
        request_type: str = "reservation",
    ) -> dict | None:
        """
        Persist a cascade event and publish it via Redis.

        Returns the created event row dict, or None on failure.
        """
        event_data = data or {}

        # Persist to cascade_events table
        row = None
        try:
            insert = {
                "request_id": request_id,
                "event_type": event_type,
                "data": json.dumps(event_data),
            }
            if restaurant_id:
                insert["restaurant_id"] = restaurant_id
            if call_id:
                insert["call_id"] = call_id

            result = self._db.table("cascade_events").insert(insert).execute()
            row = result.data[0] if result.data else None
            logger.info(f"Cascade event persisted: {event_type} for request {request_id}")
        except Exception as e:
            logger.error(f"Failed to persist cascade event: {e}")

        # Publish via Redis for SSE consumers
        redis = get_redis_client()
        if redis:
            sse_payload = {
                "event": event_type,
                "request_id": request_id,
                "request_type": request_type,
                "restaurant_id": restaurant_id,
                "restaurant_name": restaurant_name,
                "call_id": call_id,
                "data": event_data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            try:
                channel = CASCADE_EVENTS_CHANNEL.format(request_id=request_id)
                await redis.publish(channel, json.dumps(sse_payload))
            except Exception as e:
                logger.error(f"Failed to publish cascade event to Redis: {e}")

        return row
