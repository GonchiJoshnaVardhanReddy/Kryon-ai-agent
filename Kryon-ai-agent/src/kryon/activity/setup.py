"""Activity system setup — called at app startup.

Wires the live console to the bus. The activity log auto-subscribes
itself on the first call to ``get_log()`` (see ``kryon.activity.log``),
so the log does not need to be wired here. Transcript files are
managed per-subagent, not via the bus.

Idempotent — safe to call multiple times; subsequent calls are
no-ops as long as the bus hasn't been reset.
"""

from __future__ import annotations

from kryon.activity.bus import EventBus, get_bus
from kryon.activity.console import get_console
from kryon.activity.log import get_log

_SETUP_DONE_FLAG = "_kryon_activity_setup_done"


def setup_activity(verbose: bool = True) -> EventBus:
    """Initialize the activity system.

    Called once at app startup. Subscribes the console to the bus
    (the log auto-subscribes via ``get_log()``). Idempotent — if
    already set up on this bus instance, returns the existing bus
    without re-subscribing.

    Args:
        verbose: If True, the live console is enabled. If False, the
            console is disabled (events still go to the log).

    Returns:
        The configured ``EventBus``.
    """
    bus = get_bus()
    console = get_console()

    if verbose:
        console.enable()
    else:
        console.disable()

    if getattr(bus, _SETUP_DONE_FLAG, False):
        return bus

    bus.subscribe(console)
    # Force log wiring by calling get_log() (idempotent if already wired)
    get_log()
    setattr(bus, _SETUP_DONE_FLAG, True)
    return bus


def reset_activity() -> None:
    """Reset all activity-system singletons. Used in tests."""

    # avoids the (small) cost of importing them at module load.
    from kryon.activity.bus import reset_bus  # noqa: PLC0415
    from kryon.activity.console import reset_console  # noqa: PLC0415
    from kryon.activity.log import reset_log  # noqa: PLC0415
    from kryon.activity.transcript import reset_transcript  # noqa: PLC0415

    reset_bus()
    reset_console()
    reset_log()
    reset_transcript()


__all__ = ["reset_activity", "setup_activity"]
