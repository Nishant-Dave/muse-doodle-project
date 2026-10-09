"""CursorMonitor tests: hysteresis, edge-triggering, cooldown."""

from PySide6.QtCore import QPoint

from doodle_mvp.behavior import events as E
from doodle_mvp.desktop.cursor_monitor import CursorMonitor


class FakeClock:
    def __init__(self):
        self.now = 5000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def make_monitor(bus, pos, clock=None, **kwargs):
    holder = {"pos": pos}
    clock = clock or FakeClock()
    mon = CursorMonitor(
        bus,
        anchor=lambda: QPoint(1000, 1000),
        pos_provider=lambda: holder["pos"],
        clock=clock,
        **kwargs,
    )
    return mon, holder, clock


def test_enter_publishes_near_once(qapp, bus, emitted):
    bus.subscribe(E.CURSOR_NEAR, emitted.append)
    mon, holder, _ = make_monitor(bus, QPoint(0, 0))
    holder["pos"] = QPoint(1010, 1010)  # inside 150px radius
    mon.poll()
    mon.poll()  # jitter inside: no repeat
    mon.poll()
    assert len(emitted) == 1
    assert emitted[0]["distance_px"] < 150.0
    mon.shutdown()


def test_exit_publishes_away_once_with_hysteresis(qapp, bus, emitted):
    bus.subscribe(E.CURSOR_NEAR, lambda p: emitted.append(("near", p)))
    bus.subscribe(E.CURSOR_AWAY, lambda p: emitted.append(("away", p)))
    mon, holder, _ = make_monitor(bus, QPoint(1010, 1010))
    mon.poll()  # enter
    holder["pos"] = QPoint(1100, 1000)  # 100px: inside exit radius (200)
    mon.poll()
    assert [e[0] for e in emitted] == ["near"]  # no away yet: hysteresis
    holder["pos"] = QPoint(1250, 1000)  # 250px: beyond exit radius
    mon.poll()
    mon.poll()
    assert [e[0] for e in emitted] == ["near", "away"]
    mon.shutdown()


def test_cooldown_prevents_immediate_retrigger(qapp, bus, emitted):
    bus.subscribe(E.CURSOR_NEAR, emitted.append)
    mon, holder, clock = make_monitor(bus, QPoint(1010, 1010), cooldown_s=20.0)
    mon.poll()  # enter -> published
    holder["pos"] = QPoint(0, 0)
    mon.poll()  # leave
    clock.advance(5)
    holder["pos"] = QPoint(1010, 1010)
    mon.poll()  # re-enter within cooldown -> silent
    assert len(emitted) == 1
    clock.advance(20)
    holder["pos"] = QPoint(0, 0)
    mon.poll()
    holder["pos"] = QPoint(1010, 1010)
    mon.poll()  # cooldown expired -> published again
    assert len(emitted) == 2
    mon.shutdown()


def test_poll_never_raises(qapp, bus):
    def bad_anchor():
        raise RuntimeError("no screen")

    mon = CursorMonitor(bus, anchor=bad_anchor, pos_provider=lambda: QPoint(0, 0))
    mon.poll()  # must not raise
    mon.shutdown()


def test_shutdown_stops_timer(qapp, bus):
    mon, _, _ = make_monitor(bus, QPoint(0, 0))
    mon.start()
    assert mon.is_running
    mon.shutdown()
    assert not mon.is_running
    mon.start()  # idempotent restart
    mon.start()
    mon.shutdown()


def test_dwell_publishes_after_lingering(qapp, bus, emitted):
    bus.subscribe(E.CURSOR_DWELL, lambda p: emitted.append(("dwell", p)))
    mon, holder, clock = make_monitor(bus, QPoint(1010, 1010), dwell_s=2.5)
    mon.poll()  # enter
    clock.advance(1.0)
    mon.poll()
    assert emitted == []
    clock.advance(2.0)
    mon.poll()  # 3.0s inside -> dwell fires once
    assert len(emitted) == 1
    assert emitted[0][1]["side"] == "right"
    clock.advance(5.0)
    mon.poll()  # no repeat while lingering
    assert len(emitted) == 1
    mon.shutdown()


def test_dwell_resets_on_exit(qapp, bus, emitted):
    bus.subscribe(E.CURSOR_DWELL, emitted.append)
    mon, holder, clock = make_monitor(bus, QPoint(1010, 1010), dwell_s=2.5)
    mon.poll()
    holder["pos"] = QPoint(0, 0)
    mon.poll()  # leave before dwell time
    clock.advance(10.0)
    holder["pos"] = QPoint(1010, 1010)
    mon.poll()  # re-enter: dwell timer restarts
    clock.advance(1.0)
    mon.poll()
    assert emitted == []
    mon.shutdown()
