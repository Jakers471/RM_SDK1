"""
TIME_TICK Event Generator

Generates periodic TIME_TICK events for time-based rule evaluation.
Used by NoStopLossGrace, SessionBlock, CooldownAfterLoss, and other time-dependent rules.

Architecture reference: docs/architecture/02-risk-engine.md
"""

import asyncio
from datetime import datetime
from typing import Callable, Optional
from uuid import uuid4

from src.state.models import Event


class TimeTickGenerator:
    """
    Generates TIME_TICK events at regular intervals.

    TIME_TICK events are low-priority events that trigger evaluation of
    time-based rules such as grace periods, cooldowns, and session times.

    Configuration:
        interval_seconds: Seconds between ticks (default: 1)
    """

    def __init__(self, interval_seconds: int = 1):
        """
        Initialize TIME_TICK generator.

        Args:
            interval_seconds: Seconds between ticks
        """
        self.interval_seconds = interval_seconds
        self.enabled = True
        self._callback: Optional[Callable] = None
        self._running = False
        self._paused = False
        self._task: Optional[asyncio.Task] = None

    def set_callback(self, callback: Callable):
        """
        Set callback to receive tick events.

        Args:
            callback: Async function that receives Event objects
        """
        self._callback = callback

    def create_tick_event(self, current_time: datetime) -> Event:
        """
        Create TIME_TICK event.

        Args:
            current_time: Current timestamp

        Returns:
            TIME_TICK Event object
        """
        return Event(
            event_id=uuid4(),
            event_type="TIME_TICK",
            timestamp=current_time,
            priority=5,  # Low priority - background monitoring
            account_id="system",  # Will be processed for all accounts
            source="system",
            data={
                "current_time": current_time
            }
        )

    async def start(self):
        """Start generating ticks."""
        self._running = True
        self._paused = False

    async def stop(self):
        """Stop generating ticks."""
        self._running = False
        self._paused = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def pause(self):
        """Pause tick generation (can be resumed)."""
        self._paused = True

    def resume(self):
        """Resume tick generation after pause."""
        self._paused = False

    async def tick(self):
        """
        Generate single tick event (for testing).

        In production, this would be called by an event loop.
        For testing, we call it manually to control timing.
        """
        if not self._running or self._paused:
            return

        # Generate tick event with current time
        from datetime import datetime, timezone
        tick_event = self.create_tick_event(datetime.now(timezone.utc))

        # Call callback if set
        if self._callback:
            await self._callback(tick_event)

    async def run_forever(self):
        """
        Run tick generation loop continuously.

        This method should be called in a background task in production.
        For testing, use tick() for manual control.
        """
        self._running = True
        self._paused = False

        try:
            while self._running:
                if not self._paused:
                    await self.tick()

                # Wait for interval before next tick
                await asyncio.sleep(self.interval_seconds)
        except asyncio.CancelledError:
            pass
        finally:
            self._running = False
