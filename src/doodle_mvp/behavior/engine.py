"""Behavior engine: EVENT -> STATE/CONTEXT -> DECISION -> ACTION -> ANIMATION.

A small, explicit, rule-based state model (no AI in Phase 1):

States: IDLE, DRAGGING, REACTING (a one-shot animation is playing).

Priority rules (higher wins, deterministic and testable):
- Dragging (100) preempts everything; nothing interrupts a drag.
- Poke / mood reactions (60) run only when not dragging; a poke is
  ignored while another reaction is playing (no stacked timers).
- Idle personality (10) runs only when fully idle.

The engine never touches widgets directly: it emits ``play_requested`` /
``static_requested`` signals, which the application wires to the
AnimationPlayer. Idle timing uses one single-shot QTimer with randomized
intervals (injectable RNG for deterministic tests).
"""

from __future__ import annotations

import logging
import random

from PySide6.QtCore import QObject, QTimer, Signal

from . import events as E

log = logging.getLogger(__name__)

IDLE = "idle"
DRAGGING = "dragging"
REACTING = "reacting"

MOOD_ANIMATIONS = {
    "happy": "happy",
    "okay": "blink",
    "sad": "sad",
    "stressed": "stressed",
}

IDLE_MIN_S = 4.0
IDLE_MAX_S = 9.0
DIZZY_DISTANCE_PX = 120.0
DIZZY_DURATION_S = 1.5


class BehaviorEngine(QObject):
    play_requested = Signal(str, bool)   # (animation_name, loop)
    static_requested = Signal(str)       # show first frame of animation, no timer

    def __init__(
        self,
        bus: E.EventBus,
        rng: random.Random | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._bus = bus
        self._rng = rng or random.Random()
        self._state = IDLE
        self._enabled = True
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._on_idle_timeout)
        self._started = False

    # -- lifecycle ------------------------------------------------------------

    @property
    def state(self) -> str:
        return self._state

    @property
    def bus(self) -> E.EventBus:
        return self._bus

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        bus = self._bus
        bus.subscribe(E.POKE, lambda _p: self.handle_poke())
        bus.subscribe(E.DRAG_START, lambda _p: self.handle_drag_start())
        bus.subscribe(E.DRAG_END, self.handle_drag_end)
        bus.subscribe(E.IDLE_TICK, lambda _p: self.handle_idle_tick())
        bus.subscribe(E.MOOD_SELECTED, self.handle_mood)
        bus.subscribe(E.ANIMATIONS_TOGGLED, self.handle_animations_toggled)
        bus.subscribe(E.APP_EXITING, lambda _p: self.shutdown())
        self.play_requested.emit("idle", True)
        self._schedule_idle()

    def shutdown(self) -> None:
        self._idle_timer.stop()
        self._started = False

    # -- event handlers (public for deterministic tests) -----------------------

    def handle_poke(self) -> None:
        if not self._enabled:
            return
        if self._state != IDLE:
            log.debug("Poke ignored while %s", self._state)
            return
        self._state = REACTING
        self._idle_timer.stop()
        self.play_requested.emit("playful", False)

    def handle_drag_start(self) -> None:
        if not self._enabled:
            return
        self._state = DRAGGING
        self._idle_timer.stop()
        self.play_requested.emit("drag", True)

    def handle_drag_end(self, payload: dict) -> None:
        if self._state != DRAGGING:
            return
        distance = float(payload.get("distance_px", 0.0))
        duration = float(payload.get("duration_s", 0.0))
        if distance >= DIZZY_DISTANCE_PX or duration >= DIZZY_DURATION_S:
            self._state = REACTING
            self.play_requested.emit("dizzy", False)
        else:
            self._to_idle()

    def handle_idle_tick(self) -> None:
        if not self._enabled or self._state != IDLE:
            return
        self._state = REACTING
        roll = self._rng.random()
        if roll < 0.15:
            choice = "yawn"
        elif roll < 0.30:
            choice = "curious"
        else:
            choice = "blink"
        self.play_requested.emit(choice, False)

    def handle_mood(self, payload: dict) -> None:
        if not self._enabled:
            return
        mood = str(payload.get("mood", ""))
        animation = MOOD_ANIMATIONS.get(mood)
        if animation is None:
            log.warning("Unknown mood %r; ignoring", mood)
            return
        if self._state == DRAGGING:
            log.debug("Mood ignored during drag")
            return
        self._state = REACTING
        self._idle_timer.stop()
        self.play_requested.emit(animation, False)

    def handle_animations_toggled(self, payload: dict) -> None:
        self.set_animations_enabled(bool(payload.get("enabled", True)))

    def set_animations_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self._idle_timer.stop()
        if not enabled:
            self._state = IDLE
            self.static_requested.emit("idle")
        else:
            self._to_idle()

    def on_animation_finished(self, name: str) -> None:
        """Called when the player's one-shot animation completes."""
        if self._state == REACTING:
            self._to_idle()
        log.debug("Animation finished: %s (state=%s)", name, self._state)

    # -- internals --------------------------------------------------------------

    def _to_idle(self) -> None:
        self._state = IDLE
        if self._enabled:
            self.play_requested.emit("idle", True)
            self._schedule_idle()
        else:
            self.static_requested.emit("idle")

    def _schedule_idle(self) -> None:
        if not self._enabled:
            return
        delay_ms = int(self._rng.uniform(IDLE_MIN_S, IDLE_MAX_S) * 1000)
        self._idle_timer.start(delay_ms)

    def _on_idle_timeout(self) -> None:
        self._bus.publish(E.IDLE_TICK)
