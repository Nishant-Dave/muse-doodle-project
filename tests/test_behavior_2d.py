"""Phase 2D tests: gravity fall, come-here, wander-now, cursor dwell."""

import random

from PySide6.QtCore import QObject, QPoint, Signal

from doodle_mvp.behavior import events as E
from doodle_mvp.behavior.engine import IDLE, MOVING, REACTING, BehaviorEngine
from doodle_mvp.desktop.mover import Mover, ease_in_quad


class FakeMover(QObject):
    arrived = Signal(str)

    def __init__(self):
        super().__init__()
        self.calls = []
        self._active = False

    @property
    def is_active(self):
        return self._active

    def glide_to(self, target, duration_ms=350):
        self._active = True
        self.calls.append(("glide", target, duration_ms))

    def wander_to(self, target, duration_ms=1200):
        self._active = True
        self.calls.append(("wander", target, duration_ms))

    def fall_to(self, target, duration_ms=650):
        self._active = True
        self.calls.append(("fall", target, duration_ms))

    def cancel(self):
        self._active = False
        self.calls.append(("cancel",))

    def shutdown(self):
        self._active = False


def make_engine(bus, emitted, **kwargs):
    mover = FakeMover()
    engine = BehaviorEngine(
        bus, rng=kwargs.pop("rng", random.Random(0)),
        mover=mover, get_pos=lambda: QPoint(500, 500), **kwargs,
    )
    engine.play_requested.connect(lambda n, l, f: emitted.append((n, l, f)))
    engine.facing_changed.connect(lambda f: emitted.append(("facing", f)))
    engine.start()
    return engine, mover


def test_downward_throw_falls_with_gravity(qapp, bus, emitted):
    engine, mover = make_engine(bus, emitted)
    engine.handle_drag_start()
    engine.handle_drag_end({
        "distance_px": 40.0, "duration_s": 0.3,
        "velocity_x": 100.0, "velocity_y": 1000.0,
    })
    assert engine.state == MOVING
    kind, target, duration = mover.calls[-1]
    assert kind == "fall"
    assert target.y() > 500  # headed for the bottom of the screen
    assert abs(target.x() - 500) <= 80  # slight horizontal drift only
    assert duration == 650
    assert ("surprised", True, 0) in emitted  # wide-eyed fall, looping
    mover.arrived.emit("fall")
    assert emitted[-1] == ("land", False, 100)  # settle on landing
    engine.on_animation_finished("land")
    assert engine.state == IDLE
    engine.shutdown()


def test_sideways_throw_still_glides(qapp, bus, emitted):
    engine, mover = make_engine(bus, emitted)
    engine.handle_drag_start()
    engine.handle_drag_end({
        "distance_px": 40.0, "duration_s": 0.3,
        "velocity_x": 1500.0, "velocity_y": 100.0,
    })
    assert mover.calls[-1][0] == "glide"
    engine.shutdown()


def test_dizzy_takes_precedence_over_fall(qapp, bus, emitted):
    engine, mover = make_engine(bus, emitted)
    engine.handle_drag_start()
    engine.handle_drag_end({
        "distance_px": 200.0, "duration_s": 0.3,
        "velocity_x": 0.0, "velocity_y": 2000.0,
    })
    assert emitted[-1] == ("dizzy", False, 0)
    assert mover.calls == []
    engine.shutdown()


def test_fall_disabled_with_momentum_toggle(qapp, bus, emitted):
    engine, mover = make_engine(bus, emitted)
    bus.publish(E.MOMENTUM_TOGGLED, {"enabled": False})
    engine.handle_drag_start()
    engine.handle_drag_end({
        "distance_px": 40.0, "duration_s": 0.3,
        "velocity_x": 0.0, "velocity_y": 2000.0,
    })
    assert mover.calls == []
    assert engine.state == IDLE
    engine.shutdown()


def test_fall_accelerates():
    assert ease_in_quad(0.0) == 0.0
    assert ease_in_quad(1.0) == 1.0
    assert ease_in_quad(0.75) - ease_in_quad(0.5) > ease_in_quad(0.25) - ease_in_quad(0.0)


def test_real_mover_fall_reaches_target(qapp, emitted):
    seen = []
    mover = Mover(get_pos=lambda: QPoint(500, 100), move_to=seen.append)
    mover.arrived.connect(emitted.append)

    class Steps:
        def __init__(self):
            self.t = [0, 160, 320, 480, 650, 650]
        def start(self): pass
        def elapsed(self):
            return self.t.pop(0) if len(self.t) > 1 else self.t[0]
    mover._clock = Steps()
    mover.fall_to(QPoint(520, 900), duration_ms=650)
    for _ in range(6):
        mover._tick()
    assert emitted == ["fall"]
    assert seen[-1] == QPoint(520, 900)
    gaps = [seen[i + 1].y() - seen[i].y() for i in range(len(seen) - 1)]
    assert gaps[-1] > gaps[0]  # accelerating: later gaps larger


def test_come_here_walks_beside_cursor(qapp, bus, emitted):
    engine, mover = make_engine(bus, emitted)
    bus.publish(E.COME_HERE, {"x": 1000, "y": 600})
    assert engine.state == MOVING
    kind, target, duration = mover.calls[-1]
    assert kind == "wander"  # directed walk reuses the walk machinery
    assert target == QPoint(820, 600)  # 180px beside the cursor
    assert ("facing", "right") in emitted
    assert ("walk", True, 150) in emitted
    mover.arrived.emit("wander")
    engine.on_animation_finished("land")
    assert engine.state == IDLE
    engine.shutdown()


def test_come_here_too_close_just_looks(qapp, bus, emitted):
    engine, mover = make_engine(bus, emitted)
    bus.publish(E.COME_HERE, {"x": 650, "y": 500})  # target (470,500): dist 30 < 80
    assert mover.calls == []
    assert emitted[-1] == ("gaze_right", False, 0)
    assert engine.state == REACTING
    engine.shutdown()


def test_come_here_ignored_while_dragging(qapp, bus, emitted):
    engine, mover = make_engine(bus, emitted)
    engine.handle_drag_start()
    bus.publish(E.COME_HERE, {"x": 1000, "y": 600})
    assert mover.calls == []
    assert emitted[-1] == ("drag", True, 0)
    engine.shutdown()


def test_wander_now_triggers_walk(qapp, bus, emitted):
    engine, mover = make_engine(bus, emitted)
    bus.publish(E.WANDER_NOW, {})
    assert engine.state == MOVING
    assert mover.calls[-1][0] == "wander"
    engine.shutdown()


def test_wander_now_ignored_when_busy(qapp, bus, emitted):
    engine, mover = make_engine(bus, emitted)
    engine.handle_poke()
    bus.publish(E.WANDER_NOW, {})
    assert mover.calls == []
    assert emitted[-1] == ("playful", False, 0)
    engine.shutdown()


def test_dwell_turns_to_face_cursor(qapp, bus, emitted):
    engine, _ = make_engine(bus, emitted)
    engine._set_facing("right")
    emitted.clear()
    bus.publish(E.CURSOR_DWELL, {"side": "left"})
    assert ("facing", "left") in emitted
    assert engine.state == IDLE  # no animation change, just the turn
    engine.shutdown()


def test_dwell_ignored_when_moving(qapp, bus, emitted):
    engine, mover = make_engine(bus, emitted)
    assert engine._start_wander() is True
    emitted.clear()
    bus.publish(E.CURSOR_DWELL, {"side": "left"})
    assert ("facing", "left") not in emitted
    engine.shutdown()
