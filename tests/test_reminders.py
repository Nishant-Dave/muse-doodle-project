"""Tests for the Phase 3 reminder store + scheduler."""

from __future__ import annotations

import json

import pytest
from PySide6.QtWidgets import QApplication

from doodle_mvp.behavior import events as E
from doodle_mvp.behavior.events import EventBus
from doodle_mvp.companion.reminders import ReminderScheduler, ReminderStore


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def store(app, tmp_path):
    return ReminderStore(path=tmp_path / "reminders.json")


def test_add_and_upcoming_sorted(store):
    r1 = store.add("Later", due_at=2000.0)
    r2 = store.add("Sooner", due_at=1000.0)
    upcoming = store.upcoming(now=500.0)
    assert [r["id"] for r in upcoming] == [r2["id"], r1["id"]]
    assert store.get(r1["id"])["title"] == "Later"


def test_update_and_remove(store):
    r = store.add("Original", due_at=1000.0)
    updated = store.update(r["id"], title="Edited", enabled=False)
    assert updated["title"] == "Edited"
    assert updated["enabled"] is False
    assert store.upcoming(now=0.0) == []  # disabled -> not upcoming
    assert store.remove(r["id"]) is True
    assert store.get(r["id"]) is None
    assert store.remove("missing") is False


def test_due_fires_once_and_persists(app, tmp_path):
    path = tmp_path / "reminders.json"
    bus = EventBus()
    fired: list[dict] = []
    bus.subscribe(E.REMINDER_DUE, lambda p: fired.append(p))
    store = ReminderStore(path=path)
    sched = ReminderScheduler(bus, store, clock=lambda: 1000.0)
    r = store.add("Due now", due_at=990.0)
    first = sched.check_due()
    assert len(first) == 1
    assert fired[0]["id"] == r["id"]
    assert fired[0]["overdue"] is True  # 10 s past due
    # Second check (simulating a restart with a fresh scheduler) never refires.
    store2 = ReminderStore(path=path)
    sched2 = ReminderScheduler(bus, store2, clock=lambda: 2000.0)
    assert sched2.check_due() == []
    assert len(fired) == 1


def test_multiple_due_at_once(app, tmp_path):
    bus = EventBus()
    fired: list[dict] = []
    bus.subscribe(E.REMINDER_DUE, lambda p: fired.append(p))
    store = ReminderStore(path=tmp_path / "r.json")
    sched = ReminderScheduler(bus, store, clock=lambda: 5000.0)
    store.add("One", due_at=4000.0)
    store.add("Two", due_at=4999.0)
    store.add("Future", due_at=9000.0)
    assert len(sched.check_due()) == 2
    assert {f["title"] for f in fired} == {"One", "Two"}


def test_dismiss_prevents_notification(app, tmp_path):
    bus = EventBus()
    fired: list[dict] = []
    bus.subscribe(E.REMINDER_DUE, lambda p: fired.append(p))
    store = ReminderStore(path=tmp_path / "r.json")
    sched = ReminderScheduler(bus, store, clock=lambda: 5000.0)
    r = store.add("Dismissed", due_at=4000.0)
    assert store.dismiss(r["id"]) is True
    assert sched.check_due() == []
    assert fired == []
    assert store.upcoming(now=0.0) == []


def test_persistence_across_restart(app, tmp_path):
    path = tmp_path / "r.json"
    store = ReminderStore(path=path)
    r = store.add("Persist me", due_at=99999.0, notes="hello")
    reloaded = ReminderStore(path=path)
    got = reloaded.get(r["id"])
    assert got is not None and got["title"] == "Persist me" and got["notes"] == "hello"


def test_malformed_records_are_skipped(app, tmp_path):
    path = tmp_path / "r.json"
    path.write_text(json.dumps([
        {"id": "good", "title": "Good", "due_at": 99999.0},
        {"id": "bad", "title": "", "due_at": 99999.0},      # empty title
        {"id": "bad2", "due_at": 99999.0},                  # missing title
        {"id": "bad3", "title": "x", "due_at": "soon"},     # bad due_at
        "not-a-dict",
    ]))
    store = ReminderStore(path=path)
    assert [r["id"] for r in store.all()] == ["good"]
    # Corrupt file entirely: store starts empty instead of crashing.
    path.write_text("{not json")
    assert ReminderStore(path=path).all() == []


def test_disabled_never_fires(app, tmp_path):
    bus = EventBus()
    fired: list[dict] = []
    bus.subscribe(E.REMINDER_DUE, lambda p: fired.append(p))
    store = ReminderStore(path=tmp_path / "r.json")
    sched = ReminderScheduler(bus, store, clock=lambda: 5000.0)
    store.add("Off", due_at=1000.0, enabled=False)
    assert sched.check_due() == []
    assert fired == []
