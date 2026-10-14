"""Phase 7 tests: personality profiles, movement gating, focus cheer."""

import random

import pytest
from PySide6.QtCore import QObject, QPoint, Signal

from doodle_mvp.behavior import events as E
from doodle_mvp.behavior.engine import IDLE, REACTING, BehaviorEngine
from doodle_mvp.behavior.scheduler import (
    DEFAULT_PROFILE,
    PERSONALITY_PROFILES,
    POST_INTERACTION_QUIET_S,
    PersonalityScheduler,
)
from doodle_mvp.context.policy import ActivityLevel


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class FakeMover(QObject):
    arrived = Signal(str)

    def __init__(self):
        super().__init__()
        self._active = False

    @property
    def is_active(self):
        return self._active

    def walk_to(self, target, speed_px_s=56.0):
        self._active = True

    def cancel(self):
        self._active = False

    def shutdown(self):
        self._active = False


class FakeMonitor:
    def start(self):
        pass

    def shutdown(self):
        pass


def make_engine(bus, emitted, **kwargs):
    mover = FakeMover()
    rng = kwargs.pop("rng", random.Random(0))
    clock = kwargs.pop("clock", None)
    scheduler = kwargs.pop("scheduler", None)
    if scheduler is None and clock is not None:
        scheduler = PersonalityScheduler(rng=rng, clock=clock)
    engine = BehaviorEngine(
        bus, rng=rng, scheduler=scheduler, mover=mover,
        monitor=FakeMonitor(), get_pos=lambda: QPoint(500, 500), **kwargs,
    )
    engine.play_requested.connect(lambda n, l, f: emitted.append((n, l, f)))
    engine.start()
    return engine, mover


def test_default_profile_is_calm():
    assert DEFAULT_PROFILE == "calm"
    sched = PersonalityScheduler(rng=random.Random(0))
    assert sched.profile == "calm"


def test_profiles_adjust_weights():
    sched = PersonalityScheduler(rng=random.Random(0))
    calm_playful = sched._weights["playful"]
    sched.set_profile("playful")
    assert sched._weights["playful"] > calm_playful
    sched.set_profile("sleepy")
    assert sched._weights["sleepy"] > sched._weights["playful"]
    sched.set_profile("curious")
    assert sched._weights["notice"] > sched._weights["surprised"]


def test_unknown_profile_rejected():
    sched = PersonalityScheduler(rng=random.Random(0))
    with pytest.raises(ValueError):
        sched.set_profile("feral")
    assert sched.profile == "calm"


def test_playful_picks_more_expressive_than_calm():
    def count(profile):
        clock = FakeClock()
        sched = PersonalityScheduler(rng=random.Random(7), clock=clock)
        sched.set_profile(profile)
        hits = 0
        for _ in range(300):
            pick = sched.pick()
            clock.advance(120.0)
            if pick:
                sched.record(pick)
                if pick in ("playful", "happy", "surprised"):
                    hits += 1
        return hits

    assert count("playful") > count("calm")


def test_interaction_gates_wander_but_not_other_activity():
    clock = FakeClock()
    sched = PersonalityScheduler(rng=random.Random(0), clock=clock)
    sched.note_interaction()
    assert "wander" not in sched.eligible()
    assert "blink" in sched.eligible()
    clock.advance(POST_INTERACTION_QUIET_S + 1.0)
    assert "wander" in sched.eligible()


def test_cooled_down():
    clock = FakeClock()
    sched = PersonalityScheduler(rng=random.Random(0), clock=clock)
    assert sched.cooled_down("happy", 60.0)
    sched.record("happy")
    assert not sched.cooled_down("happy", 60.0)
    clock.advance(61.0)
    assert sched.cooled_down("happy", 60.0)


def test_personality_changed_event_applies_profile(qapp, bus, emitted):
    engine, _ = make_engine(bus, emitted)
    bus.publish(E.PERSONALITY_CHANGED, {"profile": "sleepy"})
    assert engine._scheduler.profile == "sleepy"
    bus.publish(E.PERSONALITY_CHANGED, {"profile": "feral"})
    assert engine._scheduler.profile == "sleepy"  # unchanged
    engine.shutdown()


def test_focus_completed_cheers_once(qapp, bus, emitted):
    clock = FakeClock()
    engine, _ = make_engine(bus, emitted, clock=clock)
    engine.handle_focus_completed({"kind": "focus", "minutes": 25})
    assert emitted[-1] == ("happy", False, 0)
    assert engine.state == REACTING
    engine.on_animation_finished("happy")
    assert engine.state == IDLE
    # second completion within 30 min: no repeat celebration
    n = len(emitted)
    engine.handle_focus_completed({"kind": "focus", "minutes": 25})
    assert len(emitted) == n
    engine.shutdown()


def test_focus_completed_ignored_when_busy_or_break_or_quiet(
        qapp, bus, emitted):
    clock = FakeClock()
    engine, _ = make_engine(bus, emitted, clock=clock)
    engine.handle_focus_completed({"kind": "break", "minutes": 5})
    assert not [e for e in emitted if e[0] == "happy"]
    engine._react("blink")
    engine.handle_focus_completed({"kind": "focus", "minutes": 25})
    assert not [e for e in emitted if e[0] == "happy"]
    engine.on_animation_finished("blink")
    engine._level = ActivityLevel.QUIET
    engine.handle_focus_completed({"kind": "focus", "minutes": 25})
    assert not [e for e in emitted if e[0] == "happy"]
    engine.shutdown()


def test_poke_notes_interaction_for_wander_gating(qapp, bus, emitted):
    clock = FakeClock()
    sched = PersonalityScheduler(rng=random.Random(0), clock=clock)
    engine, _ = make_engine(bus, emitted, scheduler=sched)
    engine.handle_poke()
    assert "wander" not in sched.eligible()
    engine.shutdown()


def test_settings_personality_roundtrip(test_settings):
    settings = test_settings
    assert settings.personality_profile() == "calm"  # default
    settings.set_personality_profile("playful")
    assert settings.personality_profile() == "playful"
    with pytest.raises(ValueError):
        settings.set_personality_profile("feral")
    assert settings.personality_profile() == "playful"  # unchanged


def test_personality_menu_profiles_match_scheduler():
    assert set(PERSONALITY_PROFILES) == {"calm", "playful", "curious", "sleepy"}
