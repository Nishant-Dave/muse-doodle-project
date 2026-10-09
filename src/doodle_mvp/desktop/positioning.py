"""Positioning helpers: keep the panda on-screen across launches."""

from __future__ import annotations

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QWidget


def default_position(window: QWidget) -> QPoint:
    """Bottom-right of the primary screen with a small margin."""
    screen = QApplication.primaryScreen()
    if screen is None:
        return QPoint(100, 100)
    geo = screen.availableGeometry()
    size = window.sizeHint() if window.size().isEmpty() else window.size()
    margin = 24
    return QPoint(
        geo.right() - size.width() - margin,
        geo.bottom() - size.height() - margin,
    )


def clamp_to_screen(window: QWidget, pos: QPoint) -> QPoint:
    """Clamp ``pos`` so the window stays fully within available geometry."""
    screen = QApplication.screenAt(pos)
    if screen is None:
        screen = QApplication.primaryScreen()
    if screen is None:
        return pos
    geo = screen.availableGeometry()
    size = window.size() if not window.size().isEmpty() else window.sizeHint()
    x = min(max(pos.x(), geo.left()), max(geo.left(), geo.right() - size.width()))
    y = min(max(pos.y(), geo.top()), max(geo.top(), geo.bottom() - size.height()))
    return QPoint(x, y)
