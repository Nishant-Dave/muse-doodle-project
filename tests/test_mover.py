"""Mover tests: easing shape, completion, cancellation, bounds."""

from PySide6.QtCore import QPoint

from doodle_mvp.desktop.mover import ease_in_out_quad, ease_out_cubic, Mover


class FakeElapsed:
    """Deterministic QElapsedTimer replacement."""

    def __init__(self, samples):
        self._samples = list(samples)

    def start(self):
        pass

    def elapsed(self):
        if len(self._samples) > 1:
            return self._samples.pop(0)
        return self._samples[0]


def make_mover(positions=None, duration=400):
    seen = []
    pos = {"at": QPoint(100, 100)}
    mover = Mover(get_pos=lambda: pos["at"], move_to=seen.append)
    mover._clock = FakeElapsed([0, 100, 200, 300, 400, 400])
    return mover, seen, pos


def test_easing_functions_are_well_formed():
    assert ease_out_cubic(0.0) == 0.0
    assert ease_out_cubic(1.0) == 1.0
    assert ease_in_out_quad(0.0) == 0.0
    assert ease_in_out_quad(1.0) == 1.0
    # ease-out: covers more ground early than ease-in-out
    assert ease_out_cubic(0.25) > ease_in_out_quad(0.25)
    assert all(0.0 <= ease_out_cubic(t / 10) <= 1.0 for t in range(11))


def test_glide_reaches_target_and_emits(qapp, emitted):
    mover, seen, _ = make_mover()
    mover.arrived.connect(emitted.append)
    mover.glide_to(QPoint(300, 100), duration_ms=400)
    assert mover.is_active
    for _ in range(6):
        mover._tick()
    assert not mover.is_active
    assert emitted == ["glide"]
    assert seen[-1] == QPoint(300, 100)


def test_glide_decelerates():
    mover, seen, _ = make_mover()
    mover.glide_to(QPoint(500, 100), duration_ms=400)
    for _ in range(5):
        mover._tick()
    steps = [seen[i + 1].x() - seen[i].x() for i in range(len(seen) - 1)]
    assert steps[0] > steps[-1]  # ease-out: early steps larger


def test_wander_uses_gentle_easing_and_completes(qapp, emitted):
    mover, seen, _ = make_mover()
    mover.arrived.connect(emitted.append)
    mover.wander_to(QPoint(200, 200), duration_ms=400)
    for _ in range(6):
        mover._tick()
    assert emitted == ["wander"]
    assert seen[-1] == QPoint(200, 200)


def test_cancel_stops_and_reports(qapp, emitted):
    mover, seen, _ = make_mover()
    mover.arrived.connect(emitted.append)
    mover.glide_to(QPoint(900, 900), duration_ms=400)
    mover._tick()
    mover.cancel()
    assert not mover.is_active
    assert emitted == ["cancelled"]


def test_new_movement_replaces_old(qapp, emitted):
    mover, _, _ = make_mover()
    mover.arrived.connect(emitted.append)
    mover.glide_to(QPoint(900, 900), duration_ms=400)
    mover.wander_to(QPoint(120, 120), duration_ms=400)
    assert mover.kind == "wander"
    for _ in range(6):
        mover._tick()
    assert emitted == ["wander"]  # no stray glide arrival


def test_shutdown_stops_timer(qapp):
    mover, _, _ = make_mover()
    mover.glide_to(QPoint(900, 900), duration_ms=40000)
    assert mover.is_active
    mover.shutdown()
    assert not mover.is_active
