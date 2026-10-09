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
from ..character.animation import AnimationPlayer
from ..character.assets import AssetLoader
from ..character.character import PandaCharacter
from ..desktop.companion_window import CompanionWindow
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
        self.engine = BehaviorEngine(self.bus)
        self.mood_state = MoodState()
        self.popup = MoodPopup()

        icon = self._tray_icon()
        self.tray = TrayController(icon, self.settings.animations_enabled())

        self._wire()
        self._shutdown_done = False

    # -- wiring -----------------------------------------------------------------

    def _wire(self) -> None:
        self.engine.play_requested.connect(self.player.play)
        self.engine.static_requested.connect(self.player.show_static)
        self.player.frame_changed.connect(self.character.show_frame)
        self.player.animation_finished.connect(self.engine.on_animation_finished)

        self.window.request_mood_popup.connect(lambda: self.popup.show_near(self.window))
        self.window.request_quit.connect(self.shutdown_and_quit)

        self.tray.request_show_hide.connect(self._toggle_visible)
        self.tray.request_mood_popup.connect(lambda: self.popup.show_near(self.window))
        self.tray.request_quit.connect(self.shutdown_and_quit)
        self.tray.animations_toggled.connect(self._on_animations_toggled)

        self.popup.mood_chosen.connect(self._on_mood_chosen)

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
        self.bus.clear()

    # -- slots ----------------------------------------------------------------------

    def _toggle_visible(self) -> None:
        if self.window.isVisible():
            self.window.hide()
        else:
            self.window.show()
            self.window.raise_()

    def _on_animations_toggled(self, enabled: bool) -> None:
        self.settings.set_animations_enabled(enabled)
        self.window.set_animations_enabled(enabled)
        self.tray.set_animations_enabled(enabled)
        self.bus.publish(E.ANIMATIONS_TOGGLED, {"enabled": enabled})

    def _on_mood_chosen(self, mood: str) -> None:
        if self.mood_state.set_mood(mood):
            self.bus.publish(E.MOOD_SELECTED, {"mood": mood})

    def _tray_icon(self) -> QPixmap:
        frames = self.assets.frames_for("idle")
        if frames:
            return frames[0]
        return QPixmap()
