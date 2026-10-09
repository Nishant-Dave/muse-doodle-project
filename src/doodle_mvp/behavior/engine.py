"""BehaviorEngine: EVENT -> STATE/CONTEXT -> DECISION -> ACTION -> ANIMATION.

Extended in Phase 2B with a unified behavior coordinator. Explicit states
and priorities (higher wins, deterministic, testable):

    DRAGGING (100): active drag or direct manipulation. Preempts everything.
    REACTING (60):  one-shot reactions: poke/playful, mood, cursor-curious,
                    dizzy recovery.
    MOVING   (40):  glide after release, autonomous wander.
    IDLE     (10):  scheduler-driven personality or calm inactivity.

The engine never touches widgets: it emits play_requested / static_requested
/ facing_changed signals, wired by the application to the player/character.
One single-shot QTimer drives the personality schedule; the Mover owns its
own short-lived timer for motion. Idle timing uses injectable RNG/clock.
"""

from __future__ import annotations

import logging
import random
import time

from PySide6.QtCore import QObject, QPoint, QTimer, Signal

from . import events as E
from .scheduler import PersonalityScheduler

log = logging.getLogger(__name__)

IDLE = "idle"
DRAGGING = "dragging"
REACTING = "reacting"
MOVING = "moving"

MOOD_VARIANTS: dict[str, list[tuple[str, float]]] = {
    "happy": [("happy", 0.9), ("playful", 0.1)],
    "okay": [("blink", 1.0)],
    "sad": [("sad", 1.0)],
    "stressed": [("stressed", 0.75), ("yawn", 0.25)],
}

DIZZY_DISTANCE_PX = 120.0
DIZZY_DURATION_S = 1.5
GLIDE_MIN_SPEED_PX_S = 120.0
GLIDE_MAX_DIST_PX = 140.0
GLIDE_TIME_FACTOR = 0.22
WANDER_MIN_DIST_PX = 60.0
WANDER_MAX_DIST_PX = 180.0

SCHEDULE_MIN_S = 4.0
SCHEDULE_MAX_S = 9.0
SCHEDULE_IDLE_MIN_S = 8.0
SCHEDULE_IDLE_MAX_S = 16.0


