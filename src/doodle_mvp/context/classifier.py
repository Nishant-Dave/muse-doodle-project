"""IdleClassifier: raw idle seconds -> stable DesktopActivity.

Hysteresis: entering an idle state requires crossing the threshold;
leaving it requires dropping below threshold - rearm_s. A single stray
cursor nudge therefore never flips the classification back and forth.
Thresholds are configurable; rearm defaults to 10s.
"""

from __future__ import annotations

from .model import DesktopActivity


class IdleClassifier:
    def __init__(self, short_s: float = 60.0, long_s: float = 300.0,
                 rearm_s: float = 10.0) -> None:
        if not 0 < short_s < long_s:
            raise ValueError("need 0 < short_s < long_s")
        self.short_s = short_s
        self.long_s = long_s
        self.rearm_s = rearm_s
        self.state = DesktopActivity.UNKNOWN

    def update_thresholds(self, short_s: float, long_s: float) -> None:
        if not 0 < short_s < long_s:
            raise ValueError("need 0 < short_s < long_s")
        self.short_s = short_s
        self.long_s = long_s
        self.state = DesktopActivity.UNKNOWN  # re-classify cleanly

    def classify(self, idle_s: float | None) -> DesktopActivity:
        """Classify one sample; keeps hysteresis across calls."""
        if idle_s is None or idle_s < 0:
            self.state = DesktopActivity.UNKNOWN
            return self.state
        if self.state == DesktopActivity.IDLE_LONG:
            if idle_s < self.long_s - self.rearm_s:
                self.state = (DesktopActivity.IDLE_SHORT
                              if idle_s >= self.short_s
                              else DesktopActivity.ACTIVE)
        elif self.state == DesktopActivity.IDLE_SHORT:
            if idle_s >= self.long_s:
                self.state = DesktopActivity.IDLE_LONG
            elif idle_s < self.short_s - self.rearm_s:
                self.state = DesktopActivity.ACTIVE
        else:  # ACTIVE or UNKNOWN: no hysteresis on entry
            if idle_s >= self.long_s:
                self.state = DesktopActivity.IDLE_LONG
            elif idle_s >= self.short_s:
                self.state = DesktopActivity.IDLE_SHORT
            else:
                self.state = DesktopActivity.ACTIVE
        return self.state
