"""Context model: the single coherent source for Doodle's adaptive behavior.

Observed signals (idle seconds, drag state, focus-timer events, user
toggles) are kept separate from the classified snapshot the behavior
engine consumes. Nothing here is persisted: the snapshot is transient,
in-memory state rebuilt from live signals and settings.
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field


class DesktopActivity(enum.Enum):
    """Classified desktop state (from system idle time)."""

    ACTIVE = "active"          # recent input
    IDLE_SHORT = "idle_short"  # briefly away
    IDLE_LONG = "idle_long"    # away for a while
    UNKNOWN = "unknown"        # signal unavailable


class FocusPhase(enum.Enum):
    """Focus-timer state. The FocusTimer remains the single source."""

    NONE = "none"
    FOCUSING = "focusing"
    FOCUS_PAUSED = "focus_paused"
    ON_BREAK = "on_break"
    BREAK_PAUSED = "break_paused"


class DoodleInteraction(enum.Enum):
    """Whether the user is directly interacting with Doodle right now."""

    NONE = "none"
    DIRECT = "direct"  # dragging, poking, menu open, using focus controls


@dataclass(frozen=True)
class ContextSnapshot:
    """Point-in-time context. Immutable; the store replaces it wholesale."""

    desktop: DesktopActivity = DesktopActivity.UNKNOWN
    focus: FocusPhase = FocusPhase.NONE
    interaction: DoodleInteraction = DoodleInteraction.NONE
    quiet: bool = False
    idle_detection_enabled: bool = True
    sampled_at: float = field(default_factory=time.monotonic)

    def summary(self) -> dict:
        return {
            "desktop": self.desktop.value,
            "focus": self.focus.value,
            "interaction": self.interaction.value,
            "quiet": self.quiet,
            "idle_detection_enabled": self.idle_detection_enabled,
        }
