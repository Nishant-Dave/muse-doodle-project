"""DoodleApplication: builds, wires, runs, and shuts down the companion.

Wiring (all in one place, so module boundaries stay clean):

    CompanionWindow --(bus events)--> BehaviorEngine --(play_requested)--> AnimationPlayer
        |                                                                    |
        +-- request_mood_popup --> MoodPopup --(mood_chosen)--> MoodState/bus -+
        +-- request_quit --> shutdown                                          |
    TrayController --(menu actions)-------------------------------------------+

``shutdown()`` is idempotent: timers stop, position is saved, resources are
released, and the bus is cleared. Calling it twice is safe.
"""

from __future__ import annotations

import logging

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from ..behavior import events as E
from ..behavior.engine import BehaviorEngine
from ..behavior.events import EventBus
from ..behavior.scheduler import PersonalityScheduler
from ..character.animation import AnimationPlayer
from ..character.assets import AssetLoader
from ..character.character import PandaCharacter
from ..companion.dialogs import (
    FocusPanel,
    NoticePopup,
    ReminderDialog,
    ReminderListDialog,
    ScratchpadDialog,
)
from ..companion.focus import FocusTimer
from ..companion.reminders import ReminderScheduler, ReminderStore
from ..desktop import positioning
from ..desktop.companion_window import CompanionWindow
from ..desktop.cursor_monitor import CursorMonitor
from ..desktop.mover import Mover
from ..desktop.tray import TrayController
from ..mood.mood import MoodState
from ..mood.mood_popup import MoodPopup
from ..persistence.settings import AppSettings
from ..platform.adapter import PlatformAdapter, get_platform_adapter

log = logging.getLogger(__name__)


