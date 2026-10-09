"""FocusTimer: Pomodoro-style focus/break sessions with a monotonic clock.

States: IDLE -> FOCUS <-> PAUSED -> BREAK <-> PAUSED -> IDLE.
A running session is deliberately *not* resumed after an app restart
(documented behavior): shutdown discards it, config and history persist.

Timing uses time.monotonic() deadlines, so accuracy never depends on GUI
tick frequency. A 1s QTimer drives UI updates; tests drive poll() directly
with a fake clock.

Publishes FOCUS_STARTED/PAUSED/RESUMED/STOPPED/COMPLETED, BREAK_STARTED/
COMPLETED, and FOCUS_TICK {kind, remaining_s} on the event bus.
"""

from __future__ import annotations

import datetime
import logging
import time

from PySide6.QtCore import QObject, QTimer

from ..behavior import events as E
from ..persistence.settings import AppSettings
from .storage import data_dir, read_json, write_json

log = logging.getLogger(__name__)

IDLE = "idle"
FOCUS = "focus"
BREAK = "break"
PAUSED = "paused"

HISTORY_FILE = "focus_history.json"
TICK_MS = 1000


class FocusTimer(QObject):
    def __init__(
        self,
        bus: E.EventBus,
        settings: AppSettings,
        history_path=None,
        clock=time.monotonic,
        tick_ms: int = TICK_MS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._bus = bus
        self._settings = settings
        self._history_path = history_path or (data_dir() / HISTORY_FILE)
        self._clock = clock
        self._state = IDLE
        self._kind = FOCUS          # kind of the active (or paused) session
        self._paused_kind = FOCUS
        self._deadline = 0.0
        self._remaining = 0.0
        self._session_minutes = 0
        self._completed_focus_sessions = 0  # this run, for long-break cadence
        self._timer = QTimer(self)
        self._timer.setInterval(tick_ms)
        self._timer.timeout.connect(self.poll)
        self._started = False

    # -- lifecycle ------------------------------------------------------------

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._bus.subscribe(E.FOCUS_CONTROL, self._on_control)
        self._bus.subscribe(E.APP_EXITING, lambda _p: self.shutdown())

    def shutdown(self) -> None:
        self._timer.stop()
        self._started = False
        # A running session is discarded on shutdown (documented).
        self._state = IDLE

    # -- state ------------------------------------------------------------------

    @property
    def state(self) -> str:
        return self._state

    @property
    def active_kind(self) -> str:
        return self._kind if self._state != IDLE else IDLE

    @property
    def remaining_s(self) -> int:
        if self._state == PAUSED:
            return max(0, int(self._remaining))
        if self._state in (FOCUS, BREAK):
            return max(0, int(self._deadline - self._clock()))
        return 0

    @property
    def is_active(self) -> bool:
        return self._state in (FOCUS, BREAK, PAUSED)

    # -- controls -------------------------------------------------------------------

    def start_focus(self) -> bool:
        if self._state != IDLE:
            return False
        self._begin(FOCUS, self._settings.focus_minutes())
        return True

    def pause(self) -> bool:
        if self._state not in (FOCUS, BREAK):
            return False
        self._remaining = self._deadline - self._clock()
        self._paused_kind = self._kind
        self._state = PAUSED
        self._timer.stop()
        self._bus.publish(E.FOCUS_PAUSED, {"kind": self._paused_kind})
        return True

    def resume(self) -> bool:
        if self._state != PAUSED:
            return False
        self._kind = self._paused_kind
        self._deadline = self._clock() + max(0.0, self._remaining)
        self._state = self._kind
        self._timer.start()
        self._bus.publish(E.FOCUS_RESUMED, {"kind": self._kind})
        return True

    def stop(self) -> bool:
        if not self.is_active:
            return False
        self._timer.stop()
        self._state = IDLE
        self._bus.publish(E.FOCUS_STOPPED, {})
        return True

    def skip(self) -> bool:
        """Finish the current session immediately (counts a focus session)."""
        if self._state not in (FOCUS, BREAK, PAUSED):
            return False
        kind = self._paused_kind if self._state == PAUSED else self._kind
        minutes = self._session_minutes
        self._timer.stop()
        self._state = IDLE
        self._complete(kind, minutes)
        return True

    def poll(self) -> None:
        """Timer tick; public so tests can drive it with a fake clock."""
        if self._state not in (FOCUS, BREAK):
            return
        remaining = self._deadline - self._clock()
        if remaining <= 0:
            kind, minutes = self._kind, self._session_minutes
            self._timer.stop()
            self._state = IDLE
            self._complete(kind, minutes)
        else:
            self._bus.publish(
                E.FOCUS_TICK, {"kind": self._kind, "remaining_s": int(remaining)}
            )

    # -- history ----------------------------------------------------------------------

    def record_completed(self, kind: str, minutes: int) -> None:
        if kind != FOCUS:
            return
        history = read_json(self._history_path, [])
        if not isinstance(history, list):
            history = []
        history.append(
            {
                "start": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "minutes": minutes,
                "kind": kind,
            }
        )
        write_json(self._history_path, history[-500:])  # cap growth

    def today_summary(self) -> tuple[int, int]:
        """(completed focus sessions today, total minutes) local time."""
        history = read_json(self._history_path, [])
        if not isinstance(history, list):
            return (0, 0)
        today = datetime.date.today().isoformat()
        count = minutes = 0
        for entry in history:
            try:
                if not isinstance(entry, dict):
                    continue
                ts = datetime.datetime.fromisoformat(entry["start"])
                if ts.date().isoformat() == today and entry.get("kind") == FOCUS:
                    count += 1
                    minutes += int(entry.get("minutes", 0))
            except (KeyError, ValueError, TypeError):
                continue
        return (count, minutes)

    # -- internals ----------------------------------------------------------------------

    def _on_control(self, payload: dict) -> None:
        action = str(payload.get("action", ""))
        if action == "start":
            self.start_focus()
        elif action == "pause":
            self.pause()
        elif action == "resume":
            self.resume()
        elif action == "stop":
            self.stop()
        elif action == "skip":
            self.skip()

    def _begin(self, kind: str, minutes: int) -> None:
        self._kind = kind
        self._paused_kind = kind
        self._session_minutes = minutes
        self._deadline = self._clock() + minutes * 60.0
        self._state = kind
        self._timer.start()
        if kind == FOCUS:
            self._bus.publish(E.FOCUS_STARTED, {"kind": kind, "minutes": minutes})
        else:
            self._bus.publish(E.BREAK_STARTED, {"minutes": minutes})

    def _complete(self, kind: str, minutes: int) -> None:
        if kind == FOCUS:
            self.record_completed(kind, minutes)
            self._completed_focus_sessions += 1
            self._bus.publish(E.FOCUS_COMPLETED, {"kind": kind, "minutes": minutes})
            # Auto-transition into the appropriate break.
            if self._completed_focus_sessions % self._settings.sessions_before_long_break() == 0:
                self._begin(BREAK, self._settings.long_break_minutes())
            else:
                self._begin(BREAK, self._settings.break_minutes())
        else:
            self._bus.publish(E.BREAK_COMPLETED, {"minutes": minutes})
