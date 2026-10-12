"""DesktopStateMonitor: one sampler, translating raw signals into context.

Owns the single periodic QTimer for idle sampling (default 5s) and
subscribes to bus events for Doodle interaction + focus-timer state.
The FocusTimer remains the single source of focus state; this monitor
only mirrors its published events into the context store.

Collects nothing but idle seconds (a single number) and interaction
flags. No keystrokes, no screenshots, no window contents, no cursor paths.
"""

from __future__ import annotations

import logging
import time

from PySide6.QtCore import QObject, QTimer

from ..behavior import events as E
from ..persistence.settings import AppSettings
from ..platform.adapter import PlatformAdapter
from .classifier import IdleClassifier
from .model import DoodleInteraction, FocusPhase
from .store import ContextStore

log = logging.getLogger(__name__)

DIRECT_RESET_S = 8.0  # poke/menu/focus-control counts as direct this long


class DesktopStateMonitor(QObject):
    def __init__(
        self,
        bus: E.EventBus,
        store: ContextStore,
        settings: AppSettings,
        adapter: PlatformAdapter,
        idle_provider=None,  # () -> float | None; injectable for tests
        clock=time.monotonic,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._bus = bus
        self._store = store
        self._settings = settings
        self._adapter = adapter
        self._idle_provider = idle_provider or adapter.system_idle_seconds
        self._clock = clock
        self._classifier = IdleClassifier()
        self._sampler = QTimer(self)
        self._sampler.timeout.connect(self.sample)
        self._direct_reset = QTimer(self)
        self._direct_reset.setSingleShot(True)
        self._direct_reset.timeout.connect(
            lambda: self._store.update(interaction=DoodleInteraction.NONE))
        self._started = False
        self.refresh_from_settings()

    # -- lifecycle --------------------------------------------------------------

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        b = self._bus
        b.subscribe(E.DRAG_START, lambda _p: self._note_direct(persistent=True))
        b.subscribe(E.DRAG_END, self._on_drag_end)
        b.subscribe(E.POKE, lambda _p: self._note_direct())
        b.subscribe(E.MENU_OPENED, lambda _p: self._note_direct())
        b.subscribe(E.MENU_CLOSED, lambda _p: self._store.update(
            interaction=DoodleInteraction.NONE))
        b.subscribe(E.FOCUS_STARTED, lambda _p: self._store.update(
            focus=FocusPhase.FOCUSING))
        b.subscribe(E.FOCUS_PAUSED, lambda p: self._store.update(
            focus=FocusPhase.FOCUS_PAUSED if p.get("kind") == "focus"
            else FocusPhase.BREAK_PAUSED))
        b.subscribe(E.FOCUS_RESUMED, lambda p: self._store.update(
            focus=FocusPhase.FOCUSING if p.get("kind") == "focus"
            else FocusPhase.ON_BREAK))
        b.subscribe(E.FOCUS_STOPPED, lambda _p: self._store.update(
            focus=FocusPhase.NONE))
        b.subscribe(E.BREAK_STARTED, lambda _p: self._store.update(
            focus=FocusPhase.ON_BREAK))
        b.subscribe(E.BREAK_COMPLETED, lambda _p: self._store.update(
            focus=FocusPhase.NONE))
        b.subscribe(E.APP_EXITING, lambda _p: self.shutdown())
        self._apply_enabled()

    def shutdown(self) -> None:
        self._sampler.stop()
        self._direct_reset.stop()
        self._started = False

    # -- settings -----------------------------------------------------------------

    def refresh_from_settings(self) -> None:
        s = self._settings
        self._classifier.update_thresholds(s.context_idle_short_s(),
                                           s.context_idle_long_s())
        self._store.update(quiet=s.context_quiet_mode(),
                           idle_detection_enabled=s.context_enabled())
        self._apply_enabled()

    def _apply_enabled(self) -> None:
        if not self._started:
            return
        if self._settings.context_enabled():
            self._sampler.setInterval(int(self._settings.context_sample_s() * 1000))
            self._sampler.start()
            self.sample()  # classify immediately, don't wait one interval
        else:
            self._sampler.stop()
            self._classifier.state = self._classifier.state  # keep thresholds
            from .model import DesktopActivity
            self._store.update(desktop=DesktopActivity.UNKNOWN)

    # -- sampling -------------------------------------------------------------------

    def sample(self) -> None:
        """One idle sample -> classify -> store. Public for tests."""
        if not self._settings.context_enabled():
            return
        try:
            idle_s = self._idle_provider()
        except Exception as exc:  # never let sampling crash the app
            log.warning("Idle provider failed: %s", exc)
            idle_s = None
        desktop = self._classifier.classify(idle_s)
        self._store.update(desktop=desktop)

    # -- interaction ------------------------------------------------------------------

    def _note_direct(self, persistent: bool = False) -> None:
        self._direct_reset.stop()
        self._store.update(interaction=DoodleInteraction.DIRECT)
        if not persistent:
            self._direct_reset.start(int(DIRECT_RESET_S * 1000))

    def _on_drag_end(self, _payload: dict) -> None:
        self._direct_reset.stop()
        self._store.update(interaction=DoodleInteraction.NONE)
