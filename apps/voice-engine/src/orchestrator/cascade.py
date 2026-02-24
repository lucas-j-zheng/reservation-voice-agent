"""
Cascade Orchestrator
Tries restaurants in priority order, waits for call outcome, advances or stops.
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone

import redis.asyncio as aioredis

from src.db import PostgresClient
from src.call_context_store import get_call_context, store_call_context
from src.redis_client import get_redis_client
from src.brain.prompts import build_cascade_reservation_prompt
from .state import CascadeStatus, AttemptStatus, CallOutcome
from .events import EventBus
from .notifications import NotificationService

logger = logging.getLogger(__name__)

# How long to wait for a call outcome before treating as no-answer
CALL_OUTCOME_TIMEOUT = 120  # seconds
NO_ANSWER_TIMEOUT = 45  # seconds — Twilio ringing timeout


class CascadeOrchestrator:
    """
    Orchestrates calling multiple restaurants in priority order.

    Lifecycle:
      start() → for each restaurant: place call → wait outcome → next or stop
    Controls:
      pause() / resume() / skip() / reorder() / cancel()
    """

    def __init__(self, db: PostgresClient, request_id: str):
        self._db = db
        self._request_id = request_id
        self._event_bus = EventBus(db)
        self._notifications = NotificationService(db)

        # Control signals
        self._paused = asyncio.Event()
        self._paused.set()  # Not paused initially
        self._cancelled = False
        self._skip_current = False
        self._task: asyncio.Task | None = None

    # ------------------------------------------------------------------ #
    # Public controls
    # ------------------------------------------------------------------ #

    async def start(self) -> None:
        """Start the cascade in a background task."""
        self._task = asyncio.create_task(self._run_cascade())

    async def pause(self) -> None:
        """Pause the cascade after the current call finishes."""
        self._paused.clear()
        self._update_cascade_status(CascadeStatus.PAUSED)
        await self._event_bus.emit(self._request_id, "cascade_paused")
        logger.info(f"Cascade paused for request {self._request_id}")

    async def resume(self) -> None:
        """Resume a paused cascade."""
        self._paused.set()
        self._update_cascade_status(CascadeStatus.RUNNING)
        await self._event_bus.emit(self._request_id, "cascade_resumed")
        logger.info(f"Cascade resumed for request {self._request_id}")

    async def skip(self) -> None:
        """Skip the currently-calling restaurant and move to the next."""
        self._skip_current = True
        logger.info(f"Skip requested for request {self._request_id}")

    async def reorder(self, restaurant_order: list[str]) -> None:
        """
        Reorder the remaining restaurants.
        Only affects pending restaurants — doesn't touch already-attempted ones.
        """
        for new_priority, rid in enumerate(restaurant_order, start=1):
            try:
                self._db.table("request_restaurants").update(
                    {"priority": new_priority}
                ).eq("request_id", self._request_id).eq("restaurant_id", rid).execute()
            except Exception as e:
                logger.error(f"Failed to reorder restaurant {rid}: {e}")
        logger.info(f"Restaurants reordered for request {self._request_id}")

    async def cancel(self) -> None:
        """Cancel the cascade entirely."""
        self._cancelled = True
        self._paused.set()  # Unblock if paused so the loop can exit

        self._update_cascade_status(CascadeStatus.CANCELLED)
        self._db.table("requests").update(
            {"status": "cancelled"}
        ).eq("id", self._request_id).execute()

        await self._event_bus.emit(self._request_id, "cascade_cancelled")

        # Send notification
        contact_phone = self._get_contact_phone()
        user_id = self._get_user_id()
        if contact_phone:
            await self._notifications.notify_cascade_cancelled(
                self._request_id, user_id, contact_phone,
            )

        # Cancel the background task if running
        if self._task and not self._task.done():
            self._task.cancel()

        logger.info(f"Cascade cancelled for request {self._request_id}")

    # ------------------------------------------------------------------ #
    # Internal: the main cascade loop
    # ------------------------------------------------------------------ #

    async def _run_cascade(self) -> None:
        """Main cascade loop — iterate restaurants by priority."""
        try:
            # Load request info
            req = self._load_request()
            if not req:
                logger.error(f"Request {self._request_id} not found")
                return

            # Load restaurants sorted by priority
            restaurants = self._load_restaurants()
            if not restaurants:
                logger.error(f"No restaurants for request {self._request_id}")
                self._update_cascade_status(CascadeStatus.EXHAUSTED)
                return

            # Mark cascade as running
            self._update_cascade_status(CascadeStatus.RUNNING)
            self._db.table("requests").update(
                {"status": "in_progress"}
            ).eq("id", self._request_id).execute()

            await self._event_bus.emit(
                self._request_id, "cascade_started",
                data={"restaurant_count": len(restaurants)},
            )

            # Send start notification
            contact_phone = req.get("contact_phone")
            user_id = str(req.get("user_id")) if req.get("user_id") else None
            if contact_phone:
                await self._notifications.notify_cascade_started(
                    self._request_id, user_id, contact_phone, len(restaurants),
                )

            # Iterate restaurants
            for idx, rr in enumerate(restaurants):
                if self._cancelled:
                    break

                # Wait if paused
                await self._paused.wait()
                if self._cancelled:
                    break

                # Skip already-attempted restaurants
                if rr["attempt_status"] in (
                    AttemptStatus.SUCCEEDED.value,
                    AttemptStatus.SKIPPED.value,
                ):
                    continue

                # Update current index
                self._db.table("requests").update(
                    {"current_restaurant_idx": idx}
                ).eq("id", self._request_id).execute()

                # Load restaurant details
                restaurant = self._load_restaurant(rr["restaurant_id"])
                if not restaurant:
                    logger.warning(f"Restaurant {rr['restaurant_id']} not found, skipping")
                    continue

                restaurant_name = restaurant["name"]
                restaurant_phone = restaurant["phone"]
                restaurant_id = str(rr["restaurant_id"])

                logger.info(
                    f"Cascade [{idx+1}/{len(restaurants)}]: calling {restaurant_name} "
                    f"({restaurant_phone}) for request {self._request_id}"
                )

                # Notify user
                if contact_phone:
                    await self._notifications.notify_trying_restaurant(
                        self._request_id, user_id, contact_phone,
                        restaurant_name, idx + 1, len(restaurants),
                    )

                # Attempt the call
                outcome = await self._attempt_restaurant(
                    req, rr, restaurant, idx + 1, len(restaurants),
                )

                if outcome == CallOutcome.SUCCEEDED:
                    # Reservation confirmed — stop cascade
                    self._update_cascade_status(CascadeStatus.COMPLETED)
                    self._db.table("requests").update(
                        {"status": "completed"}
                    ).eq("id", self._request_id).execute()

                    await self._event_bus.emit(
                        self._request_id, "cascade_completed",
                        restaurant_id=restaurant_id,
                        restaurant_name=restaurant_name,
                    )

                    # Notification for success is handled inside _attempt_restaurant
                    return

                # Otherwise, continue to next restaurant

            # All restaurants exhausted
            if not self._cancelled:
                self._update_cascade_status(CascadeStatus.EXHAUSTED)
                self._db.table("requests").update(
                    {"status": "failed"}
                ).eq("id", self._request_id).execute()

                await self._event_bus.emit(self._request_id, "cascade_exhausted")

                if contact_phone:
                    await self._notifications.notify_cascade_exhausted(
                        self._request_id, user_id, contact_phone,
                    )

        except asyncio.CancelledError:
            logger.info(f"Cascade task cancelled for request {self._request_id}")
        except Exception as e:
            logger.error(f"Cascade error for request {self._request_id}: {e}", exc_info=True)
            self._update_cascade_status(CascadeStatus.EXHAUSTED)

    async def _attempt_restaurant(
        self,
        req: dict,
        rr: dict,
        restaurant: dict,
        index: int,
        total: int,
    ) -> CallOutcome:
        """
        Place a call to one restaurant and wait for the outcome.
        Returns the CallOutcome.
        """
        restaurant_id = str(rr["restaurant_id"])
        restaurant_name = restaurant["name"]
        restaurant_phone = restaurant["phone"]
        rr_id = str(rr["id"])

        # Mark as calling
        self._db.table("request_restaurants").update({
            "attempt_status": AttemptStatus.CALLING.value,
            "attempt_count": rr["attempt_count"] + 1,
            "attempted_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", rr_id).execute()

        await self._event_bus.emit(
            self._request_id, "restaurant_calling",
            restaurant_id=restaurant_id,
            restaurant_name=restaurant_name,
            data={"index": index, "total": total},
        )

        # Place the outbound call via Twilio
        call_sid = await self._place_call(req, restaurant, rr["attempt_count"] + 1)
        if not call_sid:
            # Twilio call placement failed
            self._db.table("request_restaurants").update({
                "attempt_status": AttemptStatus.FAILED.value,
                "failure_reason": "Failed to place outbound call",
            }).eq("id", rr_id).execute()

            await self._event_bus.emit(
                self._request_id, "restaurant_failed",
                restaurant_id=restaurant_id,
                restaurant_name=restaurant_name,
                data={"reason": "Failed to place outbound call"},
            )
            return CallOutcome.FAILED

        # Create call record in DB
        call_id = self._create_call_record(call_sid, restaurant_id, rr["attempt_count"] + 1)
        if call_id:
            self._db.table("request_restaurants").update({
                "last_call_id": call_id,
            }).eq("id", rr_id).execute()

        # Wait for call outcome from Redis
        outcome = await self._wait_for_outcome(call_id, call_sid)

        # Handle skip request
        if self._skip_current:
            self._skip_current = False
            outcome = CallOutcome.FAILED  # Treat as failed and move on
            # Mark as skipped
            self._db.table("request_restaurants").update({
                "attempt_status": AttemptStatus.SKIPPED.value,
            }).eq("id", rr_id).execute()

            await self._event_bus.emit(
                self._request_id, "restaurant_skipped",
                restaurant_id=restaurant_id,
                restaurant_name=restaurant_name,
            )
            return outcome

        # Update attempt status based on outcome
        if outcome == CallOutcome.SUCCEEDED:
            self._db.table("request_restaurants").update({
                "attempt_status": AttemptStatus.SUCCEEDED.value,
            }).eq("id", rr_id).execute()

            await self._event_bus.emit(
                self._request_id, "restaurant_succeeded",
                restaurant_id=restaurant_id,
                restaurant_name=restaurant_name,
                call_id=call_id,
            )

            # Send confirmation notification
            contact_phone = req.get("contact_phone")
            user_id = str(req.get("user_id")) if req.get("user_id") else None
            if contact_phone:
                await self._notifications.notify_reservation_confirmed(
                    self._request_id, user_id, contact_phone,
                    restaurant_name,
                    str(req.get("requested_date", "")),
                    str(req.get("time_range_start", "")),
                    req.get("party_size", 0),
                )

        elif outcome == CallOutcome.NO_ANSWER:
            self._db.table("request_restaurants").update({
                "attempt_status": AttemptStatus.NO_ANSWER.value,
                "failure_reason": "No answer",
            }).eq("id", rr_id).execute()

            await self._event_bus.emit(
                self._request_id, "restaurant_no_answer",
                restaurant_id=restaurant_id,
                restaurant_name=restaurant_name,
            )

        else:
            # FAILED or NO_AVAILABILITY
            failure_reason = "No availability" if outcome == CallOutcome.NO_AVAILABILITY else "Call failed"
            self._db.table("request_restaurants").update({
                "attempt_status": AttemptStatus.FAILED.value,
                "failure_reason": failure_reason,
            }).eq("id", rr_id).execute()

            await self._event_bus.emit(
                self._request_id, "restaurant_failed",
                restaurant_id=restaurant_id,
                restaurant_name=restaurant_name,
                call_id=call_id,
                data={"reason": failure_reason},
            )

        return outcome

    async def _place_call(self, req: dict, restaurant: dict, attempt_number: int) -> str | None:
        """Place an outbound Twilio call. Returns the Call SID or None on failure."""
        try:
            from twilio.rest import Client

            sid = os.getenv("TWILIO_ACCOUNT_SID")
            token = os.getenv("TWILIO_AUTH_TOKEN")
            from_phone = os.getenv("TWILIO_PHONE_NUMBER")

            if not all([sid, token, from_phone]):
                logger.error("Twilio credentials not configured")
                return None

            client = Client(sid, token)

            base_url = os.getenv("TUNNEL_URL") or os.getenv("BASE_URL", "http://localhost:8000")

            # Build cascade system prompt with reservation details
            system_prompt = build_cascade_reservation_prompt(
                party_size=req.get("party_size", 2),
                preferred_date=str(req.get("requested_date", "")),
                time_range_start=req.get("time_range_start", ""),
                time_range_end=req.get("time_range_end", ""),
                restaurant_name=restaurant["name"],
                contact_phone=req.get("contact_phone", ""),
                special_requests=req.get("special_requests"),
                user_name=req.get("user_name"),
            )

            # Store call context so the WebSocket handler can retrieve it
            context_id = str(uuid.uuid4())
            context = {
                "request_id": self._request_id,
                "restaurant_id": str(restaurant.get("id", "")),
                "restaurant_name": restaurant["name"],
                "user_id": str(req["user_id"]) if req.get("user_id") else "",
                "user_name": req.get("user_name", ""),
                "party_size": req.get("party_size", 2),
                "requested_date": str(req.get("requested_date", "")),
                "time_range_start": req.get("time_range_start", ""),
                "time_range_end": req.get("time_range_end", ""),
                "contact_phone": req.get("contact_phone", ""),
                "special_requests": req.get("special_requests", ""),
                "system_prompt": system_prompt,
            }

            redis = get_redis_client()
            await store_call_context(redis, context_id, context)

            # Verify context is retrievable before dialing to avoid deterministic TwiML failure.
            stored_context = await get_call_context(redis, context_id)
            if not stored_context:
                logger.error(
                    "Call context unavailable after store attempt; aborting outbound dial "
                    f"for restaurant {restaurant['name']} (context: {context_id})"
                )
                return None

            # Use the outbound TwiML endpoint that passes context to the WebSocket
            twiml_url = f"{base_url}/ws/twilio/outbound-twiml?context_id={context_id}"
            status_callback_url = f"{base_url}/api/calls/status-callback"

            call = client.calls.create(
                to=restaurant["phone"],
                from_=from_phone,
                url=twiml_url,
                status_callback=status_callback_url,
                status_callback_event=["initiated", "ringing", "answered", "completed"],
                timeout=NO_ANSWER_TIMEOUT,
            )

            logger.info(f"Placed outbound call: {call.sid} to {restaurant['phone']} (context: {context_id})")
            return call.sid

        except Exception as e:
            logger.error(f"Failed to place call to {restaurant['phone']}: {e}")
            return None

    def _create_call_record(self, call_sid: str, restaurant_id: str, attempt_number: int) -> str | None:
        """Create a call record in the DB. Returns the call ID."""
        try:
            result = self._db.table("calls").insert({
                "twilio_sid": call_sid,
                "request_id": self._request_id,
                "restaurant_id": restaurant_id,
                "status": "ongoing",
                "attempt_number": attempt_number,
            }).execute()
            if result.data:
                return str(result.data[0]["id"])
        except Exception as e:
            logger.error(f"Failed to create call record: {e}")
        return None

    async def _wait_for_outcome(self, call_id: str | None, call_sid: str) -> CallOutcome:
        """
        Wait for call outcome from Redis.
        Listens on both call_complete:{call_id} (tool signals) and
        call_status:{call_sid} (Twilio status callbacks).
        """
        redis = get_redis_client()
        if not redis:
            logger.warning("No Redis — cannot wait for call outcome, waiting fixed timeout")
            await asyncio.sleep(CALL_OUTCOME_TIMEOUT)
            return CallOutcome.FAILED

        pubsub = redis.pubsub()
        channels = []
        if call_id:
            channels.append(f"call_complete:{call_id}")
        channels.append(f"call_status:{call_sid}")

        await pubsub.subscribe(*channels)

        try:
            deadline = asyncio.get_event_loop().time() + CALL_OUTCOME_TIMEOUT

            while True:
                # Check skip signal
                if self._skip_current or self._cancelled:
                    return CallOutcome.FAILED

                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    logger.warning(f"Call outcome timeout for {call_sid}")
                    return CallOutcome.NO_ANSWER

                try:
                    msg = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                        timeout=min(remaining, 2.0),
                    )
                except asyncio.TimeoutError:
                    continue

                if msg is None:
                    continue

                if msg["type"] != "message":
                    continue

                channel = msg["channel"]
                if isinstance(channel, bytes):
                    channel = channel.decode()

                data_str = msg["data"]
                if isinstance(data_str, bytes):
                    data_str = data_str.decode()

                try:
                    payload = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                # Tool completion signal
                if call_id and channel == f"call_complete:{call_id}":
                    outcome_str = payload.get("outcome", "failed")
                    if outcome_str == "succeeded":
                        return CallOutcome.SUCCEEDED
                    elif outcome_str == "no_availability":
                        return CallOutcome.NO_AVAILABILITY
                    else:
                        return CallOutcome.FAILED

                # Twilio status callback
                if channel == f"call_status:{call_sid}":
                    status = payload.get("status", "")
                    if status in ("busy", "no-answer"):
                        return CallOutcome.NO_ANSWER
                    elif status == "failed":
                        return CallOutcome.FAILED
                    # "completed" without a tool signal means the call ended
                    # without save_booking — poll for tool signal during grace period
                    elif status == "completed":
                        grace_deadline = asyncio.get_event_loop().time() + 5
                        while asyncio.get_event_loop().time() < grace_deadline:
                            grace_remaining = grace_deadline - asyncio.get_event_loop().time()
                            if grace_remaining <= 0:
                                break
                            try:
                                tool_msg = await asyncio.wait_for(
                                    pubsub.get_message(ignore_subscribe_messages=True, timeout=0.5),
                                    timeout=min(grace_remaining, 1.0),
                                )
                            except asyncio.TimeoutError:
                                continue
                            if tool_msg and tool_msg["type"] == "message":
                                ch = tool_msg["channel"]
                                if isinstance(ch, bytes):
                                    ch = ch.decode()
                                if call_id and ch == f"call_complete:{call_id}":
                                    d = tool_msg["data"]
                                    if isinstance(d, bytes):
                                        d = d.decode()
                                    try:
                                        p = json.loads(d)
                                        outcome_str = p.get("outcome", "failed")
                                        if outcome_str == "succeeded":
                                            return CallOutcome.SUCCEEDED
                                        elif outcome_str == "no_availability":
                                            return CallOutcome.NO_AVAILABILITY
                                    except json.JSONDecodeError:
                                        pass
                        return CallOutcome.FAILED

        finally:
            await pubsub.unsubscribe(*channels)
            await pubsub.aclose()

    # ------------------------------------------------------------------ #
    # DB helpers
    # ------------------------------------------------------------------ #

    def _load_request(self) -> dict | None:
        """Load request + reservation_details merged into one dict."""
        result = self._db.table("requests").select("*").eq(
            "id", self._request_id
        ).execute()
        if not result.data:
            return None
        req = result.data[0]

        # Merge reservation details (party_size, dates, contact_phone, etc.)
        details = self._db.table("reservation_details").select("*").eq(
            "request_id", self._request_id
        ).execute()
        if details.data:
            req.update(details.data[0])

        # Attach user name for concierge-style prompt identity when available.
        user_id = req.get("user_id")
        if user_id:
            try:
                user_result = self._db.table("users").select("name").eq(
                    "id", user_id
                ).execute()
                if user_result.data and user_result.data[0].get("name"):
                    req["user_name"] = user_result.data[0]["name"]
            except Exception as e:
                logger.warning(f"Failed to load user name for request {self._request_id}: {e}")

        return req

    def _load_restaurants(self) -> list[dict]:
        result = self._db.table("request_restaurants").select("*").eq(
            "request_id", self._request_id
        ).order("priority", ascending=True).execute()
        return result.data

    def _load_restaurant(self, restaurant_id: str) -> dict | None:
        result = self._db.table("restaurants").select("*").eq(
            "id", restaurant_id
        ).execute()
        return result.data[0] if result.data else None

    def _update_cascade_status(self, status: CascadeStatus) -> None:
        try:
            self._db.table("requests").update({
                "cascade_status": status.value,
            }).eq("id", self._request_id).execute()
        except Exception as e:
            logger.error(f"Failed to update cascade status: {e}")

    def _get_contact_phone(self) -> str | None:
        req = self._load_request()
        return req.get("contact_phone") if req else None

    def _get_user_id(self) -> str | None:
        req = self._load_request()
        uid = req.get("user_id") if req else None
        return str(uid) if uid else None
