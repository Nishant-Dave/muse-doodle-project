"""Phase 6 tests: physical interaction states, grab, fall, momentum."""

import random

from PySide6.QtCore import QObject, QPoint, Signal

from doodle_mvp.behavior import events as E
from doodle_mvp.behavior.engine import (
    PHYS_DRAGGING,
    PHYS_FALLING,
    PHYS_GLIDING,
    PHYS_GRABBING,
    PHYS_LANDING,
    PHYS_RECOVERING,
    PHYS_RESTING,
    PHYS_TURNING,
    PHYS_WALKING,
    PHYSICAL_TRANSITIONS,
    DRAGGING,
    IDLE,
    MOVING,
    BehaviorEngine,
)


class FakeMover(QObject):
    arrived = Signal(str)

    def __init__(self):
        super().__init__()
        self.calls = []
        self._active = False

    @property
    def is_active(self):
        return self._active

    @property
    def kind(self):
        return self._kind if self._active else ""

    def glide_to(self, target, duration_ms=350):
        self._active = True
        self._kind = "glide"
        self.calls.append(("glide", target, duration_ms))

    def walk_to(self, target, speed_px_s=56.0):
        self._active = True
        self._kind = "walk"
        self.calls.append(("walk", target, speed_px_s))

    def fall_to(self, target, duration_ms=650):
        self._active = True
        self._kind = "fall"
        self.calls.append(("fall", target, duration_ms))

    def cancel(self):
        self._active = False
        self.calls.append(("cancel",))

    def shutdown(self):
        self._active = False


class FakeMonitor:
    def start(self):
        pass

    def shutdown(self):
        pass


def make_engine(bus, emitted, **kwargs):
    mover = FakeMover()
    engine = BehaviorEngine(
        bus, rng=kwargs.pop("rng", random.Random(0)),
        scheduler=kwargs.pop("scheduler", None), mover=mover,
        monitor=FakeMonitor(), get_pos=lambda: QPoint(500, 500), **kwargs,
    )
    engine.play_requested.connect(lambda n, l, f: emitted.append((n, l, f)))
    engine.start()
    return engine, mover


def test_grab_plays_grabbed_then_drag_loop(qapp, bus, emitted):
    engine, _ = make_engine(bus, emitted)
    engine.handle_drag_start()
    assert emitted[-1] == ("grabbed", False, 0)
    assert engine.physical_state == PHYS_GRABBING
    engine.on_animation_finished("grabbed")
    assert emitted[-1] == ("drag", True, 0)
    assert engine.physical_state == PHYS_DRAGGING
    engine.shutdown()


def test_drag_end_during_grabbed_never_starts_drag_loop(qapp, bus, emitted):
    engine, _ = make_engine(bus, emitted)
    engine.handle_drag_start()
    engine.handle_drag_end({"distance_px": 5.0, "duration_s": 0.2,
                            "velocity_x": 0.0, "velocity_y": 0.0})
    assert engine.state == IDLE
    engine.on_animation_finished("grabbed")  # stale: ignored
    assert not [e for e in emitted if e[0] == "drag"]
    assert engine.state == IDLE
    engine.shutdown()


def test_fall_uses_fall_artwork_then_lands(qapp, bus, emitted):
    engine, mover = make_engine(bus, emitted)
    engine.handle_drag_start()
    engine.on_animation_finished("grabbed")
    engine.handle_drag_end({"distance_px": 100.0, "duration_s": 0.3,
                            "velocity_x": 50.0, "velocity_y": 900.0})
    assert ("fall", True, 0) in emitted
    assert engine.physical_state == PHYS_FALLING
    assert mover.calls[-1][0] == "fall"
    engine.on_move_arrived("fall")
    assert ("land", False, 100) in emitted
    assert engine.physical_state == PHYS_LANDING
    engine.on_animation_finished("land")
    assert engine.state == IDLE
    assert engine.physical_state == PHYS_RESTING
    engine.shutdown()


def test_glide_physical_states(qapp, bus, emitted):
    engine, _ = make_engine(bus, emitted)
    engine.handle_drag_start()
    engine.on_animation_finished("grabbed")
    engine.handle_drag_end({"distance_px": 100.0, "duration_s": 0.3,
                            "velocity_x": 600.0, "velocity_y": 50.0})
    assert engine.physical_state == PHYS_GLIDING
    engine.on_move_arrived("glide")
    assert engine.physical_state == PHYS_LANDING
    engine.on_animation_finished("land")
    assert engine.physical_state == PHYS_RESTING
    engine.shutdown()


def test_walk_physical_states(qapp, bus, emitted):
    engine, _ = make_engine(bus, emitted)
    bus.publish(E.WANDER_NOW, {})
    assert engine.physical_state == PHYS_TURNING
    engine.on_animation_finished("walk_start")
    assert engine.physical_state == PHYS_WALKING
    engine.on_move_arrived("walk")
    assert engine.physical_state == PHYS_RECOVERING
    engine.on_animation_finished("walk_stop")
    assert engine.physical_state == PHYS_RESTING
    engine.shutdown()


