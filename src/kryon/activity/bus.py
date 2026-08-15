"""Async event bus for the activity system.

Singleton — ``get_bus()`` returns the global bus. Subscribers are async
callbacks that receive each event. Subscriptions are not removed at
runtime (File #0 simplification). The bus is safe to call from any
coroutine.

Subscriber exceptions are caught and logged, never re-raised — a failing
subscriber must not break the agent.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from kryon.activity.event import Event
from kryon.core.logger import get_logger

Subscriber = Callable[[Event], Awaitable[None]]

_log = get_logger(__name__)


class EventBus:
    """Async pub/sub event bus."""

    def __init__(self) -> None:
        self._subscribers: list[Subscriber] = []
        self._lock = asyncio.Lock()

    def subscribe(self, callback: Subscriber) -> None:
        """Add a subscriber. Subscribers receive every emitted event.

        Args:
            callback: Async function called with each emitted event.
                Exceptions are caught and logged; they will not
                propagate to the emitter.
        """
        self._subscribers.append(callback)

    async def emit(self, event: Event) -> None:
        """Emit an event to all subscribers.

        Subscriber exceptions are caught and logged, not re-raised — a
        failing subscriber must not break the agent. Subscribers are
        snapshotted under a lock before iteration so concurrent
        ``subscribe()`` calls don't race with emit.

        Args:
            event: The event to broadcast.
        """
        async with self._lock:
            subs = list(self._subscribers)
        for sub in subs:
            try:
                await sub(event)
            except Exception as e:
                _log.warning(
                    "subscriber_failed",
                    subscriber=getattr(sub, "__name__", repr(sub)),
                    error=str(e),
                )

    def subscriber_count(self) -> int:
        """Return the number of currently-registered subscribers.

        For tests and diagnostics.
        """
        return len(self._subscribers)


_bus: EventBus | None = None


def get_bus() -> EventBus:
    """Get the global event bus singleton.

    Returns:
        The shared ``EventBus`` instance.
    """
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus


def reset_bus() -> None:
    """Reset the global bus (used in tests)."""
    global _bus
    _bus = None


__all__ = ["EventBus", "Subscriber", "get_bus", "reset_bus"]
