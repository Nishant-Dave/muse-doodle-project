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
MOMENTUM_KEY = "behavior/momentum_enabled"
WANDER_KEY = "behavior/wander_enabled"
PROXIMITY_RADIUS_KEY = "behavior/proximity_radius_px"
# -- Phase 3: focus timer ------------------------------------------------------
FOCUS_MINUTES_KEY = "focus/focus_minutes"
BREAK_MINUTES_KEY = "focus/break_minutes"
LONG_BREAK_MINUTES_KEY = "focus/long_break_minutes"
SESSIONS_BEFORE_LONG_BREAK_KEY = "focus/sessions_before_long_break"


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

    # -- movement & interaction ------------------------------------------------

    def momentum_enabled(self) -> bool:
        return self._bool(MOMENTUM_KEY, True)

    def set_momentum_enabled(self, enabled: bool) -> None:
        self._s.setValue(MOMENTUM_KEY, bool(enabled))

    def wander_enabled(self) -> bool:
        return self._bool(WANDER_KEY, True)

    def set_wander_enabled(self, enabled: bool) -> None:
        self._s.setValue(WANDER_KEY, bool(enabled))

    def proximity_radius(self) -> float:
        raw = self._s.value(PROXIMITY_RADIUS_KEY, 150.0)
        try:
            return max(60.0, min(float(raw), 600.0))
        except (TypeError, ValueError):
            log.warning("Ignoring invalid proximity radius %r", raw)
            return 150.0

    def set_proximity_radius(self, radius: float) -> None:
        self._s.setValue(PROXIMITY_RADIUS_KEY, float(radius))

    # -- focus timer ------------------------------------------------------------

    def focus_minutes(self) -> int:
        return self._clamped_int(FOCUS_MINUTES_KEY, 25, 1, 180)

    def set_focus_minutes(self, minutes: int) -> None:
        self._s.setValue(FOCUS_MINUTES_KEY, int(minutes))

    def break_minutes(self) -> int:
        return self._clamped_int(BREAK_MINUTES_KEY, 5, 1, 60)

    def set_break_minutes(self, minutes: int) -> None:
        self._s.setValue(BREAK_MINUTES_KEY, int(minutes))

    def long_break_minutes(self) -> int:
        return self._clamped_int(LONG_BREAK_MINUTES_KEY, 15, 1, 120)

    def set_long_break_minutes(self, minutes: int) -> None:
        self._s.setValue(LONG_BREAK_MINUTES_KEY, int(minutes))

    def sessions_before_long_break(self) -> int:
        return self._clamped_int(SESSIONS_BEFORE_LONG_BREAK_KEY, 4, 2, 12)

    def set_sessions_before_long_break(self, n: int) -> None:
        self._s.setValue(SESSIONS_BEFORE_LONG_BREAK_KEY, int(n))

    def _clamped_int(self, key: str, default: int, lo: int, hi: int) -> int:
        raw = self._s.value(key, default)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            log.warning("Ignoring invalid %s value %r", key, raw)
            return default
        return max(lo, min(hi, value))

    def _bool(self, key: str, default: bool) -> bool:
        raw = self._s.value(key, default)
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            v = raw.strip().lower()
            if v in ("1", "true", "yes", "on"):
                return True
            if v in ("0", "false", "no", "off"):
                return False
            log.warning("Ignoring invalid %s value %r; using %s", key, raw, default)
            return default
        try:
            return bool(int(raw))
        except (TypeError, ValueError):
            return default

    def sync(self) -> None:
        self._s.sync()
