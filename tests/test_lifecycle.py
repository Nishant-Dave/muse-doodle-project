"""Lifecycle tests: startup, shutdown, no duplicated handlers."""

from doodle_mvp.app.application import DoodleApplication
from doodle_mvp.behavior import events as E


def test_application_starts_with_idle_animation(qapp, emitted):
    app = DoodleApplication([])
    try:
        assert app.player.current_animation == "idle"
        assert app.player.is_playing
        assert app.engine.state == "idle"
        assert app.window is not None
    finally:
        app.shutdown()


def test_shutdown_stops_timers_and_is_idempotent(qapp):
    app = DoodleApplication([])
    app.self_check()  # includes shutdown
    assert not app.player.is_playing
    assert not app.engine._schedule_timer.isActive()
    app.shutdown()  # second call must be safe
    assert not app.player.is_playing


def test_self_check_returns_zero(qapp):
    app = DoodleApplication([])
    assert app.self_check() == 0


def test_repeated_init_does_not_duplicate_handlers(qapp, emitted):
    app = DoodleApplication([])
    try:
        app.bus.subscribe(E.POKE, emitted.append)
        app.bus.subscribe(E.POKE, emitted.append)  # same slot twice
        app.bus.publish(E.POKE)
        assert len(emitted) == 1
    finally:
        app.shutdown()


def test_quit_path_publishes_app_exiting(qapp, emitted):
    app = DoodleApplication([])
    try:
        app.bus.subscribe(E.APP_EXITING, emitted.append)
        app.shutdown()
        assert len(emitted) == 1
    finally:
        app.shutdown()


def test_animations_disabled_at_startup_shows_static(qapp, tmp_path):
    from PySide6.QtCore import QSettings

    from doodle_mvp.persistence.settings import AppSettings

    ini = str(tmp_path / "disabled.ini")
    settings = AppSettings(QSettings(ini, QSettings.Format.IniFormat))
    settings.set_animations_enabled(False)
    app = DoodleApplication([], settings=settings)
    try:
        assert not app.player.is_playing
        assert app.player.current_animation == "idle"
        assert not app.engine._schedule_timer.isActive()
    finally:
        app.shutdown()
