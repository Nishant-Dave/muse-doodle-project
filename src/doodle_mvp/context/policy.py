"""PersonalityPolicy: snapshot -> activity decision.

Pure, deterministic function of the context snapshot: no timers, no Qt,
injectable anywhere. Precedence (first match wins):

1. Context adaptation disabled  -> NORMAL (ordinary behavior)
2. Direct interaction with Doodle -> NORMAL (responsiveness always wins)
3. Quiet mode                    -> QUIET  (minimal everything)
4. Focus session active/paused   -> CALM
5. On break                      -> NORMAL (relaxed)
6. Idle long                     -> REST   (quiet, resting character)
7. Idle short                    -> CALM
8. Otherwise                     -> NORMAL

Deliberately no inference of emotion, productivity, or attention: idle
time only ever quiets Doodle down, never judges the user.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from .model import (
    ContextSnapshot,
    DesktopActivity,
    DoodleInteraction,
    FocusPhase,
)


class ActivityLevel(enum.Enum):
    NORMAL = "normal"  # full personality
    CALM = "calm"      # reduced: calm animations, slower cadence, no wandering
    REST = "rest"      # minimal: blink/sleepy only, rare, never wanders
    QUIET = "quiet"    # user-requested: like REST, plus no cursor reactions


@dataclass(frozen=True)
class PolicyDecision:
    level: ActivityLevel
    reason: str


class PersonalityPolicy:
    def __init__(self, adaptive: bool = True) -> None:
        self.adaptive = adaptive

    def decide(self, snapshot: ContextSnapshot) -> PolicyDecision:
        if not self.adaptive:
            return PolicyDecision(ActivityLevel.NORMAL, "adaptive personality off")
        if snapshot.interaction == DoodleInteraction.DIRECT:
            return PolicyDecision(ActivityLevel.NORMAL, "direct interaction")
        if snapshot.quiet:
            return PolicyDecision(ActivityLevel.QUIET, "quiet mode")
        if snapshot.focus in (FocusPhase.FOCUSING, FocusPhase.FOCUS_PAUSED):
            return PolicyDecision(ActivityLevel.CALM, "focus session")
        if snapshot.focus in (FocusPhase.ON_BREAK, FocusPhase.BREAK_PAUSED):
            return PolicyDecision(ActivityLevel.NORMAL, "on break")
        if snapshot.desktop == DesktopActivity.IDLE_LONG:
            return PolicyDecision(ActivityLevel.REST, "idle long")
        if snapshot.desktop == DesktopActivity.IDLE_SHORT:
            return PolicyDecision(ActivityLevel.CALM, "idle short")
        return PolicyDecision(ActivityLevel.NORMAL, "active or unknown")
