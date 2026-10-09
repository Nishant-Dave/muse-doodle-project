"""Preference tests: defaults, persistence, invalid values."""

from PySide6.QtCore import QPoint


def test_defaults_are_sensible(test_settings):
    assert test_settings.animations_enabled() is True
    assert test_settings.get_position() is None


def test_position_roundtrip(test_settings):
    test_settings.set_position(QPoint(320, 240))
    assert test_settings.get_position() == QPoint(320, 240)


def test_invalid_position_returns_none(test_settings):
    test_settings._s.setValue("window/pos", "not-a-position")
    assert test_settings.get_position() is None
    test_settings._s.setValue("window/pos", "12")
    assert test_settings.get_position() is None


def test_animations_toggle_roundtrip(test_settings):
    test_settings.set_animations_enabled(False)
    assert test_settings.animations_enabled() is False
    test_settings.set_animations_enabled(True)
    assert test_settings.animations_enabled() is True


def test_invalid_animations_value_falls_back_to_true(test_settings):
    test_settings._s.setValue("behavior/animations_enabled", "maybe")
    assert test_settings.animations_enabled() is True


def test_values_survive_reload(qapp, tmp_path):
    from PySide6.QtCore import QSettings

    from doodle_mvp.persistence.settings import AppSettings

    ini = str(tmp_path / "reload.ini")
    first = AppSettings(QSettings(ini, QSettings.Format.IniFormat))
    first.set_position(QPoint(111, 222))
    first.set_animations_enabled(False)
    first.sync()

    second = AppSettings(QSettings(ini, QSettings.Format.IniFormat))
    assert second.get_position() == QPoint(111, 222)
    assert second.animations_enabled() is False