class BehaviorEngine(QObject):
    play_requested = Signal(str, bool)   # (animation_name, loop)
    static_requested = Signal(str)       # show first frame, no timer
    facing_changed = Signal(str)         # "left" | "right"

    def __init__(
        self,
        bus: E.EventBus,
        rng: random.Random | None = None,
        scheduler: PersonalityScheduler | None = None,
        mover=None,
        monitor=None,
        get_pos=None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._bus = bus
        self._rng = rng or random.Random()
        self._scheduler = scheduler or PersonalityScheduler(rng=self._rng)
        self._mover = mover
        self._monitor = monitor
        self._get_pos = get_pos
        self._state = IDLE
        self._enabled = True
        self._momentum_enabled = True
        self._wander_enabled = True
        self._last_played: tuple[str, bool] | None = None
        self._schedule_timer = QTimer(self)
        self._schedule_timer.setSingleShot(True)
        self._schedule_timer.timeout.connect(self._on_schedule_timeout)
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
        bus.subscribe(E.MOOD_SELECTED, self.handle_mood)
        bus.subscribe(E.CURSOR_NEAR, self.handle_cursor_near)
        bus.subscribe(E.ANIMATIONS_TOGGLED, self.handle_animations_toggled)
        bus.subscribe(E.MOMENTUM_TOGGLED, self.handle_momentum_toggled)
        bus.subscribe(E.WANDER_TOGGLED, self.handle_wander_toggled)
        bus.subscribe(E.APP_EXITING, lambda _p: self.shutdown())
        if self._mover is not None:
            self._mover.arrived.connect(self.on_move_arrived)
        if self._monitor is not None:
            self._monitor.start()
        self._play("idle", True)
        self._schedule_next()

    def shutdown(self) -> None:
        self._schedule_timer.stop()
        if self._mover is not None:
            self._mover.shutdown()
        if self._monitor is not None:
            self._monitor.shutdown()
        self._started = False

    # -- event handlers (public for deterministic tests) -----------------------

    def handle_poke(self) -> None:
        if not self._enabled:
            return
        if self._state == DRAGGING or self._state == REACTING:
            log.debug("Poke ignored while %s", self._state)
            return
        self._cancel_movement()
        self._react("playful")

    def handle_drag_start(self) -> None:
        if not self._enabled:
            return
        self._cancel_movement()
        self._state = DRAGGING
        self._schedule_timer.stop()
        self._play("drag", True)

    def handle_drag_end(self, payload: dict) -> None:
        if self._state != DRAGGING:
            return
        distance = float(payload.get("distance_px", 0.0))
        duration = float(payload.get("duration_s", 0.0))
        if distance >= DIZZY_DISTANCE_PX or duration >= DIZZY_DURATION_S:
            self._react("dizzy")
            return
        if self._momentum_enabled and self._mover is not None and self._get_pos is not None:
            vx = float(payload.get("velocity_x", 0.0))
            vy = float(payload.get("velocity_y", 0.0))
            speed = (vx * vx + vy * vy) ** 0.5
            if speed >= GLIDE_MIN_SPEED_PX_S:
                self._start_glide(vx, vy, speed)
                return
        self._to_idle()

    def handle_cursor_near(self, payload: dict) -> None:
        if not self._enabled or self._state != IDLE:
            return
        self._react("curious")

    def handle_mood(self, payload: dict) -> None:
        if not self._enabled:
            return
        mood = str(payload.get("mood", ""))
        variants = MOOD_VARIANTS.get(mood)
        if not variants:
            log.warning("Unknown mood %r; ignoring", mood)
            return
        if self._state == DRAGGING:
            log.debug("Mood ignored during drag")
            return
        self._cancel_movement()
        animation = self._weighted_pick(variants)
        self._react(animation)

    def handle_animations_toggled(self, payload: dict) -> None:
        self.set_animations_enabled(bool(payload.get("enabled", True)))

    def handle_momentum_toggled(self, payload: dict) -> None:
        self._momentum_enabled = bool(payload.get("enabled", True))

    def handle_wander_toggled(self, payload: dict) -> None:
        self._wander_enabled = bool(payload.get("enabled", True))

    def set_animations_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self._schedule_timer.stop()
        self._cancel_movement()
        if self._monitor is not None:
            if enabled:
                self._monitor.start()
            else:
                self._monitor.shutdown()
        if not enabled:
            self._state = IDLE
            self._emit_static("idle")
        else:
            self._to_idle()

    def on_animation_finished(self, name: str) -> None:
        """Called when the player's one-shot animation completes."""
        if self._state == REACTING:
            self._to_idle()
        log.debug("Animation finished: %s (state=%s)", name, self._state)

    def on_move_arrived(self, kind: str) -> None:
        """Called by the Mover when a glide/wander completes or is cancelled."""
        if kind == "cancelled":
            return  # something else took over; it owns the state now
        if self._state == MOVING:
            self._to_idle()

    # -- personality schedule ----------------------------------------------------

    def _on_schedule_timeout(self) -> None:
        if not self._enabled or self._state != IDLE:
            return
        activity = self._scheduler.pick()
        if activity is None:
            # Calm inactivity: do nothing, check again later.
            self._schedule_next(SCHEDULE_IDLE_MIN_S, SCHEDULE_IDLE_MAX_S)
            return
        if activity == "wander":
            if not self._start_wander():
                self._schedule_next()
            return
        self._react(activity)

    # -- internals ------------------------------------------------------------------

    def _react(self, animation: str) -> None:
        """Play a one-shot reaction, returning to idle afterwards."""
        self._state = REACTING
        self._schedule_timer.stop()
        self._scheduler.record(animation)
        self._play(animation, False)

    def _play(self, name: str, loop: bool) -> None:
        # Never restart the same animation back-to-back.
        if self._last_played == (name, loop):
            return
        self._last_played = (name, loop)
        self.play_requested.emit(name, loop)

    def _emit_static(self, name: str) -> None:
        self._last_played = None
        self.static_requested.emit(name)

    def _to_idle(self) -> None:
        self._state = IDLE
        if self._enabled:
            self._play("idle", True)
            self._schedule_next()
        else:
            self._emit_static("idle")

    def _schedule_next(self, lo: float = SCHEDULE_MIN_S, hi: float = SCHEDULE_MAX_S) -> None:
        if not self._enabled:
            return
        delay_ms = int(self._rng.uniform(lo, hi) * 1000)
        self._schedule_timer.start(delay_ms)

    def _cancel_movement(self) -> None:
        if self._mover is not None and self._mover.is_active:
            self._mover.cancel()

    def _start_glide(self, vx: float, vy: float, speed: float) -> None:
        pos = self._get_pos()
        dist = min(GLIDE_MAX_DIST_PX, speed * GLIDE_TIME_FACTOR)
        nx, ny = vx / speed, vy / speed
        target = QPoint(int(pos.x() + nx * dist), int(pos.y() + ny * dist))
        self._state = MOVING
        self._schedule_timer.stop()
        self.facing_changed.emit("left" if nx < 0 else "right")
        self._play("idle", True)  # settle back to the calm pose for the glide
        self._mover.glide_to(target, duration_ms=350)

    def _start_wander(self) -> bool:
        if (
            not self._wander_enabled
            or self._mover is None
            or self._get_pos is None
        ):
            return False
        pos = self._get_pos()
        for _ in range(8):  # a few tries to find a non-trivial target
            dx = self._rng.uniform(-WANDER_MAX_DIST_PX, WANDER_MAX_DIST_PX)
            dy = self._rng.uniform(-WANDER_MAX_DIST_PX, WANDER_MAX_DIST_PX)
            if abs(dx) + abs(dy) >= WANDER_MIN_DIST_PX:
                break
        else:
            return False
        target = QPoint(int(pos.x() + dx), int(pos.y() + dy))
        self._state = MOVING
        self._schedule_timer.stop()
        self._scheduler.record("wander")
        self.facing_changed.emit("left" if dx < 0 else "right")
        self._play("idle", True)  # already idle; guard prevents restart
        self._mover.wander_to(target, duration_ms=1200)
        return True

    def _weighted_pick(self, variants: list[tuple[str, float]]) -> str:
        total = sum(w for _, w in variants)
        roll = self._rng.random() * total
        for name, weight in variants:
            roll -= weight
            if roll <= 0:
                return name
        return variants[-1][0]
