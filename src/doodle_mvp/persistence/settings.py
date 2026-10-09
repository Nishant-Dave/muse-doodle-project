"""Lightweight preferences via QSettings (no database in Phase 1).

Stored keys:
- ``window/pos``: last panda position as "x,y"
- ``behavior/animations_enabled``: bool, default True
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QPoint, QSettings

log = logging.getLogger(__name__)

ORG_NAME = "Doodle"
APP_NAME = "DoodlePhase1"
POS_KEY = "window/pos"
ANIMATIONS_KEY = "behavior/animations_enabled"


class AppSettings:
    def __init__(self, settings: QSettings | None = None) -> None:
        self._s = settings or QSettings(ORG_NAME, APP_NAME)

    # -- window position ----------------------------------------------------

    def get_position(self) -> QPoint | None:
        raw = self._s.value(POS_KEY, None)
        if raw is None:
            return None
        try:
            if isinstance(raw, QPoint):
                return raw
            x_str, y_str = str(raw).split(",")
            return QPoint(int(x_str), int(y_str))
        except (ValueError, AttributeError) as exc:
            log.warning("Ignoring invalid stored position %r: %s", raw, exc)
            return None

    def set_position(self, pos: QPoint) -> None:
        self._s.setValue(POS_KEY, f"{pos.x()},{pos.y()}")

    # -- animation enablement -----------------------------------------------

    def animations_enabled(self) -> bool:
        raw = self._s.value(ANIMATIONS_KEY, True)
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            v = raw.strip().lower()
            if v in ("1", "true", "yes", "on"):
                return True
            if v in ("0", "false", "no", "off"):
                return False
            log.warning("Ignoring invalid animations_enabled value %r; using True", raw)
            return True
        try:
            return bool(int(raw))
        except (TypeError, ValueError):
            log.warning("Ignoring invalid animations_enabled value %r; using True", raw)
            return True

    def set_animations_enabled(self, enabled: bool) -> None:
        self._s.setValue(ANIMATIONS_KEY, bool(enabled))

    def sync(self) -> None:
        self._s.sync()