class DoodleApplication:
    def __init__(
        self,
        argv: list[str] | None = None,
        *,
        settings: AppSettings | None = None,
        adapter: PlatformAdapter | None = None,
    ) -> None:
        existing = QApplication.instance()
        self._qapp = existing or QApplication(argv or [])
        self._owns_qapp = existing is None

        self.bus = EventBus()
        self.settings = settings or AppSettings()
        self.adapter = adapter or get_platform_adapter()
        self.assets = AssetLoader()
        self.player = AnimationPlayer(self.assets)
        self.character = PandaCharacter()
        self.window = CompanionWindow(self.bus, self.character, self.settings, self.adapter)
        self.scheduler = PersonalityScheduler()
        self.mover = Mover(
            get_pos=self.window.pos,
            move_to=lambda p: self.window.move(positioning.clamp_to_screen(self.window, p)),
        )
        self.cursor_monitor = CursorMonitor(
            self.bus,
            anchor=self.window.center,
            radius_px=self.settings.proximity_radius(),
        )
        self.engine = BehaviorEngine(
            self.bus,
            scheduler=self.scheduler,
            mover=self.mover,
            monitor=self.cursor_monitor,
            get_pos=self.window.pos,
        )
        self.mood_state = MoodState()
        self.popup = MoodPopup()

        # Phase 3: companion features (local only).
        self.focus_timer = FocusTimer(self.bus, self.settings)
        self.reminder_store = ReminderStore()
        self.reminder_scheduler = ReminderScheduler(self.bus, self.reminder_store)
        self.focus_panel = FocusPanel(self.focus_timer, self.bus)
        self.reminder_list_dialog = ReminderListDialog(self.reminder_store, self.bus)
        self.scratchpad_dialog = ScratchpadDialog()
        self.notice_popup = NoticePopup()
        self.notice_popup.dismissed.connect(self._on_notice_dismissed)
        self.notice_popup.closed.connect(self._show_next_notice)
        self._notice_queue: list[dict] = []

        icon = self._tray_icon()
        self.tray = TrayController(
            icon,
            self.settings.animations_enabled(),
            momentum_enabled=self.settings.momentum_enabled(),
            wander_enabled=self.settings.wander_enabled(),
        )

        self._wire()
        self._shutdown_done = False

    # -- wiring -----------------------------------------------------------------

    def _wire(self) -> None:
        self.engine.play_requested.connect(self.player.play)
        self.engine.static_requested.connect(self.player.show_static)
        self.engine.facing_changed.connect(self.character.set_facing)
        self.player.frame_changed.connect(self.character.show_frame)
        self.player.animation_finished.connect(self.engine.on_animation_finished)

        self.window.request_mood_popup.connect(lambda: self.popup.show_near(self.window))
        self.window.request_quit.connect(self.shutdown_and_quit)
        self.window.request_focus_panel.connect(self._show_focus_panel)
        self.window.request_reminder_dialog.connect(self._open_reminder_dialog)
        self.window.request_reminder_list.connect(self._show_reminder_list)
        self.window.request_scratchpad.connect(self._show_scratchpad)
        self.window.set_focus_state_provider(self._focus_state)

        self.tray.request_show_hide.connect(self._toggle_visible)
        self.tray.request_mood_popup.connect(lambda: self.popup.show_near(self.window))
        self.tray.request_quit.connect(self.shutdown_and_quit)
        self.tray.request_focus_panel.connect(self._show_focus_panel)
        self.tray.request_reminder_dialog.connect(self._open_reminder_dialog)
        self.tray.request_reminder_list.connect(self._show_reminder_list)
        self.tray.request_scratchpad.connect(self._show_scratchpad)
        self.tray.set_focus_state_provider(self._focus_state)
        self.tray.focus_control.connect(
            lambda action: self.bus.publish(E.FOCUS_CONTROL, {"action": action})
        )

        self.tray.request_show_hide.connect(self._toggle_visible)
        self.tray.request_mood_popup.connect(lambda: self.popup.show_near(self.window))
        self.tray.request_quit.connect(self.shutdown_and_quit)
        self.tray.animations_toggled.connect(
            lambda enabled: self.bus.publish(E.ANIMATIONS_TOGGLED, {"enabled": enabled})
        )
        self.tray.momentum_toggled.connect(
            lambda enabled: self.bus.publish(E.MOMENTUM_TOGGLED, {"enabled": enabled})
        )
        self.tray.wander_toggled.connect(
            lambda enabled: self.bus.publish(E.WANDER_TOGGLED, {"enabled": enabled})
        )
        self.tray.come_here_requested.connect(self._on_tray_come_here)
        self.tray.wander_now_requested.connect(
            lambda: self.bus.publish(E.WANDER_NOW, {})
        )

        # Application owns settings persistence + menu checkmarks for toggles
        # (the engine subscribes to the same events for behavior flags).
        self.bus.subscribe(E.ANIMATIONS_TOGGLED, self._apply_animations_toggled)
        self.bus.subscribe(E.MOMENTUM_TOGGLED, self._apply_momentum_toggled)
        self.bus.subscribe(E.WANDER_TOGGLED, self._apply_wander_toggled)

        self.popup.mood_chosen.connect(self._on_mood_chosen)

        # Companion wiring.
        self.bus.subscribe(E.REMINDER_DUE, self._on_reminder_due)
        self.bus.subscribe(E.FOCUS_TICK, self._on_focus_tick)
        for ev in (E.FOCUS_STOPPED, E.FOCUS_COMPLETED, E.BREAK_COMPLETED):
            self.bus.subscribe(ev, lambda _p: self._reset_tray_tooltip())
        self.focus_timer.start()
        self.reminder_scheduler.start()

        self.engine.start()
        if not self.settings.animations_enabled():
            # Go through the real event path so startup == toggle behavior.
            self.bus.publish(E.ANIMATIONS_TOGGLED, {"enabled": False})

    # -- run / shutdown -----------------------------------------------------------

    def run(self) -> int:
        self.window.restore_or_default_position()
        self.window.show()
        self.bus.publish(E.APP_STARTED)
        log.info("Doodle is running")
        return self._qapp.exec()

    def self_check(self) -> int:
        """Headless smoke test: build everything, pump events, shut down."""
        self.window.restore_or_default_position()
        self.window.show()
        self._qapp.processEvents()
        playing = self.player.current_animation == "idle"
        self.shutdown()
        self._qapp.processEvents()
        log.info("self-check: idle animation active=%s", playing)
        return 0 if playing else 1

    def shutdown_and_quit(self) -> None:
        self.shutdown()
        self._qapp.quit()

    def shutdown(self) -> None:
        if self._shutdown_done:
            return
        self._shutdown_done = True
        log.info("Shutting down Doodle")
        self.bus.publish(E.APP_EXITING)
        try:
            self.settings.set_position(self.window.pos())
            self.settings.sync()
        except Exception as exc:  # never let shutdown itself crash
            log.warning("Could not persist position: %s", exc)
        self.player.shutdown()
        self.tray.shutdown()
        self.popup.close()
        for dialog in (self.focus_panel, self.reminder_list_dialog,
                       self.scratchpad_dialog, self.notice_popup):
            try:
                dialog.close()
            except Exception:  # noqa: BLE001
                pass
        self.bus.clear()

    # -- slots ----------------------------------------------------------------------

    def _toggle_visible(self) -> None:
        if self.window.isVisible():
            self.window.hide()
        else:
            self.window.show()
            self.window.raise_()

    def _apply_animations_toggled(self, payload: dict) -> None:
        enabled = bool(payload.get("enabled", True))
        self.settings.set_animations_enabled(enabled)
        self.window.set_animations_enabled(enabled)
        self.tray.set_animations_enabled(enabled)

    def _apply_momentum_toggled(self, payload: dict) -> None:
        enabled = bool(payload.get("enabled", True))
        self.settings.set_momentum_enabled(enabled)
        self.window.set_momentum_enabled(enabled)
        self.tray.set_momentum_enabled(enabled)

    def _apply_wander_toggled(self, payload: dict) -> None:
        enabled = bool(payload.get("enabled", True))
        self.settings.set_wander_enabled(enabled)
        self.window.set_wander_enabled(enabled)
        self.tray.set_wander_enabled(enabled)

    def _on_tray_come_here(self) -> None:
        from PySide6.QtGui import QCursor

        pos = QCursor.pos()
        self.bus.publish(E.COME_HERE, {"x": pos.x(), "y": pos.y()})

    def _on_mood_chosen(self, mood: str) -> None:
        if self.mood_state.set_mood(mood):
            self.bus.publish(E.MOOD_SELECTED, {"mood": mood})

    # -- Phase 3: companion slots -----------------------------------------------------

    def _focus_state(self) -> tuple[str, str]:
        return (self.focus_timer.state, self.focus_timer.active_kind)

    def _show_focus_panel(self) -> None:
        self.focus_panel.refresh()
        self.focus_panel.show()
        self.focus_panel.raise_()
        self.focus_panel.activateWindow()

    def _open_reminder_dialog(self) -> None:
        dlg = ReminderDialog()
        if dlg.exec() == ReminderDialog.DialogCode.Accepted:
            record = dlg.result_record()
            if record:
                created = self.reminder_store.add(**record)
                self.bus.publish(E.REMINDER_CREATED,
                                 {"id": created["id"], "title": created["title"]})

    def _show_reminder_list(self) -> None:
        self.reminder_list_dialog.refresh()
        self.reminder_list_dialog.show()
        self.reminder_list_dialog.raise_()
        self.reminder_list_dialog.activateWindow()

    def _show_scratchpad(self) -> None:
        self.scratchpad_dialog.show()
        self.scratchpad_dialog.raise_()
        self.scratchpad_dialog.activateWindow()

    def _on_reminder_due(self, payload: dict) -> None:
        self._notice_queue.append(payload)
        self._show_next_notice()

    def _show_next_notice(self) -> None:
        if self.notice_popup.isVisible() or not self._notice_queue:
            return
        payload = self._notice_queue.pop(0)
        self.notice_popup.show_near(
            self.window,
            str(payload.get("id", "")),
            str(payload.get("title", "")),
            overdue=bool(payload.get("overdue", False)),
        )

    def _on_notice_dismissed(self, reminder_id: str) -> None:
        if self.reminder_store.dismiss(reminder_id):
            self.bus.publish(E.REMINDER_DISMISSED, {"id": reminder_id})
        self._show_next_notice()

    def _on_focus_tick(self, payload: dict) -> None:
        kind = str(payload.get("kind", "focus"))
        remaining = int(payload.get("remaining_s", 0))
        label = "Focus" if kind == "focus" else "Break"
        mins, secs = divmod(remaining, 60)
        if self.tray.is_available:
            self.tray.set_tooltip(f"Doodle — {label} {mins:02d}:{secs:02d} left")

    def _reset_tray_tooltip(self) -> None:
        if self.tray.is_available:
            self.tray.set_tooltip("Doodle — desktop companion")

    def _tray_icon(self) -> QPixmap:
        frames = self.assets.frames_for("idle")
        if frames:
            return frames[0]
        return QPixmap()
