"""Phase 2B behavior tests: cursor, glide, wander, facing, priorities."""

import random

from PySide6.QtCore import QObject, QPoint, Signal

from doodle_mvp.behavior import events as E
from doodle_mvp.behavior.engine import IDLE, MOVING, REACTING, BehaviorEngine
from doodle_mvp.behavior.scheduler import PersonalityScheduler


class FakeMover(QObject):
    arrived = Signal(str)

    def __init__(self):
        super().__init__()
        self.calls = []
        self._active = False
        self.shutdown_called = False

    @property
    def is_active(self):
        return self._active

    def glide_to(self, target, duration_ms=350):
        self._active = True
        self.calls.append(("glide", target, duration_ms))

    def wander_to(self, target, duration_ms=1200):
        self._active = True
        self.calls.append(("wander", target, duration_ms))

    def cancel(self):
        self._active = False
        self.calls.append(("cancel",))

    def shutdown(self):
        self._active = False
        self.shutdown_called = True


class FakeMonitor:
    def __init__(self):
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True
        self.stopped = False

    def shutdown(self):
        self.stopped = True
        self.started = False


class ScriptedRng:
    def __init__(self, values):
        self._v = list(values)

    def random(self):
        return self._v.pop(0)

    def uniform(self, a, b):
        return a + (b - a) * self.random()


def make_engine(bus, emitted, **kwargs):
    mover = FakeMover()
    monitor = FakeMonitor()
    rng = kwargs.pop("rng", random.Random(0))
    scheduler = kwargs.pop("scheduler", None)
    engine = BehaviorEngine(
        bus, rng=rng, scheduler=scheduler, mover=mover, monitor=monitor,
        get_pos=lambda: QPoint(500, 500), **kwargs,
    )
    engine.play_requested.connect(lambda n, l: emitted.append((n, l)))
    engine.facing_changed.connect(lambda f: emitted.append(("facing", f)))
    engine.start()
    return engine, mover, monitor


def test_cursor_near_triggers_curious_once(qapp, bus, emitted):
    engine, _, _ = make_engine(bus, emitted)
    bus.publish(E.CURSOR_NEAR, {"distance_px": 100.0})
    assert emitted[-1] == ("curious", False)
    assert engine.state == REACTING
    engine.shutdown()


def test_cursor_near_ignored_while_dragging(qapp, bus, emitted):
    engine, _, _ = make_engine(bus, emitted)
    engine.handle_drag_start()
    bus.publish(E.CURSOR_NEAR, {"distance_px": 50.0})
    assert emitted[-1] == ("drag", True)
    engine.shutdown()


def test_fast_drag_release_glides_with_bounded_target(qapp, bus, emitted):
    engine, mover, _ = make_engine(bus, emitted)
    engine.handle_drag_start()
    engine.handle_drag_end({
        "distance_px": 40.0, "duration_s": 0.3,
        "velocity_x": 1000.0, "velocity_y": 0.0,
    })
    assert engine.state == MOVING
    kind, target, duration = mover.calls[-1]
    assert kind == "glide"
    # speed 1000 * 0.22 = 220 -> clamped to 140px max
    assert target == QPoint(640, 500)
    assert duration == 350
    mover.arrived.emit("glide")
    assert engine.state == IDLE
    engine.shutdown()


def test_slow_drag_release_skips_glide(qapp, bus, emitted):
    engine, mover, _ = make_engine(bus, emitted)
    engine.handle_drag_start()
    engine.handle_drag_end({
        "distance_px": 40.0, "duration_s": 0.3,
        "velocity_x": 50.0, "velocity_y": 0.0,
    })
    assert mover.calls == []
    assert engine.state == IDLE
    engine.shutdown()


def test_momentum_toggle_disables_glide(qapp, bus, emitted):
    engine, mover, _ = make_engine(bus, emitted)
    bus.publish(E.MOMENTUM_TOGGLED, {"enabled": False})
    engine.handle_drag_start()
    engine.handle_drag_end({
        "distance_px": 40.0, "duration_s": 0.3,
        "velocity_x": 2000.0, "velocity_y": 0.0,
    })
    assert mover.calls == []
    assert engine.state == IDLE
    engine.shutdown()


def test_poke_cancels_wander(qapp, bus, emitted):
    engine, mover, _ = make_engine(bus, emitted)
    assert engine._start_wander() is True
    assert engine.state == MOVING
    engine.handle_poke()
    assert ("cancel",) in mover.calls
    assert emitted[-1] == ("playful", False)
    assert engine.state == REACTING
    engine.shutdown()


def test_wander_sets_facing_and_returns_to_idle(qapp, bus, emitted):
    # schedule delay, idle-check (proceed), roll (wander), dx, dy
    rng = ScriptedRng([0.9, 0.5, 0.0, 0.9, 0.1])
    sched = PersonalityScheduler(rng=rng, weights={"wander": 1.0})
    engine, mover, _ = make_engine(bus, emitted, rng=rng, scheduler=sched)
    engine._on_schedule_timeout()
    assert engine.state == MOVING
    assert ("facing", "right") in emitted
    assert mover.calls[-1][0] == "wander"
    mover.arrived.emit("wander")
    assert engine.state == IDLE
    engine.shutdown()


def test_wander_disabled_by_toggle(qapp, bus, emitted):
    engine, mover, _ = make_engine(bus, emitted)
    bus.publish(E.WANDER_TOGGLED, {"enabled": False})
    assert engine._start_wander() is False
    assert mover.calls == []
    engine.shutdown()


def test_cancelled_move_does_not_change_state(qapp, bus, emitted):
    engine, mover, _ = make_engine(bus, emitted)
    assert engine._start_wander() is True
    engine.handle_drag_start()  # drag preempts the wander
    assert ("cancel",) in mover.calls
    assert engine.state == "dragging"
    engine.shutdown()


def test_idle_animation_is_not_restarted(qapp, bus, emitted):
    engine, _, _ = make_engine(bus, emitted)
    idles = [e for e in emitted if e == ("idle", True)]
    assert len(idles) == 1
    engine._to_idle()
    engine._to_idle()
    assert [e for e in emitted if e == ("idle", True)] == idles
    engine.shutdown()


def test_shutdown_stops_mover_and_monitor(qapp, bus, emitted):
    engine, mover, monitor = make_engine(bus, emitted)
    assert monitor.started
    engine.handle_drag_start()
    engine.shutdown()
    assert mover.shutdown_called
    assert monitor.stopped
    assert not engine._schedule_timer.isActive()


def test_mood_during_wander_reacts_and_cancels_move(qapp, bus, emitted):
    engine, mover, _ = make_engine(bus, emitted, rng=random.Random(42))
    assert engine._start_wander() is True
    bus.publish(E.MOOD_SELECTED, {"mood": "happy"})
    assert ("cancel",) in mover.calls
    assert emitted[-1] == ("happy", False)
    assert engine.state == REACTING
    engine.shutdown()
