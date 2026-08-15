"""Live console subscriber — renders events to the terminal in real time.

Subscribes to the EventBus and prints each event as a single colored
line. Color is keyed off the event type so the operator can scan a
screen full of activity and instantly see state transitions (blue),
tool calls (cyan), LLM calls (magenta), scope blocks (red), findings
(green), and errors (red bold).

Disable by passing ``enabled=False`` at construction time, or call
``disable()`` at runtime (e.g., for ``--quiet`` mode).
"""

from __future__ import annotations

from typing import ClassVar

from rich.console import Console
from rich.text import Text

from kryon.activity.event import Event


class LiveConsole:
    """Subscriber that renders events to stdout in real time.

    Color codes:
    - state transitions: blue
    - tool calls: cyan
    - LLM calls: magenta
    - scope blocks: red
    - findings: green (bold)
    - errors: red (bold)
    """

    COLOR_MAP: ClassVar[dict[str, str]] = {
        "subagent_start": "cyan",
        "subagent_end": "cyan",
        "tool_call": "cyan",
        "llm_call": "magenta",
        "state_transition": "blue",
        "finding_confirmed": "green bold",
        "scope_blocked": "red",
        "error": "red bold",
        "warning": "yellow",
    }

    def __init__(self, enabled: bool = True) -> None:
        """Construct a live console subscriber.

        Args:
            enabled: If False, ``__call__`` becomes a no-op.
        """
        self._console = Console()
        self._enabled = enabled

    async def __call__(self, event: Event) -> None:
        """Render the event to the console.

        Subscribers must be async; this awaits rich's synchronous print
        by simply calling it.

        Args:
            event: The event to render.
        """
        if not self._enabled:
            return
        color = self.COLOR_MAP.get(event.event_type, "white")
        text = Text(event.render_one_line(), style=color)
        self._console.print(text, highlight=False)

    def enable(self) -> None:
        """Re-enable the console after a ``disable()``."""
        self._enabled = True

    def disable(self) -> None:
        """Disable the console. Events will be ignored."""
        self._enabled = False

    @property
    def enabled(self) -> bool:
        """Whether the console is currently rendering events."""
        return self._enabled


_console: LiveConsole | None = None


def get_console() -> LiveConsole:
    """Get the global live console singleton.

    Returns:
        The shared ``LiveConsole`` instance.
    """
    global _console
    if _console is None:
        _console = LiveConsole()
    return _console


def reset_console() -> None:
    """Reset the global console (used in tests)."""
    global _console
    _console = None


__all__ = ["LiveConsole", "get_console", "reset_console"]
