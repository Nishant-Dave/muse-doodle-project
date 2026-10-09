"""Lightweight in-process event bus built on Qt signals.

Phase 1 is a single process and needs no external messaging. The bus lets
input handling, the behavior engine, and UI components communicate without
importing each other directly.

Subscriptions are idempotent: subscribing the same (name, slot) twice
replaces the old subscription instead of duplicating it, so repeated
initialization can never multiply event handlers.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, Signal

Payload = dict[str, Any]
Slot = Callable[[Payload], None]


class EventBus(QObject):
    """Tiny publish/subscribe bus: publish(name, payload) -> subscribed slots."""

    event = Signal(str, object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._subscriptions: list[tuple[str, Slot]] = []
        self._connected = False

    def publish(self, name: str, payload: Payload | None = None) -> None:
        self.event.emit(name, payload or {})

    def subscribe(self, name: str, slot: Slot) -> None:
        """Subscribe ``slot(payload)`` to ``name``; idempotent per (name, slot)."""
        self._subscriptions = [
            (n, s) for (n, s) in self._subscriptions if not (n == name and s == slot)
        ]
        self._subscriptions.append((name, slot))
        self._rebuild()

    def unsubscribe(self, name: str, slot: Slot) -> None:
        self._subscriptions = [
            (n, s) for (n, s) in self._subscriptions if not (n == name and s == slot)
        ]
        self._rebuild()

    def clear(self) -> None:
        """Disconnect everything (used at shutdown)."""
        self._subscriptions.clear()
        self._rebuild()

    def _rebuild(self) -> None:
        if self._connected:
            try:
                self.event.disconnect(self._dispatch)
            except (RuntimeError, TypeError):
                pass
            self._connected = False
        if self._subscriptions:
            self.event.connect(self._dispatch)
            self._connected = True

    def _dispatch(self, event_name: str, payload: object) -> None:
        assert isinstance(payload, dict)
        for name, slot in list(self._subscriptions):
            if name == event_name:
                slot(payload)


# Event names (the vocabulary of the behavior loop).
APP_STARTED = "app_started"
APP_EXITING = "app_exiting"
POKE = "poke"                      # a click/tap on the panda
DRAG_START = "drag_start"
DRAG_END = "drag_end"              # payload: {distance_px: float, duration_s: float}
IDLE_TICK = "idle_tick"            # behavior engine's randomized idle timer fired
MOOD_SELECTED = "mood_selected"    # payload: {mood: str}
ANIMATIONS_TOGGLED = "animations_toggled"  # payload: {enabled: bool}
CURSOR_NEAR = "cursor_near"        # payload: {distance_px: float}
CURSOR_AWAY = "cursor_away"        # payload: {}
MOMENTUM_TOGGLED = "momentum_toggled"  # payload: {enabled: bool}
WANDER_TOGGLED = "wander_toggled"      # payload: {enabled: bool}
COME_HERE = "come_here"                # payload: {x: int, y: int} cursor pos
WANDER_NOW = "wander_now"              # payload: {}
CURSOR_DWELL = "cursor_dwell"          # payload: {side: str}
# -- Phase 3: companion features -------------------------------------------------
FOCUS_CONTROL = "focus_control"        # payload: {action: start|pause|resume|stop|skip}
FOCUS_STARTED = "focus_started"        # payload: {kind: focus|break, minutes: int}
FOCUS_PAUSED = "focus_paused"          # payload: {kind: str}
FOCUS_RESUMED = "focus_resumed"        # payload: {kind: str}
FOCUS_STOPPED = "focus_stopped"        # payload: {}
FOCUS_COMPLETED = "focus_completed"    # payload: {kind: focus|break, minutes: int}
BREAK_STARTED = "break_started"        # payload: {minutes: int}
BREAK_COMPLETED = "break_completed"    # payload: {minutes: int}
FOCUS_TICK = "focus_tick"              # payload: {kind: str, remaining_s: int}
REMINDER_CREATED = "reminder_created"  # payload: {id: str, title: str}
REMINDER_DUE = "reminder_due"          # payload: {id: str, title: str, overdue: bool}
REMINDER_DISMISSED = "reminder_dismissed"  # payload: {id: str}
REMINDER_DELETED = "reminder_deleted"  # payload: {id: str}
