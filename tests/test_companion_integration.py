"""Phase 3 integration: events -> behavior engine -> animations."""

import random

from PySide6.QtCore import QObject, QPoint, Signal
from PySide6.QtWidgets import QApplication

from doodle_mvp.behavior import events as E
from doodle_mvp.behavior.engine import IDLE, REACTING, BehaviorEngine
from doodle_mvp.behavior.events import EventBus
from doodle_mvp.companion.focus import FOCUS, FocusTimer
from doodle_mvp.companion.reminders import ReminderScheduler, ReminderStore
from doodle_mvp.persistence.settings import AppSettings


class FakeMover(QObject):
    arrived = Signal(str)

    def __init__(self):
        super().__init__()
        self._active = False

    @property
    def is_active(self):
        return self._active

    def glide_to(self, target, duration_ms=350):
        self._active = True

    def wander_to(self, target, duration_ms=1200):
        self._active = True

    def fall_to(self, target, duration_ms=650):
        self._active = True

    def cancel(self):
        self._active = False

    def shutdown(self):
        self._active = False


def make(bus, emitted, tmp_path, now):
    from PySide6.QtCore import QSettings
    settings = AppSettings(QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    engine = BehaviorEngine(
        bus, rng=random.Random(0), mover=FakeMover(),
        get_pos=lambda: QPoint(500, 500),
    )
    engine.play_requested.connect(lambda n, l, f: emitted.append((n, l, f)))
    engine.start()
    timer = FocusTimer(bus, settings, history_path=tmp_path / "hist.json",
                       clock=lambda: now[0])
    timer.start()
    return engine, timer


def test_focus_started_calms_engine(qapp, tmp_path):
    bus, emitted, now = EventBus(), [], [0.0]
    engine, timer = make(bus, emitted, tmp_path, now)
    timer.start_focus()
    assert engine.focus_mode is True
    calm = engine._scheduler.eligible(now=0.0)
    assert "wander" not in calm and "happy" not in calm and "blink" in calm
    assert ("happy", False, 0) in emitted  # brief encouragement
    engine.on_animation_finished("happy")
    assert engine._state == IDLE  # returns to normal behavior


def test_focus_completed_celebrates_and_uncalms(qapp, tmp_path):
    bus, emitted, now = EventBus(), [], [0.0]
    engine, timer = make(bus, emitted, tmp_path, now)
    timer._settings.set_focus_minutes(1)
    timer.start_focus()
    now[0] += 61.0
    timer.poll()
    assert engine.focus_mode is False
    assert ("happy", False, 0) in emitted  # celebration
    # Scheduler is back to the full profile.
    assert "wander" in engine._scheduler.eligible(now=0.0)


def test_reminder_due_reacts_subtly_during_focus(qapp, tmp_path):
    bus, emitted, now = EventBus(), [], [0.0]
    engine, timer = make(bus, emitted, tmp_path, now)
    timer.start_focus()
    engine.on_animation_finished("happy")  # encouragement done -> back to idle
    emitted.clear()
    bus.publish(E.REMINDER_DUE, {"id": "x", "title": "Stand up", "overdue": False})
    assert ("blink", False, 0) in emitted  # subtle during focus
    engine.on_animation_finished("blink")
    assert engine._state == IDLE  # returns to previous behavior


def test_reminder_due_cheerful_outside_focus(qapp, tmp_path):
    bus, emitted, now = EventBus(), [], [0.0]
    engine, timer = make(bus, emitted, tmp_path, now)
    bus.publish(E.REMINDER_DUE, {"id": "x", "title": "Stand up", "overdue": False})
    assert ("happy", False, 0) in emitted
    assert engine.focus_mode is False


def test_reminder_ignored_while_dragging(qapp, tmp_path):
    bus, emitted, now = EventBus(), [], [0.0]
    engine, timer = make(bus, emitted, tmp_path, now)
    engine.handle_drag_start()
    bus.publish(E.REMINDER_DUE, {"id": "x", "title": "Hi", "overdue": False})
    assert emitted == [("idle", True, 0)] or not any(
        n in ("happy", "blink") for n, _, _ in emitted)


def test_scheduler_shutdown_stops_polling(qapp, tmp_path):
    app = QApplication.instance()
    bus = EventBus()
    store = ReminderStore(path=tmp_path / "r.json")
    sched = ReminderScheduler(bus, store, clock=lambda: 0.0, interval_ms=50)
    sched.start()
    assert sched._timer.isActive()
    sched.shutdown()
    assert not sched._timer.isActive()
    bus.publish(E.APP_EXITING)
    assert not sched._timer.isActive()


def test_focus_stopped_clears_calm(qapp, tmp_path):
    bus, emitted, now = EventBus(), [], [0.0]
    engine, timer = make(bus, emitted, tmp_path, now)
    timer.start_focus()
    assert engine.focus_mode is True
    timer.stop()
    assert engine.focus_mode is False
