"""System tray icon and its menu (lifecycle controls)."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

log = logging.getLogger(__name__)


class TrayController(QObject):
    request_show_hide = Signal()
    request_mood_popup = Signal()
    request_quit = Signal()
    animations_toggled = Signal(bool)

    def __init__(
        self,
        icon_pixmap: QPixmap,
        animations_enabled: bool,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._tray: QSystemTrayIcon | None = None
        self._animations_enabled = animations_enabled
        self._anim_action: QAction | None = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            log.warning("System tray not available; continuing without it")
            return
        self._tray = QSystemTrayIcon(QIcon(icon_pixmap), parent)
        self._tray.setToolTip("Doodle — desktop companion")
        self._tray.activated.connect(self._on_activated)
        self._tray.setContextMenu(self._build_menu())
        self._tray.show()

    @property
    def is_available(self) -> bool:
        return self._tray is not None

    def set_animations_enabled(self, enabled: bool) -> None:
        self._animations_enabled = enabled
        if self._anim_action is not None:
            self._anim_action.setChecked(enabled)

    def shutdown(self) -> None:
        if self._tray is not None:
            self._tray.hide()
            self._tray.deleteLater()
            self._tray = None

    # -- internals ------------------------------------------------------------

    def _build_menu(self) -> QMenu:
        menu = QMenu()
        show_action = QAction("Show / Hide Doodle", menu)
        show_action.triggered.connect(self.request_show_hide.emit)
        menu.addAction(show_action)

        mood_action = QAction("Log mood…", menu)
        mood_action.triggered.connect(self.request_mood_popup.emit)
        menu.addAction(mood_action)

        self._anim_action = QAction("Animations", menu)
        self._anim_action.setCheckable(True)
        self._anim_action.setChecked(self._animations_enabled)
        self._anim_action.triggered.connect(self._on_anim_triggered)
        menu.addAction(self._anim_action)

        menu.addSeparator()
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self.request_quit.emit)
        menu.addAction(quit_action)
        return menu

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.request_show_hide.emit()

    def _on_anim_triggered(self, checked: bool) -> None:
        self._animations_enabled = checked
        self.animations_toggled.emit(checked)
