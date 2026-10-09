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


class CompanionWindow(QWidget):
    request_mood_popup = Signal()
    request_quit = Signal()

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

        self._animations_enabled = settings.animations_enabled()

    # -- public ---------------------------------------------------------------

    def restore_or_default_position(self) -> None:
        saved = self._settings.get_position()
        if saved is not None:
            self.move(positioning.clamp_to_screen(self, saved))
        else:
            self.move(positioning.clamp_to_screen(self, positioning.default_position(self)))

    def set_animations_enabled(self, enabled: bool) -> None:
        self._animations_enabled = enabled

    # -- mouse input ------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_global = event.globalPosition().toPoint()
            self._press_window = self.pos()
            self._press_time = time.monotonic()
            self._dragging = False
            self._drag_start_emitted = False
            self._max_distance = 0.0
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
            assert self._press_window is not None
            new_pos = positioning.clamp_to_screen(self, self._press_window + delta)
            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or self._press_global is None:
            return
        duration = time.monotonic() - self._press_time
        was_drag = self._dragging
        self._press_global = None
        self._dragging = False
        if was_drag:
            self._settings.set_position(self.pos())
            self._bus.publish(
                E.DRAG_END,
                {"distance_px": self._max_distance, "duration_s": duration},
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

        anim_action = QAction("Animations", menu)
        anim_action.setCheckable(True)
        anim_action.setChecked(self._animations_enabled)
        anim_action.triggered.connect(self._on_animations_triggered)
        menu.addAction(anim_action)

        menu.addSeparator()
        quit_action = QAction("Quit Doodle", menu)
        quit_action.triggered.connect(self.request_quit.emit)
        menu.addAction(quit_action)

        menu.popup(global_pos)

    def _on_animations_triggered(self, checked: bool) -> None:
        self._animations_enabled = checked
        self._settings.set_animations_enabled(checked)
        self._bus.publish(E.ANIMATIONS_TOGGLED, {"enabled": checked})

    # -- Qt events ------------------------------------------------------------------

    def moveEvent(self, event) -> None:  # noqa: N802
        super().moveEvent(event)
        # Keep the character filling the window after resizes from frame changes.
        self._character.setGeometry(self.rect())

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._character.setGeometry(self.rect())
