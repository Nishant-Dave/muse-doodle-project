"""Package marker for the desktop subpackage."""

from .companion_window import CompanionWindow
from .positioning import clamp_to_screen, default_position
from .tray import TrayController

__all__ = ["CompanionWindow", "TrayController", "clamp_to_screen", "default_position"]
