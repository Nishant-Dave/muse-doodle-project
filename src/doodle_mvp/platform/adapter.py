"""Platform adapter: Windows-specific behavior behind a clean interface.

All OS-specific operations live here. The rest of the application talks only
to :class:`PlatformAdapter`, so behavior code never branches on sys.platform
and tests can substitute a fake adapter.
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

log = logging.getLogger(__name__)


class PlatformAdapter:
    """Base adapter: safe cross-platform defaults."""

    name = "base"

    def supports_transparency(self) -> bool:
        return True

    def configure_companion_window(self, window: QWidget) -> None:
        """Apply window flags/attributes for a floating companion window."""
        window.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool  # no taskbar button, not "always on top" aggressive
        )
        window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        window.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

    def keep_above(self, window: QWidget, above: bool = True) -> None:
        window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, above)
        # Re-applying flags requires re-showing the window.
        if window.isVisible():
            window.show()


class WindowsPlatformAdapter(PlatformAdapter):
    """Windows specifics via ctypes (no pywin32 dependency)."""

    name = "windows"

    def __init__(self) -> None:
        self._user32 = None
        try:
            import ctypes

            self._user32 = ctypes.windll.user32
        except Exception:  # pragma: no cover - non-Windows or locked down
            log.warning("ctypes user32 unavailable; using Qt-only window behavior")

    def configure_companion_window(self, window: QWidget) -> None:
        super().configure_companion_window(window)
        # Qt flags already give us frameless + top-most + tool window on
        # Windows. The ctypes handle is kept for future needs (e.g. click-
        # through regions) without letting Win32 calls leak into UI code.


class PosixPlatformAdapter(PlatformAdapter):
    """Linux/macOS fallback: Qt-only behavior."""

    name = "posix"


def get_platform_adapter() -> PlatformAdapter:
    if sys.platform.startswith("win"):
        return WindowsPlatformAdapter()
    return PosixPlatformAdapter()
