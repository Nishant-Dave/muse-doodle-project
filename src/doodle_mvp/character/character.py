"""PandaCharacter: the widget that renders the panda's current frame."""

from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QPixmap, QTransform
from PySide6.QtWidgets import QLabel


class PandaCharacter(QLabel):
    """A QLabel that displays animation frames, sized to the artwork.

    Supports horizontal facing: ``set_facing("left")`` mirrors frames so
    the panda can turn toward its movement direction without new assets.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._facing = "right"
        self._last_pixmap: QPixmap | None = None

    @property
    def facing(self) -> str:
        return self._facing

    def set_facing(self, facing: str) -> None:
        """Set facing direction ("left" or "right"); re-renders current frame."""
        if facing not in ("left", "right"):
            return
        if facing == self._facing:
            return
        self._facing = facing
        if self._last_pixmap is not None:
            self._display(self._last_pixmap)

    @Slot(QPixmap)
    def show_frame(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            return
        self._last_pixmap = pixmap
        self._display(pixmap)

    def _display(self, pixmap: QPixmap) -> None:
        shown = pixmap
        if self._facing == "left":
            w = pixmap.width()
            mirrored = pixmap.toImage().transformed(QTransform(-1, 0, 0, 0, 1, 0, w, 0, 1))
            shown = QPixmap.fromImage(mirrored)
        if self.pixmap() is None or self.pixmap().size() != shown.size():
            self.setFixedSize(shown.size())
            # Keep the top-level window snug around the artwork.
            if self.parentWidget() is not None:
                self.parentWidget().setFixedSize(shown.size())
        self.setPixmap(shown)
