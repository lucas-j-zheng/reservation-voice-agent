"""
SMS notifications via Twilio for cascade status updates.
"""

import os
import logging
from datetime import datetime, timezone

from src.db import PostgresClient

logger = logging.getLogger(__name__)


class NotificationService:
    """Send SMS notifications about cascade progress."""

    def __init__(self, db: PostgresClient):
        self._db = db
        self._twilio_client = None

    def _get_twilio(self):
        """Lazy-init Twilio client."""
        if self._twilio_client is None:
            from twilio.rest import Client
            sid = os.getenv("TWILIO_ACCOUNT_SID")
            token = os.getenv("TWILIO_AUTH_TOKEN")
            if sid and token:
                self._twilio_client = Client(sid, token)
            else:
                logger.warning("Twilio credentials not configured — SMS disabled")
        return self._twilio_client

    async def send_sms(
        self,
        request_id: str,
        user_id: str | None,
        to_phone: str,
        notification_type: str,
        message: str,
    ) -> bool:
        """
        Send an SMS and record it in the notifications table.
        Returns True if sent successfully.
        """
        # Record notification in DB
        notif = {
            "request_id": request_id,
            "channel": "sms",
            "notification_type": notification_type,
            "message": message,
            "status": "pending",
        }
        if user_id:
            notif["user_id"] = user_id

        try:
            result = self._db.table("notifications").insert(notif).execute()
            notif_id = result.data[0]["id"] if result.data else None
        except Exception as e:
            logger.error(f"Failed to record notification: {e}")
            notif_id = None

        # Send via Twilio
        twilio = self._get_twilio()
        if not twilio:
            logger.warning(f"SMS not sent (no Twilio client): {message}")
            return False

        from_phone = os.getenv("TWILIO_PHONE_NUMBER")
        if not from_phone:
            logger.warning("TWILIO_PHONE_NUMBER not set — cannot send SMS")
            return False

        try:
            twilio.messages.create(
                body=message,
                from_=from_phone,
                to=to_phone,
            )
            logger.info(f"SMS sent to {to_phone}: {notification_type}")

            # Update notification status
            if notif_id:
                self._db.table("notifications").update({
                    "status": "sent",
                    "sent_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", notif_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to send SMS to {to_phone}: {e}")
            if notif_id:
                self._db.table("notifications").update({
                    "status": "failed",
                }).eq("id", notif_id).execute()
            return False

    async def notify_cascade_started(
        self, request_id: str, user_id: str | None, to_phone: str, restaurant_count: int
    ) -> bool:
        return await self.send_sms(
            request_id, user_id, to_phone,
            "cascade_started",
            f"Sam is now calling {restaurant_count} restaurant(s) to find your reservation. We'll text you with updates!",
        )

    async def notify_trying_restaurant(
        self, request_id: str, user_id: str | None, to_phone: str, restaurant_name: str, index: int, total: int
    ) -> bool:
        return await self.send_sms(
            request_id, user_id, to_phone,
            "restaurant_trying",
            f"Trying restaurant {index}/{total}: {restaurant_name}...",
        )

    async def notify_reservation_confirmed(
        self, request_id: str, user_id: str | None, to_phone: str,
        restaurant_name: str, date: str, time: str, party_size: int,
        confirmation_code: str | None = None,
    ) -> bool:
        msg = f"Reservation confirmed at {restaurant_name} for {party_size} on {date} at {time}."
        if confirmation_code:
            msg += f" Confirmation: {confirmation_code}"
        return await self.send_sms(
            request_id, user_id, to_phone,
            "reservation_confirmed", msg,
        )

    async def notify_cascade_exhausted(
        self, request_id: str, user_id: str | None, to_phone: str
    ) -> bool:
        return await self.send_sms(
            request_id, user_id, to_phone,
            "cascade_exhausted",
            "Unfortunately, none of the restaurants had availability. Please try different times or restaurants.",
        )

    async def notify_cascade_cancelled(
        self, request_id: str, user_id: str | None, to_phone: str
    ) -> bool:
        return await self.send_sms(
            request_id, user_id, to_phone,
            "cascade_cancelled",
            "Your reservation search has been cancelled.",
        )
