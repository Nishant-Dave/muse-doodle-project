"""CursorMonitor: edge-triggered cursor proximity detection.

Polls the cursor position on a lightweight timer (default 150ms) and
publishes CURSOR_NEAR once when the cursor enters the radius, and
CURSOR_AWAY once when it leaves the (larger) exit radius. Hysteresis plus
a per-enter cooldown guarantee the panda never flickers or re-triggers
while the cursor jitters around the threshold or sits still nearby.

Only cursor *position* is read. No keystrokes, screenshots, or content.
Position provider and clock are injectable for deterministic tests.
"""

from __future__ import annotations

import logging
import time
from typing import Callable

from PySide6.QtCore import QObject, QPoint, QTimer

from ..behavior import events as E

log = logging.getLogger(__name__)


class CursorMonitor(QObject):
    def __init__(
        self,
        bus: E.EventBus,
        anchor: Callable[[], QPoint],
        radius_px: float = 150.0,
        exit_radius_px: float = 200.0,
        cooldown_s: float = 20.0,
        dwell_s: float = 2.5,
        interval_ms: int = 150,
        pos_provider: Callable[[], QPoint] | None = None,
        clock=time.monotonic,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._bus = bus
        self._anchor = anchor
        self._radius = radius_px
        self._exit_radius = max(exit_radius_px, radius_px + 10.0)
        self._cooldown = cooldown_s
        self._dwell_s = dwell_s
        self._clock = clock
        self._pos_provider = pos_provider
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self.poll)
        self._inside = False
        self._last_enter = float("-inf")
        self._inside_since = 0.0
        self._dwelled = False
        self._last_pos: QPoint | None = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._timer.start()

    def shutdown(self) -> None:
        self._running = False
        self._timer.stop()
        self._inside = False
        self._dwelled = False

    @property
    def is_running(self) -> bool:
        return self._timer.isActive()

    def set_radius(self, radius_px: float) -> None:
        self._radius = radius_px
        self._exit_radius = max(self._exit_radius, radius_px + 10.0)

    @property
    def last_pos(self) -> QPoint | None:
        """Most recently polled cursor position (None before first poll)."""
        return self._last_pos

    def poll(self) -> None:
        """Single proximity check; also called directly by tests."""
        try:
            pos = self._pos_provider() if self._pos_provider else self._qt_cursor_pos()
            anchor = self._anchor()
        except Exception as exc:  # never let polling break the app
            log.debug("Cursor poll failed: %s", exc)
            return
        self._last_pos = pos
        dx = pos.x() - anchor.x()
        dy = pos.y() - anchor.y()
        distance = (dx * dx + dy * dy) ** 0.5
        now = self._clock()
        side = "left" if pos.x() < anchor.x() else "right"
        if not self._inside and distance <= self._radius:
            self._inside = True
            self._inside_since = now
            self._dwelled = False
            if now - self._last_enter >= self._cooldown:
                self._last_enter = now
                self._bus.publish(
                    E.CURSOR_NEAR, {"distance_px": distance, "side": side}
                )
        elif self._inside and distance > self._exit_radius:
            self._inside = False
            self._dwelled = False
            self._bus.publish(E.CURSOR_AWAY, {})
        elif self._inside and not self._dwelled:
            # Cursor lingers: the panda turns to face it (Shimeji's
            # "sit and face mouse", single-shot, no tracking).
            if now - self._inside_since >= self._dwell_s:
                self._dwelled = True
                self._bus.publish(E.CURSOR_DWELL, {"side": side})

    @staticmethod
    def _qt_cursor_pos() -> QPoint:
        from PySide6.QtGui import QCursor

        return QCursor.pos()
