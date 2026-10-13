"""PersonalityScheduler: weighted, cooldown-aware autonomous activity picker.

The scheduler decides *what* Doodle does when idle, but never *when* —
timing stays with the BehaviorEngine's single-shot timer. Selection uses:

- weighted randomness (common: blink; rare: surprised),
- per-activity cooldowns (a rare treat can't fire twice in a row of minutes),
- recent-history suppression (no immediate repeats),
- an explicit "do nothing" outcome: calm inactivity is part of the charm.

All randomness goes through an injectable RNG and all time through an
injectable clock, so tests are deterministic.
"""

from __future__ import annotations

import random
import time

# Activity -> selection weight. Dizzy/sad/stressed are excluded: they are
# reactions to drags and moods, never autonomous picks.
WEIGHTS: dict[str, float] = {
    "blink": 35.0,
    "curious": 20.0,
    "yawn": 12.0,
    "sleepy": 8.0,
    "happy": 8.0,
    "playful": 7.0,
    "surprised": 5.0,
    "wander": 6.0,
    "gaze_left": 5.0,
    "gaze_right": 5.0,
    "gaze_up": 4.0,
    "blink_double": 9.0,
    "stretch": 6.0,
    "drowsy": 5.0,
    "notice": 8.0,
}

# Activity -> minimum seconds between selections.
COOLDOWNS: dict[str, float] = {
    "surprised": 120.0,
    "happy": 60.0,
    "playful": 60.0,
    "sleepy": 45.0,
    "wander": 90.0,
    "yawn": 30.0,
    "curious": 20.0,
    "gaze_left": 45.0,
    "gaze_right": 45.0,
    "gaze_up": 45.0,
    "blink": 0.0,
    "blink_double": 25.0,
    "drowsy": 120.0,
    "notice": 60.0,
    "stretch": 90.0,
}

# Focus-mode profile: calm activities only (no playful outbursts, no walks).
CALM_ACTIVITIES = frozenset(
    {"blink", "blink_double", "curious", "yawn", "sleepy", "gaze_left",
     "gaze_right", "gaze_up", "drowsy", "notice"}
)
# Rest/quiet profile: barely-there presence.
REST_ACTIVITIES = frozenset({"blink", "sleepy"})

# Activity levels driven by the personality policy (Phase 4).
LEVEL_NORMAL = "normal"
LEVEL_CALM = "calm"
LEVEL_REST = "rest"
LEVEL_QUIET = "quiet"

HISTORY_LEN = 3
IDLE_CHANCE = 0.18  # probability of "do nothing" on a given pick


class PersonalityScheduler:
    def __init__(
        self,
        rng: random.Random | None = None,
        clock=time.monotonic,
        weights: dict[str, float] | None = None,
        cooldowns: dict[str, float] | None = None,
    ) -> None:
        self._rng = rng or random.Random()
        self._clock = clock
        self._weights = dict(weights) if weights else dict(WEIGHTS)
        self._cooldowns = dict(cooldowns) if cooldowns else dict(COOLDOWNS)
        self._history: list[str] = []
        self._last_run: dict[str, float] = {}
        self._level = LEVEL_NORMAL

    @property
    def history(self) -> list[str]:
        return list(self._history)

    @property
    def level(self) -> str:
        return self._level

    def set_level(self, level: str) -> None:
        """Activity level from the personality policy."""
        if level not in (LEVEL_NORMAL, LEVEL_CALM, LEVEL_REST, LEVEL_QUIET):
            raise ValueError(f"Unknown activity level: {level!r}")
        self._level = level

    def set_calm(self, calm: bool) -> None:
        """Legacy shim (Phase 3 API)."""
        self.set_level(LEVEL_CALM if calm else LEVEL_NORMAL)

    def record(self, activity: str) -> None:
        """Mark an activity as performed (also used for user-triggered ones)."""
        now = self._clock()
        self._last_run[activity] = now
        self._history.append(activity)
        del self._history[:-HISTORY_LEN]  # keep only the most recent entries

    def eligible(self, now: float | None = None) -> list[str]:
        """Activities allowed right now (history + cooldown filtered)."""
        now = self._clock() if now is None else now
        recent = set(self._history[-2:])
        if self._level in (LEVEL_REST, LEVEL_QUIET):
            allowed = REST_ACTIVITIES
        elif self._level == LEVEL_CALM:
            allowed = CALM_ACTIVITIES
        else:
            allowed = None
        out = []
        for name in self._weights:
            if allowed is not None and name not in allowed:
                continue
            if name in recent:
                continue
            last = self._last_run.get(name, float("-inf"))
            if now - last < self._cooldowns.get(name, 0.0):
                continue
            out.append(name)
        return out

    def pick(self, now: float | None = None) -> str | None:
        """Pick the next autonomous activity, or None for calm inactivity."""
        now = self._clock() if now is None else now
        if self._rng.random() < IDLE_CHANCE:
            return None
        candidates = self.eligible(now)
        if not candidates:
            return None
        total = sum(self._weights[c] for c in candidates)
        roll = self._rng.random() * total
        for name in candidates:
            roll -= self._weights[name]
            if roll <= 0:
                return name
        return candidates[-1]
