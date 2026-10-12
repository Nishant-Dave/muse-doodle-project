"""Phase 4 tests: desktop state monitor lifecycle and signal handling."""

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from doodle_mvp.behavior import events as E
from doodle_mvp.behavior.events import EventBus
from doodle_mvp.context.model import (
    DesktopActivity,
    DoodleInteraction,
    FocusPhase,
)
from doodle_mvp.context.monitor import DesktopStateMonitor
from doodle_mvp.context.store import ContextStore
from doodle_mvp.persistence.settings import AppSettings
from doodle_mvp.platform.adapter import PlatformAdapter


@pytest.fixture
def harness(qapp, tmp_path):
    idle = {"s": 0.0}
    bus = EventBus()
    settings = AppSettings(
        QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    store = ContextStore(bus)
    monitor = DesktopStateMonitor(
        bus, store, settings, PlatformAdapter(),
        idle_provider=lambda: idle["s"])
    monitor.start()
    return {"bus": bus, "settings": settings, "store": store,
            "monitor": monitor, "idle": idle}


def test_active_to_idle_transitions(harness):
    store, monitor, idle = (harness[k] for k in ("store", "monitor", "idle"))
    monitor.sample()
    assert store.current.desktop == DesktopActivity.ACTIVE
    idle["s"] = 61.0
    monitor.sample()
    assert store.current.desktop == DesktopActivity.IDLE_SHORT
    idle["s"] = 301.0
    monitor.sample()
    assert store.current.desktop == DesktopActivity.IDLE_LONG
    idle["s"] = 0.0
    monitor.sample()
    assert store.current.desktop == DesktopActivity.ACTIVE


def test_no_transition_event_when_nothing_changed(harness):
    bus, monitor = harness["bus"], harness["monitor"]
    count = []
    bus.subscribe(E.CONTEXT_CHANGED, lambda _p: count.append(1))
    monitor.sample()
    monitor.sample()
    monitor.sample()
    assert len(count) <= 1  # at most the initial classification


def test_provider_failure_is_safe(harness):
    store, monitor = harness["store"], harness["monitor"]
    monitor._idle_provider = lambda: 1 / 0
    monitor.sample()  # must not raise
    assert store.current.desktop == DesktopActivity.UNKNOWN


def test_focus_events_mirror_into_store(harness):
    bus, store = harness["bus"], harness["store"]
    bus.publish(E.FOCUS_STARTED, {"kind": "focus", "minutes": 25})
    assert store.current.focus == FocusPhase.FOCUSING
    bus.publish(E.FOCUS_PAUSED, {"kind": "focus"})
    assert store.current.focus == FocusPhase.FOCUS_PAUSED
    bus.publish(E.FOCUS_RESUMED, {"kind": "focus"})
    assert store.current.focus == FocusPhase.FOCUSING
    bus.publish(E.FOCUS_STOPPED, {})
    assert store.current.focus == FocusPhase.NONE
    bus.publish(E.BREAK_STARTED, {"minutes": 5})
    assert store.current.focus == FocusPhase.ON_BREAK
    bus.publish(E.BREAK_COMPLETED, {"minutes": 5})
    assert store.current.focus == FocusPhase.NONE


def test_direct_interaction_tracking(harness):
    bus, store = harness["bus"], harness["store"]
    bus.publish(E.DRAG_START, {})
    assert store.current.interaction == DoodleInteraction.DIRECT
    bus.publish(E.DRAG_END, {"distance_px": 1.0, "duration_s": 0.1,
                             "velocity_px_s": 0.0, "dx": 0.0, "dy": 0.0})
    assert store.current.interaction == DoodleInteraction.NONE
    bus.publish(E.POKE, {})
    assert store.current.interaction == DoodleInteraction.DIRECT
    bus.publish(E.MENU_OPENED, {})
    assert store.current.interaction == DoodleInteraction.DIRECT
    bus.publish(E.MENU_CLOSED, {})
    assert store.current.interaction == DoodleInteraction.NONE


def test_disabled_monitoring_stops_sampler(harness):
    settings, store, monitor = (harness[k]
                                for k in ("settings", "store", "monitor"))
    assert monitor._sampler.isActive()
    settings.set_context_enabled(False)
    monitor.refresh_from_settings()
    assert not monitor._sampler.isActive()
    assert store.current.desktop == DesktopActivity.UNKNOWN
    assert store.current.idle_detection_enabled is False
    # Re-enable: sampler restarts, no restart of the app needed.
    settings.set_context_enabled(True)
    monitor.refresh_from_settings()
    assert monitor._sampler.isActive()
    assert store.current.idle_detection_enabled is True


def test_thresholds_refresh_from_settings(harness):
    settings, monitor = harness["settings"], harness["monitor"]
    settings.set_context_idle_short_s(30)
    settings.set_context_idle_long_s(120)
    monitor.refresh_from_settings()
    assert monitor._classifier.short_s == 30
    assert monitor._classifier.long_s == 120


def test_shutdown_stops_timers(harness):
    monitor = harness["monitor"]
    monitor.shutdown()
    assert not monitor._sampler.isActive()
    assert not monitor._direct_reset.isActive()


def test_quiet_mode_reaches_store(harness):
    settings, store, monitor = (harness[k]
                                for k in ("settings", "store", "monitor"))
    settings.set_context_quiet_mode(True)
    monitor.refresh_from_settings()
    assert store.current.quiet is True
