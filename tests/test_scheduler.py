"""PersonalityScheduler tests: weights, cooldowns, history, idle chance."""

import random

from doodle_mvp.behavior.scheduler import HISTORY_LEN, PersonalityScheduler


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class LowRollRng:
    """RNG stub: first random() -> 0.01 (forces idle), then delegates."""

    def __init__(self, seed=0):
        self._rng = random.Random(seed)
        self._first = True

    def random(self):
        if self._first:
            self._first = False
            return 0.01
        return self._rng.random()

    def uniform(self, a, b):
        return a + (b - a) * self.random()


def test_pick_returns_known_activity():
    sched = PersonalityScheduler(rng=random.Random(0), clock=FakeClock())
    activity = sched.pick()
    assert activity in (
        "blink", "curious", "yawn", "sleepy", "happy", "playful", "surprised", "wander",
    )


def test_idle_chance_yields_calm_inactivity():
    sched = PersonalityScheduler(rng=LowRollRng(), clock=FakeClock())
    assert sched.pick() is None  # 0.01 < IDLE_CHANCE


def test_no_immediate_repeats():
    clock = FakeClock()
    sched = PersonalityScheduler(rng=random.Random(7), clock=clock)
    first = sched.pick()
    sched.record(first)
    second = sched.pick()
    assert second != first or second is None


def test_history_is_bounded():
    clock = FakeClock()
    sched = PersonalityScheduler(rng=random.Random(0), clock=clock)
    for name in ["blink", "yawn", "curious", "happy", "playful"]:
        sched.record(name)
    assert len(sched.history) == HISTORY_LEN
    assert sched.history == ["curious", "happy", "playful"]


def test_cooldown_suppresses_rare_activity():
    clock = FakeClock()
    sched = PersonalityScheduler(rng=random.Random(0), clock=clock)
    sched.record("surprised")
    clock.advance(30)  # < 120s cooldown
    assert "surprised" not in sched.eligible()
    clock.advance(120)  # now past cooldown (and out of recent history)
    sched.record("blink")
    sched.record("yawn")
    assert "surprised" in sched.eligible()


def test_record_applies_cooldown_to_user_triggered_activity():
    clock = FakeClock()
    sched = PersonalityScheduler(rng=random.Random(0), clock=clock)
    sched.record("playful")  # e.g. user poked the panda
    assert "playful" not in sched.eligible()


def test_eligible_never_empty_for_blink():
    # blink has no cooldown and drops out of history quickly, so the
    # scheduler can always fall back to something.
    clock = FakeClock()
    sched = PersonalityScheduler(rng=random.Random(0), clock=clock)
    sched.record("blink")
    sched.record("yawn")
    sched.record("curious")
    assert "blink" in sched.eligible()
