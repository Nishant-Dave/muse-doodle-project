"""Package marker for the desktop subpackage."""

from .companion_window import CompanionWindow
from .cursor_monitor import CursorMonitor
from .mover import Mover
from .positioning import clamp_to_screen, default_position
from .tray import TrayController

__all__ = [
    "CompanionWindow",
    "CursorMonitor",
    "Mover",
    "TrayController",
    "clamp_to_screen",
    "default_position",
]
