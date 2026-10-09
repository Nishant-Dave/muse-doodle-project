"""Pytest configuration: headless Qt + shared fixtures."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import random

import pytest
from PySide6.QtWidgets import QApplication

from doodle_mvp.behavior.engine import BehaviorEngine
from doodle_mvp.behavior.events import EventBus
from doodle_mvp.character.animation import AnimationPlayer
from doodle_mvp.character.assets import AssetLoader
from doodle_mvp.persistence.settings import AppSettings
from PySide6.QtCore import QSettings


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def bus(qapp):
    return EventBus()


@pytest.fixture()
def assets(qapp):
    return AssetLoader()


@pytest.fixture()
def player(qapp, assets):
    p = AnimationPlayer(assets)
    yield p
    p.shutdown()


@pytest.fixture()
def engine(qapp, bus):
    eng = BehaviorEngine(bus, rng=random.Random(0))
    yield eng
    eng.shutdown()


@pytest.fixture()
def emitted():
    """Collect (signal-args) emissions; use as: sig.connect(emitted.append)."""
    calls: list = []
    return calls


@pytest.fixture()
def test_settings(qapp, tmp_path):
    ini = str(tmp_path / "test_settings.ini")
    return AppSettings(QSettings(ini, QSettings.Format.IniFormat))
