"""Phase 4 tests: context model, store transitions, classifier, policy."""

import pytest

from doodle_mvp.behavior import events as E
from doodle_mvp.behavior.events import EventBus
from doodle_mvp.context.classifier import IdleClassifier
from doodle_mvp.context.model import (
    ContextSnapshot,
    DesktopActivity,
    DoodleInteraction,
    FocusPhase,
)
from doodle_mvp.context.policy import ActivityLevel, PersonalityPolicy
from doodle_mvp.context.store import ContextStore


def test_snapshot_defaults():
    s = ContextSnapshot()
    assert s.desktop == DesktopActivity.UNKNOWN
    assert s.focus == FocusPhase.NONE
    assert s.interaction == DoodleInteraction.NONE
    assert s.quiet is False


def test_store_emits_only_on_meaningful_change(qapp):
    bus = EventBus()
    transitions = []
    bus.subscribe(E.CONTEXT_CHANGED, lambda p: transitions.append(p))
    store = ContextStore(bus)
    # Same values: silent.
    assert store.update(desktop=DesktopActivity.ACTIVE) is True
    assert store.update(desktop=DesktopActivity.ACTIVE) is False
    assert len(transitions) == 1
    assert transitions[0]["current"]["desktop"] == "active"
    assert transitions[0]["previous"]["desktop"] == "unknown"
    # Multiple fields at once: one event.
    assert store.update(desktop=DesktopActivity.IDLE_SHORT, quiet=True) is True
    assert len(transitions) == 2


def test_store_rejects_unknown_fields(qapp):
    store = ContextStore(EventBus())
    with pytest.raises(ValueError):
        store.update(mood="happy")


def test_classifier_thresholds_and_hysteresis():
    c = IdleClassifier(short_s=60, long_s=300, rearm_s=10)
    assert c.classify(0) == DesktopActivity.ACTIVE
    assert c.classify(59) == DesktopActivity.ACTIVE
    assert c.classify(60) == DesktopActivity.IDLE_SHORT
    # Hysteresis: a 5s nudge below the threshold does not exit idle.
    assert c.classify(55) == DesktopActivity.IDLE_SHORT
    assert c.classify(49) == DesktopActivity.ACTIVE  # 60-10-1
    assert c.classify(300) == DesktopActivity.IDLE_LONG
    assert c.classify(295) == DesktopActivity.IDLE_LONG  # rearm band
    assert c.classify(289) == DesktopActivity.IDLE_SHORT  # 300-10-1
    assert c.classify(None) == DesktopActivity.UNKNOWN
    assert c.classify(-5) == DesktopActivity.UNKNOWN


def test_classifier_rejects_bad_thresholds():
    with pytest.raises(ValueError):
        IdleClassifier(short_s=300, long_s=60)
    c = IdleClassifier()
    with pytest.raises(ValueError):
        c.update_thresholds(100, 100)


def snap(**kw):
    return ContextSnapshot(**kw)


def test_policy_precedence():
    p = PersonalityPolicy()
    # Direct interaction beats everything, even quiet+focus.
    s = snap(interaction=DoodleInteraction.DIRECT, quiet=True,
             focus=FocusPhase.FOCUSING, desktop=DesktopActivity.IDLE_LONG)
    assert p.decide(s).level == ActivityLevel.NORMAL
    # Quiet beats focus.
    s = snap(quiet=True, focus=FocusPhase.FOCUSING)
    d = p.decide(s)
    assert d.level == ActivityLevel.QUIET and d.reason == "quiet mode"
    # Focus beats idle.
    s = snap(focus=FocusPhase.FOCUSING, desktop=DesktopActivity.IDLE_LONG)
    assert p.decide(s).level == ActivityLevel.CALM
    s = snap(focus=FocusPhase.FOCUS_PAUSED, desktop=DesktopActivity.ACTIVE)
    assert p.decide(s).level == ActivityLevel.CALM
    # Break is relaxed.
    s = snap(focus=FocusPhase.ON_BREAK, desktop=DesktopActivity.IDLE_SHORT)
    assert p.decide(s).level == ActivityLevel.NORMAL
    # Idle levels.
    assert p.decide(snap(desktop=DesktopActivity.IDLE_SHORT)).level == ActivityLevel.CALM
    assert p.decide(snap(desktop=DesktopActivity.IDLE_LONG)).level == ActivityLevel.REST
    assert p.decide(snap(desktop=DesktopActivity.ACTIVE)).level == ActivityLevel.NORMAL
    # Unknown signal: ordinary behavior, never a guess.
    assert p.decide(snap(desktop=DesktopActivity.UNKNOWN)).level == ActivityLevel.NORMAL


def test_policy_adaptive_off():
    p = PersonalityPolicy(adaptive=False)
    s = snap(quiet=True, focus=FocusPhase.FOCUSING,
             desktop=DesktopActivity.IDLE_LONG)
    assert p.decide(s).level == ActivityLevel.NORMAL


def test_policy_decisions_are_deterministic():
    p = PersonalityPolicy()
    s = snap(desktop=DesktopActivity.IDLE_LONG, quiet=False)
    assert p.decide(s) == p.decide(s)
