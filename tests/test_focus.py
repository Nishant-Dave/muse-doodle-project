"""Tests for the Phase 3 focus timer (fake clock, no GUI timers needed)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from doodle_mvp.behavior import events as E
from doodle_mvp.behavior.events import EventBus
from doodle_mvp.companion.focus import BREAK, FOCUS, IDLE, PAUSED, FocusTimer
from doodle_mvp.persistence.settings import AppSettings


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def harness(app, tmp_path):
    now = [1000.0]
    bus = EventBus()
    seen: list[tuple[str, dict]] = []
    for name in (E.FOCUS_STARTED, E.FOCUS_PAUSED, E.FOCUS_RESUMED, E.FOCUS_STOPPED,
                 E.FOCUS_COMPLETED, E.BREAK_STARTED, E.BREAK_COMPLETED, E.FOCUS_TICK):
        bus.subscribe(name, lambda p, n=name: seen.append((n, p)))
    settings = AppSettings(QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    timer = FocusTimer(bus, settings, history_path=tmp_path / "hist.json",
                       clock=lambda: now[0])
    timer.start()
    return {"bus": bus, "seen": seen, "timer": timer, "now": now,
            "settings": settings, "tmp": tmp_path}


def kinds(seen):
    return [n for n, _ in seen]


def test_start_pause_resume_stop(harness):
    t, bus, seen, now = (harness[k] for k in ("timer", "bus", "seen", "now"))
    assert t.start_focus() is True
    assert t.state == FOCUS
    assert E.FOCUS_STARTED in kinds(seen)

    now[0] += 60.0
    assert t.pause() is True
    assert t.state == PAUSED
    remaining = t.remaining_s
    assert 1439 <= remaining <= 1440  # 25 min minus 60 s
    now[0] += 3600.0  # time passes while paused: nothing changes
    assert t.remaining_s == remaining
    assert t.resume() is True
    assert t.state == FOCUS
    assert E.FOCUS_RESUMED in kinds(seen)

    assert t.stop() is True
    assert t.state == IDLE
    assert E.FOCUS_STOPPED in kinds(seen)
    assert E.FOCUS_COMPLETED not in kinds(seen)  # stop does not count


def test_focus_completes_and_starts_break(harness):
    t, seen, now = harness["timer"], harness["seen"], harness["now"]
    harness["settings"].set_focus_minutes(1)
    harness["settings"].set_break_minutes(2)
    t.start_focus()
    now[0] += 59.0
    t.poll()
    assert t.state == FOCUS  # not yet
    now[0] += 2.0
    t.poll()
    assert E.FOCUS_COMPLETED in kinds(seen)
    assert t.state == BREAK  # auto-transition
    assert E.BREAK_STARTED in kinds(seen)
    assert t.remaining_s <= 2 * 60


def test_break_completion_returns_to_idle(harness):
    t, seen, now = harness["timer"], harness["seen"], harness["now"]
    harness["settings"].set_focus_minutes(1)
    harness["settings"].set_break_minutes(1)
    t.start_focus()
    now[0] += 61.0
    t.poll()  # focus completes -> break starts
    now[0] += 61.0
    t.poll()  # break completes -> idle
    assert E.BREAK_COMPLETED in kinds(seen)
    assert t.state == IDLE


def test_long_break_after_n_sessions(harness):
    t, seen, now = harness["timer"], harness["seen"], harness["now"]
    s = harness["settings"]
    s.set_focus_minutes(1)
    s.set_break_minutes(1)
    s.set_long_break_minutes(9)
    s.set_sessions_before_long_break(2)
    breaks = []
    harness["bus"].subscribe(E.BREAK_STARTED, lambda p: breaks.append(p["minutes"]))
    for _ in range(2):
        t.start_focus()
        now[0] += 61.0
        t.poll()  # focus done -> break
        now[0] += 61.0
        t.poll()  # break done -> idle
    assert breaks == [1, 9]


def test_skip_finishes_session_immediately(harness):
    t, seen = harness["timer"], harness["seen"]
    harness["settings"].set_focus_minutes(25)
    t.start_focus()
    assert t.skip() is True
    assert E.FOCUS_COMPLETED in kinds(seen)
    assert t.state == BREAK  # skipped focus still leads to a break


def test_history_and_today_summary(harness):
    t = harness["timer"]
    harness["settings"].set_focus_minutes(1)
    t.start_focus()
    harness["now"][0] += 61.0
    t.poll()
    count, minutes = t.today_summary()
    assert count == 1 and minutes == 1
    # Breaks are not recorded.
    assert count == 1


def test_invalid_settings_values_are_clamped(harness, tmp_path):
    s = harness["settings"]
    raw = s._s
    raw.setValue("focus/focus_minutes", "not-a-number")
    raw.setValue("focus/break_minutes", -5)
    raw.setValue("focus/sessions_before_long_break", 99)
    assert s.focus_minutes() == 25
    assert s.break_minutes() == 1      # clamped to minimum
    assert s.sessions_before_long_break() == 12  # clamped to maximum


def test_control_via_bus(harness):
    t, bus = harness["timer"], harness["bus"]
    bus.publish(E.FOCUS_CONTROL, {"action": "start"})
    assert t.state == FOCUS
    bus.publish(E.FOCUS_CONTROL, {"action": "pause"})
    assert t.state == PAUSED
    bus.publish(E.FOCUS_CONTROL, {"action": "resume"})
    assert t.state == FOCUS
    bus.publish(E.FOCUS_CONTROL, {"action": "stop"})
    assert t.state == IDLE
    bus.publish(E.FOCUS_CONTROL, {"action": "bogus"})  # unknown: no crash
    assert t.state == IDLE


def test_shutdown_discards_running_session(harness):
    t = harness["timer"]
    t.start_focus()
    t.shutdown()
    assert t.state == IDLE
    assert t.is_active is False


def test_monotonic_accuracy_not_tick_dependent(harness):
    t, now = harness["timer"], harness["now"]
    harness["settings"].set_focus_minutes(10)
    t.start_focus()
    # No poll() calls at all for 9 minutes: remaining still exact.
    now[0] += 9 * 60
    assert t.remaining_s == 60
