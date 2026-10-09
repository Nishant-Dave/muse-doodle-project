"""Mood registration: in-memory session state + a compact popup.

Phase 1 keeps mood in memory only (no history, no analytics). The popup is
a small frameless window that is trivial to dismiss: it closes on selection
(after brief feedback), on focus loss, or with Escape.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

HAPPY = "happy"
OKAY = "okay"
SAD = "sad"
STRESSED = "stressed"

VALID_MOODS = (HAPPY, OKAY, SAD, STRESSED)
MOOD_LABELS = {
    HAPPY: "Happy",
    OKAY: "Okay",
    SAD: "Sad",
    STRESSED: "Stressed",
}
MOOD_EMOJI = {
    HAPPY: "😊",
    OKAY: "😐",
    SAD: "😢",
    STRESSED: "😰",
}


class MoodState:
    """Session-only mood state."""

    def __init__(self) -> None:
        self._current: str | None = None

    @property
    def current(self) -> str | None:
        return self._current

    @property
    def label(self) -> str:
        return MOOD_LABELS.get(self._current, "Not set") if self._current else "Not set"

    def set_mood(self, mood: str) -> bool:
        """Set the mood; returns False for unknown values (state unchanged)."""
        if mood not in VALID_MOODS:
            log.warning("Ignoring unknown mood %r", mood)
            return False
        self._current = mood
        return True

    def clear(self) -> None:
        self._current = None
