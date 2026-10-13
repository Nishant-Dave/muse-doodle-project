"""Phase 5 tests: coherent animation sequences (drowsy, notice)."""

import random

from PySide6.QtCore import QObject, QPoint, Signal

from doodle_mvp.behavior import events as E
from doodle_mvp.behavior.engine import IDLE, REACTING, SEQUENCES, BehaviorEngine
from doodle_mvp.behavior.scheduler import (
    LEVEL_CALM,
    LEVEL_REST,
    PersonalityScheduler,
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

    def walk_to(self, target, speed_px_s=56.0):
        self._active = True
        self.calls.append(("walk", target, speed_px_s))

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
    rng = kwargs.pop("rng", random.Random(0))
    scheduler = kwargs.pop("scheduler", None)
    engine = BehaviorEngine(
        bus, rng=rng, scheduler=scheduler, mover=mover,
        monitor=FakeMonitor(), get_pos=lambda: QPoint(500, 500), **kwargs,
    )
    engine.play_requested.connect(lambda n, l, f: emitted.append((n, l, f)))
    engine.start()
    return engine, mover


def test_sequences_defined():
    assert SEQUENCES["drowsy"] == ["yawn", "sleepy"]
    assert SEQUENCES["notice"][0] == "curious"


def test_drowsy_plays_yawn_then_sleepy_then_idle(qapp, bus, emitted):
    engine, _ = make_engine(bus, emitted)
    engine._react_sequence("drowsy")
    assert engine.state == REACTING
    assert emitted[-1] == ("yawn", False, 0)
    engine.on_animation_finished("yawn")
    assert emitted[-1] == ("sleepy", False, 0)
    assert engine.state == REACTING
    engine.on_animation_finished("sleepy")
    assert emitted[-1] == ("idle", True, 0)
    assert engine.state == IDLE
    engine.shutdown()


def test_notice_picks_a_gaze_side(qapp, bus, emitted):
    seen = set()
    for seed in range(20):
        engine, _ = make_engine(bus, emitted, rng=random.Random(seed))
        emitted.clear()
        engine._react_sequence("notice")
        assert emitted[-1] == ("curious", False, 0)
        engine.on_animation_finished("curious")
        name, loop, _ = emitted[-1]
        assert name in {"gaze_left", "gaze_right", "gaze_up"}
        assert loop is False
        seen.add(name)
        engine.shutdown()
    assert len(seen) >= 2  # not always the same side


def test_sequence_interrupted_by_poke(qapp, bus, emitted):
    engine, _ = make_engine(bus, emitted)
    engine._react_sequence("drowsy")
    engine.handle_poke()  # mid-yawn
    assert emitted[-1] == ("playful", False, 0)
    engine.on_animation_finished("playful")
    assert engine.state == IDLE
    # sleepy never played: the queue was discarded
    assert not [e for e in emitted if e[0] == "sleepy"]
    engine.shutdown()


def test_sequence_interrupted_by_drag(qapp, bus, emitted):
    engine, _ = make_engine(bus, emitted)
    engine._react_sequence("notice")
    engine.handle_drag_start()
    assert engine._seq_queue == []
    engine.on_animation_finished("curious")  # stale: ignored
    assert engine.state == "dragging"
    engine.shutdown()


def test_unknown_sequence_falls_back_to_idle(qapp, bus, emitted):
    engine, _ = make_engine(bus, emitted)
    engine._react_sequence("nope")
    assert engine.state == IDLE
    engine.shutdown()


def test_scheduler_offers_new_activities(qapp):
    sched = PersonalityScheduler(rng=random.Random(3))
    seen = set()
    now = 1000.0
    for _ in range(400):
        pick = sched.pick(now=now)
        now += 120.0
        if pick:
            seen.add(pick)
            sched.record(pick)
    for name in ("blink_double", "gaze_up", "drowsy", "notice"):
        assert name in seen, f"{name} never picked"


def test_calm_level_allows_new_activities_but_rest_does_not(qapp):
    sched = PersonalityScheduler(rng=random.Random(1))
    sched.set_level(LEVEL_CALM)
    assert set(sched.eligible(now=1000.0)) >= {
        "blink", "blink_double", "gaze_up", "drowsy", "notice"}
    sched.set_level(LEVEL_REST)
    rest_ok = set(sched.eligible(now=1000.0))
    assert "drowsy" not in rest_ok
    assert "notice" not in rest_ok


def test_new_animations_exist_in_manifest(qapp, assets):
    for name in ("blink_double", "gaze_up"):
        frames = assets.frames_for(name)
        assert len(frames) >= 4
        assert assets.spec_for(name).fps > 0
        assert assets.spec_for(name).loop is False
