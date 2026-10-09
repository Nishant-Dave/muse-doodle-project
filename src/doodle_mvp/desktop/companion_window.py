"""CompanionWindow: the floating, frameless panda window.

Responsibilities (and nothing else):
- present the panda with a transparent background, always on top
- drag handling with a stable pointer-to-window offset
- click vs. drag disambiguation, click -> POKE event
- right-click context menu (mood, animations toggle, quit)
- double-click opens the mood popup
- persist position on drag end

All behavior decisions live in the BehaviorEngine; this window only
translates raw mouse input into bus events.
"""

from __future__ import annotations

import logging
import time
from collections import deque

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QAction, QMouseEvent
from PySide6.QtWidgets import QMenu, QWidget

from ..behavior import events as E
from ..character.character import PandaCharacter
from ..persistence.settings import AppSettings
from ..platform.adapter import PlatformAdapter
from . import positioning

log = logging.getLogger(__name__)

CLICK_MAX_DISTANCE_PX = 6
CLICK_MAX_DURATION_S = 0.6
VELOCITY_SAMPLES = 6
MIN_VELOCITY_DT_S = 0.02


class CompanionWindow(QWidget):
    request_mood_popup = Signal()
    request_quit = Signal()
    request_focus_panel = Signal()
    request_reminder_dialog = Signal()
    request_reminder_list = Signal()
    request_scratchpad = Signal()

    def __init__(
        self,
        bus: E.EventBus,
        character: PandaCharacter,
        settings: AppSettings,
        adapter: PlatformAdapter,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._bus = bus
        self._settings = settings
        self._character = character
        self._character.setParent(self)

        adapter.configure_companion_window(self)
        self.setMouseTracking(False)

        self._press_global: QPoint | None = None
        self._press_window: QPoint | None = None
        self._press_time = 0.0
        self._dragging = False
        self._drag_start_emitted = False
        self._max_distance = 0.0
        self._samples: deque[tuple[QPoint, float]] = deque(maxlen=VELOCITY_SAMPLES)

        self._animations_enabled = settings.animations_enabled()
        self._momentum_enabled = settings.momentum_enabled()
        self._wander_enabled = settings.wander_enabled()
        self._focus_state_provider = None  # () -> (state, kind); set by app

    # -- public ---------------------------------------------------------------

    def restore_or_default_position(self) -> None:
        saved = self._settings.get_position()
        if saved is not None:
            self.move(positioning.clamp_to_screen(self, saved))
        else:
            self.move(positioning.clamp_to_screen(self, positioning.default_position(self)))

    def set_animations_enabled(self, enabled: bool) -> None:
        self._animations_enabled = enabled

    def set_momentum_enabled(self, enabled: bool) -> None:
        self._momentum_enabled = enabled

    def set_wander_enabled(self, enabled: bool) -> None:
        self._wander_enabled = enabled

    def set_focus_state_provider(self, provider) -> None:
        """Provider returning (state, kind) for contextual focus menu items."""
        self._focus_state_provider = provider

    def center(self) -> QPoint:
        """Global position of the panda's center (cursor-proximity anchor)."""
        return self.mapToGlobal(self.rect().center())

    def release_velocity(self) -> tuple[float, float]:
        """Pointer velocity in px/s from recent drag samples."""
        if len(self._samples) < 2:
            return (0.0, 0.0)
        (p0, t0), (p1, t1) = self._samples[0], self._samples[-1]
        dt = t1 - t0
        if dt < MIN_VELOCITY_DT_S:
            return (0.0, 0.0)
        return ((p1.x() - p0.x()) / dt, (p1.y() - p0.y()) / dt)

    # -- mouse input ------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_global = event.globalPosition().toPoint()
            self._press_window = self.pos()
            self._press_time = time.monotonic()
            self._dragging = False
            self._drag_start_emitted = False
            self._max_distance = 0.0
            self._samples.clear()
            self._samples.append((self._press_global, self._press_time))
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._press_global is None:
            return
        current = event.globalPosition().toPoint()
        delta = current - self._press_global
        dist = (delta.x() ** 2 + delta.y() ** 2) ** 0.5
        self._max_distance = max(self._max_distance, dist)
        if not self._dragging and dist > CLICK_MAX_DISTANCE_PX:
            self._dragging = True
        if self._dragging:
            if not self._drag_start_emitted:
                self._drag_start_emitted = True
                self._bus.publish(E.DRAG_START)
            self._samples.append((current, time.monotonic()))
            assert self._press_window is not None
            new_pos = positioning.clamp_to_screen(self, self._press_window + delta)
            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or self._press_global is None:
            return
        duration = time.monotonic() - self._press_time
        was_drag = self._dragging
        vx, vy = self.release_velocity()
        self._press_global = None
        self._dragging = False
        self._samples.clear()
        if was_drag:
            self._settings.set_position(self.pos())
            self._bus.publish(
                E.DRAG_END,
                {
                    "distance_px": self._max_distance,
                    "duration_s": duration,
                    "velocity_x": vx,
                    "velocity_y": vy,
                },
            )
        elif duration <= CLICK_MAX_DURATION_S:
            self._bus.publish(E.POKE)
        event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.request_mood_popup.emit()
            event.accept()

    # -- context menu -------------------------------------------------------------

    def _show_context_menu(self, global_pos: QPoint) -> None:
        menu = QMenu(self)
        menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        mood_action = QAction("How are you feeling?…", menu)
        mood_action.triggered.connect(self.request_mood_popup.emit)
        menu.addAction(mood_action)

        menu.addSeparator()
        self._add_focus_items(menu)
        menu.addSeparator()
        self._add_companion_items(menu)
        menu.addSeparator()

        anim_action = QAction("Animations", menu)
        anim_action.setCheckable(True)
        anim_action.setChecked(self._animations_enabled)
        anim_action.triggered.connect(
            lambda checked: self._bus.publish(E.ANIMATIONS_TOGGLED, {"enabled": checked})
        )
        menu.addAction(anim_action)

        glide_action = QAction("Glide after drag", menu)
        glide_action.setCheckable(True)
        glide_action.setChecked(self._momentum_enabled)
        glide_action.setToolTip("Gentle momentum glide when releasing a fast drag")
        glide_action.triggered.connect(
            lambda checked: self._bus.publish(E.MOMENTUM_TOGGLED, {"enabled": checked})
        )
        menu.addAction(glide_action)

        wander_action = QAction("Wander around", menu)
        wander_action.setCheckable(True)
        wander_action.setChecked(self._wander_enabled)
        wander_action.setToolTip("Occasionally stroll to a nearby spot on its own")
        wander_action.triggered.connect(
            lambda checked: self._bus.publish(E.WANDER_TOGGLED, {"enabled": checked})
        )
        menu.addAction(wander_action)

        menu.addSeparator()
        come_action = QAction("Come here", menu)
        come_action.setToolTip("Walk over to the cursor")
        come_action.triggered.connect(self._on_come_here)
        menu.addAction(come_action)

        walk_action = QAction("Take a walk", menu)
        walk_action.setToolTip("Wander to a nearby spot right now")
        walk_action.triggered.connect(lambda: self._bus.publish(E.WANDER_NOW, {}))
        menu.addAction(walk_action)

        menu.addSeparator()
        quit_action = QAction("Quit Doodle", menu)
        quit_action.triggered.connect(self.request_quit.emit)
        menu.addAction(quit_action)

        menu.popup(global_pos)

    def _add_focus_items(self, menu: QMenu) -> None:
        """Contextual focus controls based on the timer's current state."""
        state, _kind = ("idle", "idle")
        if self._focus_state_provider is not None:
            try:
                state, _kind = self._focus_state_provider()
            except Exception:  # noqa: BLE001 - menu must never fail
                pass
        panel = QAction("Focus…", menu)
        panel.triggered.connect(self.request_focus_panel.emit)
        menu.addAction(panel)
        if state == "idle":
            start = QAction("Start &focus session", menu)
            start.triggered.connect(
                lambda: self._bus.publish(E.FOCUS_CONTROL, {"action": "start"}))
            menu.addAction(start)
        elif state == "paused":
            resume = QAction("&Resume focus", menu)
            resume.triggered.connect(
                lambda: self._bus.publish(E.FOCUS_CONTROL, {"action": "resume"}))
            menu.addAction(resume)
            stop = QAction("Stop &focus", menu)
            stop.triggered.connect(
                lambda: self._bus.publish(E.FOCUS_CONTROL, {"action": "stop"}))
            menu.addAction(stop)
        else:  # focusing or on break
            pause = QAction("&Pause focus", menu)
            pause.triggered.connect(
                lambda: self._bus.publish(E.FOCUS_CONTROL, {"action": "pause"}))
            menu.addAction(pause)
            skip = QAction("S&kip to next", menu)
            skip.triggered.connect(
                lambda: self._bus.publish(E.FOCUS_CONTROL, {"action": "skip"}))
            menu.addAction(skip)
            stop = QAction("Stop &focus", menu)
            stop.triggered.connect(
                lambda: self._bus.publish(E.FOCUS_CONTROL, {"action": "stop"}))
            menu.addAction(stop)

    def _add_companion_items(self, menu: QMenu) -> None:
        new_rem = QAction("New &reminder…", menu)
        new_rem.triggered.connect(self.request_reminder_dialog.emit)
        menu.addAction(new_rem)
        upcoming = QAction("&Reminders…", menu)
        upcoming.triggered.connect(self.request_reminder_list.emit)
        menu.addAction(upcoming)
        scratch = QAction("&Scratchpad…", menu)
        scratch.triggered.connect(self.request_scratchpad.emit)
        menu.addAction(scratch)

    def _on_come_here(self) -> None:
        from PySide6.QtGui import QCursor

        pos = QCursor.pos()
        self._bus.publish(E.COME_HERE, {"x": pos.x(), "y": pos.y()})

    # -- Qt events ------------------------------------------------------------------

    def moveEvent(self, event) -> None:  # noqa: N802
        super().moveEvent(event)
        # Keep the character filling the window after resizes from frame changes.
        self._character.setGeometry(self.rect())

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._character.setGeometry(self.rect())
