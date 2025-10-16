"""
Session Timer - Handles daily 5pm CT reset timing.

Responsibilities:
- Generate SESSION_TICK event at exactly 5:00pm CT every day
- Handle DST transitions automatically
- Prevent duplicate events on the same day
- Calculate time until next reset
- Support manual trigger for testing
- Graceful shutdown

Architecture reference: docs/architecture/04-state-management.md (Daily Reset Logic)
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

import pytz

logger = logging.getLogger(__name__)


class SessionTimer:
    """
    Session timer that fires SESSION_TICK events at 5pm CT daily.

    Handles timezone conversions, DST transitions, and prevents duplicate
    events within the same day.
    """

    def __init__(self, event_bus):
        """
        Initialize session timer.

        Args:
            event_bus: EventBus instance to publish SESSION_TICK events
        """
        self.event_bus = event_bus
        self.chicago_tz = pytz.timezone("America/Chicago")
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_reset_date: Optional[datetime] = None

    async def start(self):
        """Start the timer background task."""
        if self._running:
            logger.warning("SessionTimer already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._timer_loop())
        logger.info("SessionTimer started")

    async def stop(self):
        """Stop the timer gracefully."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        logger.info("SessionTimer stopped")

    def time_until_reset(self) -> timedelta:
        """
        Calculate time remaining until next 5pm CT reset.

        Returns:
            timedelta until next reset
        """
        now_ct = datetime.now(self.chicago_tz)
        reset_today = now_ct.replace(hour=17, minute=0, second=0, microsecond=0)

        # If past today's reset time, calculate for tomorrow
        if now_ct >= reset_today:
            reset_next = reset_today + timedelta(days=1)
        else:
            reset_next = reset_today

        return reset_next - now_ct

    async def trigger_reset(self):
        """
        Manually trigger reset (for testing).

        Fires SESSION_TICK event immediately without checking time.
        """
        await self._fire_session_tick()
        logger.info("Manual reset triggered")

    async def _timer_loop(self):
        """
        Main timer loop that checks every second for 5pm CT.

        After firing at 5pm, sleeps for 60 seconds to prevent duplicates.
        """
        try:
            while self._running:
                now_ct = datetime.now(self.chicago_tz)
                current_date = now_ct.date()

                # Check if it's 5pm CT and we haven't fired today
                if (
                    now_ct.hour == 17
                    and now_ct.minute == 0
                    and self._last_reset_date != current_date
                ):
                    await self._fire_session_tick()
                    self._last_reset_date = current_date

                    # Sleep for 60 seconds to prevent duplicate events
                    await asyncio.sleep(60)
                else:
                    # Check every second
                    await asyncio.sleep(1)

        except asyncio.CancelledError:
            logger.debug("SessionTimer loop cancelled")
            raise
        except Exception as e:
            logger.error(f"SessionTimer loop error: {e}")
            self._running = False
            raise

    async def _fire_session_tick(self):
        """Fire SESSION_TICK event to event bus."""
        now_ct = datetime.now(self.chicago_tz)
        await self.event_bus.emit(
            "SESSION_TICK",
            {
                "reset_time": now_ct,
                "source": "session_timer",
            },
            source="session_timer",
        )
        logger.info(f"SESSION_TICK event fired at {now_ct}")