def test_every_observed_transition_is_valid(qapp, bus, emitted):
    engine, mover = make_engine(bus, emitted)
    seen = [engine.physical_state]
    bus.publish(E.WANDER_NOW, {})
    seen.append(engine.physical_state)
    engine.on_animation_finished("walk_start")
    seen.append(engine.physical_state)
    engine.handle_drag_start()  # grab mid-walk
    seen.append(engine.physical_state)
    engine.on_animation_finished("grabbed")
    seen.append(engine.physical_state)
    engine.handle_drag_end({"distance_px": 100.0, "duration_s": 0.3,
                            "velocity_x": 50.0, "velocity_y": 900.0})
    seen.append(engine.physical_state)
    engine.on_move_arrived("fall")
    seen.append(engine.physical_state)
    engine.on_animation_finished("land")
    seen.append(engine.physical_state)
    for a, b in zip(seen, seen[1:]):
        assert b in PHYSICAL_TRANSITIONS[a], f"{a} -> {b} not allowed"
    engine.shutdown()


def test_grab_interrupts_glide_and_fall(qapp, bus, emitted):
    for vy in (50.0, 900.0):
        engine, mover = make_engine(bus, emitted)
        engine.handle_drag_start()
        engine.on_animation_finished("grabbed")
        engine.handle_drag_end({"distance_px": 100.0, "duration_s": 0.3,
                                "velocity_x": 600.0, "velocity_y": vy})
        assert mover.is_active
        engine.handle_drag_start()  # grab again mid-motion
        assert ("cancel",) in mover.calls
        assert engine.physical_state == PHYS_GRABBING
        assert engine.state == DRAGGING
        engine.shutdown()


def test_slow_release_stays_put(qapp, bus, emitted):
    engine, mover = make_engine(bus, emitted)
    engine.handle_drag_start()
    engine.on_animation_finished("grabbed")
    engine.handle_drag_end({"distance_px": 30.0, "duration_s": 0.5,
                            "velocity_x": 40.0, "velocity_y": 30.0})
    assert mover.calls == []
    assert engine.state == IDLE
    assert engine.physical_state == PHYS_RESTING
    engine.shutdown()


def test_glide_distance_is_bounded(qapp, bus, emitted):
    engine, mover = make_engine(bus, emitted)
    engine.handle_drag_start()
    engine.on_animation_finished("grabbed")
    # extreme fling: still capped at GLIDE_MAX_DIST_PX from release point
    engine.handle_drag_end({"distance_px": 100.0, "duration_s": 0.2,
                            "velocity_x": 5000.0, "velocity_y": 0.0})
    kind, target, _ = mover.calls[-1]
    assert kind == "glide"
    dist = ((target.x() - 500) ** 2 + (target.y() - 500) ** 2) ** 0.5
    assert dist <= 140.0 + 1.0
    engine.shutdown()


def test_fall_only_on_fast_downward_release(qapp, bus, emitted):
    engine, mover = make_engine(bus, emitted)
    # fast but sideways: glide, not fall
    engine.handle_drag_start()
    engine.on_animation_finished("grabbed")
    engine.handle_drag_end({"distance_px": 100.0, "duration_s": 0.2,
                            "velocity_x": 900.0, "velocity_y": 100.0})
    assert mover.calls[-1][0] == "glide"
    engine.shutdown()


def test_shutdown_during_fall_cleans_up(qapp, bus, emitted):
    engine, mover = make_engine(bus, emitted)
    engine.handle_drag_start()
    engine.on_animation_finished("grabbed")
    engine.handle_drag_end({"distance_px": 100.0, "duration_s": 0.3,
                            "velocity_x": 50.0, "velocity_y": 900.0})
    assert mover.is_active
    engine.shutdown()
    assert not mover.is_active
    engine2, _ = make_engine(bus, emitted)
    assert engine2.physical_state == PHYS_RESTING
    engine2.shutdown()


def test_new_physical_animations_in_manifest(qapp, assets):
    assert len(assets.frames_for("fall")) >= 4
    assert assets.spec_for("fall").loop is True
    assert len(assets.frames_for("grabbed")) >= 2
    assert assets.spec_for("grabbed").loop is False


def test_calm_level_excludes_wander_from_scheduler(qapp):
    from doodle_mvp.behavior.scheduler import (
        LEVEL_CALM,
        PersonalityScheduler,
    )
    sched = PersonalityScheduler(rng=random.Random(1))
    sched.set_level(LEVEL_CALM)  # what focus mode drives via the policy
    assert "wander" not in sched.eligible(now=1000.0)
    assert "drowsy" in sched.eligible(now=1000.0)
