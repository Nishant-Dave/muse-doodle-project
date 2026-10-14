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

    def system_idle_seconds(self) -> float | None:
        """Seconds since last user input; None when unavailable."""
        return None

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
        self._kernel32 = None
        self._idle_warned = False
        try:
            import ctypes

            self._user32 = ctypes.windll.user32
            # GetTickCount/GetTickCount64 live in kernel32, not user32.
            self._kernel32 = ctypes.windll.kernel32
            self._kernel32.GetTickCount64.restype = ctypes.c_ulonglong
            self._kernel32.GetTickCount.restype = ctypes.c_uint
        except Exception:  # pragma: no cover - non-Windows or locked down
            log.warning("ctypes user32 unavailable; using Qt-only window behavior")

    def configure_companion_window(self, window: QWidget) -> None:
        super().configure_companion_window(window)
        # Qt flags already give us frameless + top-most + tool window on
        # Windows. The ctypes handle is kept for future needs (e.g. click-
        # through regions) without letting Win32 calls leak into UI code.

    def system_idle_seconds(self) -> float | None:
        """Seconds since last input via GetLastInputInfo; None if unavailable."""
        if self._user32 is None or self._kernel32 is None:
            return None
        try:
            import ctypes

            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

            info = LASTINPUTINFO()
            info.cbSize = ctypes.sizeof(info)
            if not self._user32.GetLastInputInfo(ctypes.byref(info)):
                return None
            # GetTickCount64 avoids the 49-day wrap of GetTickCount.
            try:
                now_ms = self._kernel32.GetTickCount64()
                delta_ms = now_ms - info.dwTime
            except AttributeError:
                # 32-bit tick: mask the subtraction so the 49-day wrap
                # yields a small positive delta instead of a huge one.
                now_ms = self._kernel32.GetTickCount()
                delta_ms = (now_ms - info.dwTime) & 0xFFFFFFFF
            return max(0.0, delta_ms / 1000.0)
        except Exception as exc:  # never let idle detection crash the app
            if not self._idle_warned:
                self._idle_warned = True
                log.warning("GetLastInputInfo failed: %s", exc)
            return None


class PosixPlatformAdapter(PlatformAdapter):
    """Linux/macOS fallback: Qt-only behavior."""

    name = "posix"


def get_platform_adapter() -> PlatformAdapter:
    if sys.platform.startswith("win"):
        return WindowsPlatformAdapter()
    return PosixPlatformAdapter()
