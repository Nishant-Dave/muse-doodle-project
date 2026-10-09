"""Frame-based animation player driven by a single QTimer.

Design rules enforced here:
- Exactly one QTimer for the whole player; ``play()`` never creates another.
- Replaying the same animation restarts its frame index instead of stacking.
- One-shot animations emit ``animation_finished``; the behavior engine
  decides what plays next (usually back to idle).
- Unknown animations fail gracefully (return False, keep current state).
- ``tick()`` advances one frame deterministically for tests.
- ``shutdown()`` stops the timer and releases cached pixmaps.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QPixmap

from .assets import AssetLoader

log = logging.getLogger(__name__)


class AnimationPlayer(QObject):
    frame_changed = Signal(QPixmap)
    animation_finished = Signal(str)

    def __init__(
        self,
        assets: AssetLoader,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._assets = assets
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timeout)
        self._name: str | None = None
        self._frames: list[QPixmap] = []
        self._index = 0
        self._loop = True
        self._interval_ms = 150

    # -- public API ----------------------------------------------------------

    @property
    def current_animation(self) -> str | None:
        return self._name

    @property
    def is_playing(self) -> bool:
        return self._timer.isActive()

    @property
    def timer(self) -> QTimer:
        """Exposed for tests to assert the single-timer invariant."""
        return self._timer

    def play(self, name: str, loop: bool | None = None) -> bool:
        """Switch to ``name``. Returns False if the animation is unavailable."""
        spec = self._assets.spec_for(name)
        frames = self._assets.frames_for(name)
        if spec is None or not frames:
            log.warning("Ignoring request to play unknown/empty animation %r", name)
            return False
        self._name = name
        self._frames = frames
        self._index = 0
        self._loop = spec.loop if loop is None else loop
        self._interval_ms = max(16, int(1000 / spec.fps))
        self._timer.start(self._interval_ms)
        self.frame_changed.emit(self._frames[0])
        return True

    def stop(self) -> None:
        self._timer.stop()
        self._name = None
        self._frames = []
        self._index = 0

    def show_static(self, name: str) -> bool:
        """Display the first frame of ``name`` with no timer running."""
        frames = self._assets.frames_for(name)
        if not frames:
            log.warning("Ignoring static display of unknown/empty animation %r", name)
            return False
        self._timer.stop()
        self._name = name
        self._frames = frames
        self._index = 0
        self.frame_changed.emit(frames[0])
        return True

    def tick(self) -> QPixmap | None:
        """Advance exactly one frame; used by the timer and by tests."""
        if not self._frames:
            return None
        self._index += 1
        if self._index >= len(self._frames):
            if self._loop:
                self._index = 0
            else:
                finished = self._name or ""
                self.stop()
                self.animation_finished.emit(finished)
                return None
        pixmap = self._frames[self._index]
        self.frame_changed.emit(pixmap)
        return pixmap

    def shutdown(self) -> None:
        self.stop()
        self._assets.clear_cache()

    # -- internals ------------------------------------------------------------

    def _on_timeout(self) -> None:
        self.tick()
