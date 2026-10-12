"""ContextStore: holds the current snapshot, emits transitions only."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

from ..behavior import events as E
from .model import ContextSnapshot

log = logging.getLogger(__name__)

# Fields whose change counts as a meaningful transition (sampled_at excluded).
_TRACKED = ("desktop", "focus", "interaction", "quiet", "idle_detection_enabled")


class ContextStore(QObject):
    """Single source of context. Emits only on meaningful transitions."""

    changed = Signal(object, object)  # (current, previous) snapshots

    def __init__(self, bus: E.EventBus, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._bus = bus
        self._current = ContextSnapshot()
        self._previous = ContextSnapshot()

    @property
    def current(self) -> ContextSnapshot:
        return self._current

    @property
    def previous(self) -> ContextSnapshot:
        return self._previous

    def update(self, **fields) -> bool:
        """Replace tracked fields; returns True when a transition occurred."""
        values = {name: getattr(self._current, name) for name in _TRACKED}
        unknown = set(fields) - set(_TRACKED)
        if unknown:
            raise ValueError(f"Unknown context fields: {sorted(unknown)}")
        values.update(fields)
        new = ContextSnapshot(**values)
        if all(getattr(new, n) == getattr(self._current, n) for n in _TRACKED):
            return False  # no meaningful change: stay silent
        self._previous = self._current
        self._current = new
        log.debug("Context transition: %s -> %s",
                  self._previous.summary(), new.summary())
        self.changed.emit(new, self._previous)
        self._bus.publish(E.CONTEXT_CHANGED, {
            "current": new.summary(),
            "previous": self._previous.summary(),
        })
        return True

    def republish(self) -> None:
        """Re-emit the current snapshot (e.g. for a late subscriber).

        Transition reactions in listeners must be keyed on actual
        current != previous differences, so this is safe: it only
        re-applies policy.
        """
        self.changed.emit(self._current, self._previous)
        self._bus.publish(E.CONTEXT_CHANGED, {
            "current": self._current.summary(),
            "previous": self._previous.summary(),
        })
