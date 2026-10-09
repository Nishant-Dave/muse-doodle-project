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
    momentum_toggled = Signal(bool)
    wander_toggled = Signal(bool)
    come_here_requested = Signal()
    wander_now_requested = Signal()
    request_focus_panel = Signal()
    request_reminder_dialog = Signal()
    request_reminder_list = Signal()
    request_scratchpad = Signal()
    focus_control = Signal(str)  # start|pause|resume|stop|skip

    def __init__(
        self,
        icon_pixmap: QPixmap,
        animations_enabled: bool,
        momentum_enabled: bool = True,
        wander_enabled: bool = True,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._tray: QSystemTrayIcon | None = None
        self._animations_enabled = animations_enabled
        self._momentum_enabled = momentum_enabled
        self._wander_enabled = wander_enabled
        self._focus_state_provider = None
        self._menu: QMenu | None = None
        self._anim_action: QAction | None = None
        self._momentum_action: QAction | None = None
        self._wander_action: QAction | None = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            log.warning("System tray not available; continuing without it")
            return
        self._tray = QSystemTrayIcon(QIcon(icon_pixmap), parent)
        self._tray.setToolTip("Doodle — desktop companion")
        self._tray.activated.connect(self._on_activated)
        self._menu = self._build_menu()
        self._menu.aboutToShow.connect(self._refresh_menu)
        self._tray.setContextMenu(self._menu)
        self._tray.show()

    def set_focus_state_provider(self, provider) -> None:
        self._focus_state_provider = provider

    def _refresh_menu(self) -> None:
        """Rebuild the menu on every show so focus items stay contextual."""
        if self._tray is None or self._menu is None:
            return
        self._menu.aboutToShow.disconnect(self._refresh_menu)
        new_menu = self._build_menu()
        new_menu.aboutToShow.connect(self._refresh_menu)
        old = self._menu
        self._menu = new_menu
        self._tray.setContextMenu(new_menu)
        if old is not None:
            old.deleteLater()

    @property
    def is_available(self) -> bool:
        return self._tray is not None

    def set_animations_enabled(self, enabled: bool) -> None:
        self._animations_enabled = enabled
        if self._anim_action is not None:
            self._anim_action.setChecked(enabled)

    def set_momentum_enabled(self, enabled: bool) -> None:
        self._momentum_enabled = enabled
        if self._momentum_action is not None:
            self._momentum_action.setChecked(enabled)

    def set_wander_enabled(self, enabled: bool) -> None:
        self._wander_enabled = enabled
        if self._wander_action is not None:
            self._wander_action.setChecked(enabled)

    def set_tooltip(self, text: str) -> None:
        if self._tray is not None:
            self._tray.setToolTip(text)

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

        menu.addSeparator()
        focus_panel = QAction("Focus…", menu)
        focus_panel.triggered.connect(self.request_focus_panel.emit)
        menu.addAction(focus_panel)
        state = "idle"
        if self._focus_state_provider is not None:
            try:
                state, _kind = self._focus_state_provider()
            except Exception:  # noqa: BLE001 - menu must never fail
                pass
        if state == "idle":
            start = QAction("Start &focus session", menu)
            start.triggered.connect(lambda: self.focus_control.emit("start"))
            menu.addAction(start)
        elif state == "paused":
            resume = QAction("&Resume focus", menu)
            resume.triggered.connect(lambda: self.focus_control.emit("resume"))
            menu.addAction(resume)
            stop = QAction("Stop &focus", menu)
            stop.triggered.connect(lambda: self.focus_control.emit("stop"))
            menu.addAction(stop)
        else:
            pause = QAction("&Pause focus", menu)
            pause.triggered.connect(lambda: self.focus_control.emit("pause"))
            menu.addAction(pause)
            skip = QAction("S&kip to next", menu)
            skip.triggered.connect(lambda: self.focus_control.emit("skip"))
            menu.addAction(skip)
            stop = QAction("Stop &focus", menu)
            stop.triggered.connect(lambda: self.focus_control.emit("stop"))
            menu.addAction(stop)

        menu.addSeparator()
        new_rem = QAction("New &reminder…", menu)
        new_rem.triggered.connect(self.request_reminder_dialog.emit)
        menu.addAction(new_rem)
        upcoming = QAction("&Reminders…", menu)
        upcoming.triggered.connect(self.request_reminder_list.emit)
        menu.addAction(upcoming)
        scratch = QAction("&Scratchpad…", menu)
        scratch.triggered.connect(self.request_scratchpad.emit)
        menu.addAction(scratch)

        menu.addSeparator()
        self._anim_action = QAction("Animations", menu)
        self._anim_action.setCheckable(True)
        self._anim_action.setChecked(self._animations_enabled)
        self._anim_action.triggered.connect(self._on_anim_triggered)
        menu.addAction(self._anim_action)

        self._momentum_action = QAction("Glide after drag", menu)
        self._momentum_action.setCheckable(True)
        self._momentum_action.setChecked(self._momentum_enabled)
        self._momentum_action.triggered.connect(self._on_momentum_triggered)
        menu.addAction(self._momentum_action)

        self._wander_action = QAction("Wander around", menu)
        self._wander_action.setCheckable(True)
        self._wander_action.setChecked(self._wander_enabled)
        self._wander_action.triggered.connect(self._on_wander_triggered)
        menu.addAction(self._wander_action)

        menu.addSeparator()
        come_action = QAction("Come here", menu)
        come_action.triggered.connect(self.come_here_requested.emit)
        menu.addAction(come_action)
        walk_action = QAction("Take a walk", menu)
        walk_action.triggered.connect(self.wander_now_requested.emit)
        menu.addAction(walk_action)

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

    def _on_momentum_triggered(self, checked: bool) -> None:
        self._momentum_enabled = checked
        self.momentum_toggled.emit(checked)

    def _on_wander_triggered(self, checked: bool) -> None:
        self._wander_enabled = checked
        self.wander_toggled.emit(checked)
