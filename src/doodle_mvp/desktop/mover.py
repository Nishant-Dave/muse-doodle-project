"""Mover: smooth, eased window movement for glides and wanders.

Single short-lived 60fps QTimer, elapsed-time-based (QElapsedTimer) so
motion doesn't depend on frame-timing jitter. Supports:

- glide_to(target, duration_ms): ease-out cubic, used after drag release.
- wander_to(target, duration_ms): ease-in-out, used for autonomous strolls.

Only one movement runs at a time; starting a new one replaces the old.
cancel() stops immediately. The move callback clamps to the screen, so the
panda can never be flung off-screen. arrived(kind) fires on completion.
"""

from __future__ import annotations

import logging
from typing import Callable

from PySide6.QtCore import QElapsedTimer, QObject, QPoint, QTimer, Signal

log = logging.getLogger(__name__)

TICK_MS = 16


def ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def ease_in_out_quad(t: float) -> float:
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        return 2.0 * t * t
    return 1.0 - (-2.0 * t + 2.0) ** 2 / 2.0


def ease_in_quad(t: float) -> float:
    """Accelerating ease (gravity feel): slow start, fast finish."""
    t = max(0.0, min(1.0, t))
    return t * t


class Mover(QObject):
    arrived = Signal(str)  # kind: "glide" | "wander" | "fall" | "cancelled"

    def __init__(
        self,
        get_pos: Callable[[], QPoint],
        move_to: Callable[[QPoint], None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._get_pos = get_pos
        self._move_to = move_to
        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._tick)
        self._clock = QElapsedTimer()
        self._active = False
        self._kind = ""
        self._start = QPoint()
        self._target = QPoint()
        self._duration_ms = 0
        self._ease = ease_out_cubic

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def kind(self) -> str:
        return self._kind

    def glide_to(self, target: QPoint, duration_ms: int = 350) -> None:
        self._begin("glide", target, duration_ms, ease_out_cubic)

    def wander_to(self, target: QPoint, duration_ms: int = 1200) -> None:
        self._begin("wander", target, duration_ms, ease_in_out_quad)

    def fall_to(self, target: QPoint, duration_ms: int = 650) -> None:
        """Accelerating drop (gravity feel); the move callback clamps to
        the screen so the target may be far below the visible area."""
        self._begin("fall", target, duration_ms, ease_in_quad)

    def cancel(self) -> None:
        if not self._active:
            return
        self._stop()
        self.arrived.emit("cancelled")

    def shutdown(self) -> None:
        self._timer.stop()
        self._active = False

    # -- internals ------------------------------------------------------------

    def _begin(self, kind: str, target: QPoint, duration_ms: int, ease) -> None:
        self._timer.stop()
        self._active = True
        self._kind = kind
        self._ease = ease
        try:
            self._start = self._get_pos()
        except Exception as exc:
            log.warning("Could not read position: %s", exc)
            self._active = False
            return
        self._target = target
        self._duration_ms = max(1, duration_ms)
        self._clock.start()
        self._timer.start()

    def _tick(self) -> None:
        if not self._active:
            return
        elapsed = self._clock.elapsed()
        t = min(1.0, elapsed / self._duration_ms)
        e = self._ease(t)
        dx = self._target.x() - self._start.x()
        dy = self._target.y() - self._start.y()
        pos = QPoint(
            int(self._start.x() + dx * e),
            int(self._start.y() + dy * e),
        )
        try:
            self._move_to(pos)
        except Exception as exc:  # never let movement break the app
            log.warning("Move failed: %s", exc)
            self._stop()
            return
        if t >= 1.0:
            kind = self._kind
            self._stop()
            self.arrived.emit(kind)

    def _stop(self) -> None:
        self._timer.stop()
        self._active = False
