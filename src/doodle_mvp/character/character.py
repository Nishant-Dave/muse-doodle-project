"""PandaCharacter: the widget that renders the panda's current frame."""

from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel


class PandaCharacter(QLabel):
    """A QLabel that displays animation frames, sized to the artwork."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

    @Slot(QPixmap)
    def show_frame(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            return
        if self.pixmap() is None or self.pixmap().size() != pixmap.size():
            self.setFixedSize(pixmap.size())
            # Keep the top-level window snug around the artwork.
            if self.parentWidget() is not None:
                self.parentWidget().setFixedSize(pixmap.size())
        self.setPixmap(pixmap)
