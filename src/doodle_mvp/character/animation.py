"""Frame-based animation player driven by a single QTimer.

Design rules enforced here:
- Exactly one QTimer for the whole player; ``play()`` never creates another.
  Cross-fades reuse the same timer at a 16ms interval, then restore it.
- Replaying the same animation restarts its frame index instead of stacking.
- One-shot animations emit ``animation_finished``; the behavior engine
  decides what plays next (usually back to idle).
- Unknown animations fail gracefully (return False, keep current state).
- ``tick()`` advances one frame deterministically for tests.
- ``shutdown()`` stops the timer and releases cached pixmaps.

Transitions: ``play(name, loop, fade_ms)`` cross-fades from the currently
displayed frame to the new animation's first frame over ``fade_ms``
milliseconds (alpha blend with smoothstep easing). Fades are only used for
compatible pose pairs (loop->loop, drag->glide settle); the engine chooses
per transition. A new ``play()`` during a fade cancels it and fades from the
current blended frame, so interrupted transitions clean up correctly.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QElapsedTimer, QObject, QTimer, Signal
from PySide6.QtGui import QImage, QPainter, QPixmap

from .assets import AssetLoader

log = logging.getLogger(__name__)

FADE_TICK_MS = 16


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
        self._current: QPixmap | None = None  # last emitted frame
        self._fade: dict | None = None        # active cross-fade state

    # -- public API ----------------------------------------------------------

    @property
    def current_animation(self) -> str | None:
        return self._name

    @property
    def is_playing(self) -> bool:
        return self._timer.isActive()

    @property
    def is_fading(self) -> bool:
        return self._fade is not None

    @property
    def timer(self) -> QTimer:
        """Exposed for tests to assert the single-timer invariant."""
        return self._timer

    def play(self, name: str, loop: bool | None = None, fade_ms: int = 0) -> bool:
        """Switch to ``name``. Returns False if the animation is unavailable.

        ``fade_ms`` > 0 cross-fades from the currently displayed frame to the
        new animation's first frame instead of cutting.
        """
        spec = self._assets.spec_for(name)
        frames = self._assets.frames_for(name)
        if spec is None or not frames:
            log.warning("Ignoring request to play unknown/empty animation %r", name)
            return False
        self._cancel_fade()
        new_loop = spec.loop if loop is None else loop
        new_interval = max(16, int(1000 / spec.fps))
        if (
            fade_ms > 0
            and self._current is not None
            and self._current.cacheKey() != frames[0].cacheKey()
        ):
            self._name = name
            self._frames = frames
            self._index = 0
            self._loop = new_loop
            self._interval_ms = new_interval
            clock = QElapsedTimer()
            clock.start()
            self._fade = {
                "source": self._current,
                "target": frames[0],
                "clock": clock,
                "duration_ms": max(1, int(fade_ms)),
            }
            self._timer.start(FADE_TICK_MS)
            return True
        self._name = name
        self._frames = frames
        self._index = 0
        self._loop = new_loop
        self._interval_ms = new_interval
        self._timer.start(self._interval_ms)
        self._emit_frame(self._frames[0])
        return True

    def stop(self) -> None:
        self._cancel_fade()
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
        self._cancel_fade()
        self._timer.stop()
        self._name = name
        self._frames = frames
        self._index = 0
        self._emit_frame(frames[0])
        return True

    def tick(self) -> QPixmap | None:
        """Advance exactly one frame; used by the timer and by tests."""
        if self._fade is not None:
            self._finish_fade()
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
        self._emit_frame(pixmap)
        return pixmap

    def fade_step(self, forced_t: float | None = None) -> QPixmap | None:
        """Advance the active cross-fade; ``forced_t`` 0..1 for tests."""
        if self._fade is None:
            return None
        fade = self._fade
        if forced_t is not None:
            t = max(0.0, min(1.0, forced_t))
        else:
            t = min(1.0, fade["clock"].elapsed() / fade["duration_ms"])
        if t >= 1.0:
            self._finish_fade()
            return self._current
        eased = t * t * (3.0 - 2.0 * t)  # smoothstep
        blended = self._blend(fade["source"], fade["target"], eased)
        self._emit_frame(blended)
        return blended

    def shutdown(self) -> None:
        self.stop()
        self._assets.clear_cache()

    # -- internals ------------------------------------------------------------

    def _emit_frame(self, pixmap: QPixmap) -> None:
        self._current = pixmap
        self.frame_changed.emit(pixmap)

    def _cancel_fade(self) -> None:
        self._fade = None

    def _finish_fade(self) -> None:
        fade = self._fade
        self._fade = None
        if fade is None or not self._frames:
            return
        self._timer.start(self._interval_ms)
        self._emit_frame(self._frames[0])

    @staticmethod
    def _blend(a: QPixmap, b: QPixmap, t: float) -> QPixmap:
        img = QImage(a.size(), QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(0)
        painter = QPainter(img)
        painter.setOpacity(1.0 - t)
        painter.drawPixmap(0, 0, a)
        painter.setOpacity(t)
        painter.drawPixmap(0, 0, b)
        painter.end()
        return QPixmap.fromImage(img)

    def _on_timeout(self) -> None:
        if self._fade is not None:
            self.fade_step()
        else:
            self.tick()
