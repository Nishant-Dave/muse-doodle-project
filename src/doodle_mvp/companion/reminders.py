"""Local reminders: JSON-backed store + single-timer due scheduler.

Reminder record: {id, title, notes, due_at (epoch s), enabled,
notified (bool), dismissed (bool), created_at (epoch s)}.

- Due detection runs on one QTimer (30s); tests drive check_due(now).
- A reminder fires once: notified=True is persisted immediately, so a
  restart can never double-notify.
- Overdue-at-startup reminders fire once, flagged overdue=True.
- Malformed records are skipped with a warning; startup never crashes.
"""

from __future__ import annotations

import logging
import time
import uuid

from PySide6.QtCore import QObject, QTimer

from ..behavior import events as E
from .storage import data_dir, read_json, write_json

log = logging.getLogger(__name__)

REMINDERS_FILE = "reminders.json"
CHECK_INTERVAL_MS = 30_000


def _clean(record: dict) -> dict | None:
    """Validate a raw record; return a normalized dict or None."""
    if not isinstance(record, dict):
        return None
    try:
        title = str(record.get("title", "")).strip()
        due_at = float(record["due_at"])
        if not title:
            return None
        return {
            "id": str(record.get("id") or uuid.uuid4().hex[:12]),
            "title": title[:200],
            "notes": str(record.get("notes", ""))[:2000],
            "due_at": due_at,
            "enabled": bool(record.get("enabled", True)),
            "notified": bool(record.get("notified", False)),
            "dismissed": bool(record.get("dismissed", False)),
            "created_at": float(record.get("created_at", time.time())),
        }
    except (KeyError, TypeError, ValueError):
        return None


class ReminderStore(QObject):
    def __init__(self, path=None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._path = path or (data_dir() / REMINDERS_FILE)
        self._reminders: list[dict] = []
        self.reload()

    def reload(self) -> None:
        raw = read_json(self._path, [])
        items = []
        if isinstance(raw, list):
            for record in raw:
                cleaned = _clean(record)
                if cleaned is not None:
                    items.append(cleaned)
        self._reminders = items

    def _save(self) -> None:
        write_json(self._path, self._reminders)

    def add(self, title: str, due_at: float, notes: str = "",
            enabled: bool = True) -> dict:
        record = _clean({
            "id": uuid.uuid4().hex[:12],
            "title": title,
            "notes": notes,
            "due_at": due_at,
            "enabled": enabled,
        })
        assert record is not None
        self._reminders.append(record)
        self._save()
        return record

    def get(self, reminder_id: str) -> dict | None:
        return next((r for r in self._reminders if r["id"] == reminder_id), None)

    def update(self, reminder_id: str, **fields) -> dict | None:
        record = self.get(reminder_id)
        if record is None:
            return None
        for key in ("title", "notes", "due_at", "enabled", "dismissed"):
            if key in fields:
                record[key] = fields[key]
        cleaned = _clean(record)
        if cleaned is None:  # update made it invalid -> revert
            self.reload()
            return None
        record.update(cleaned)
        self._save()
        return record

    def remove(self, reminder_id: str) -> bool:
        before = len(self._reminders)
        self._reminders = [r for r in self._reminders if r["id"] != reminder_id]
        if len(self._reminders) != before:
            self._save()
            return True
        return False

    def dismiss(self, reminder_id: str) -> bool:
        record = self.get(reminder_id)
        if record is None:
            return False
        record["dismissed"] = True
        record["notified"] = True  # dismissed counts as handled: never refires
        self._save()
        return True

    def mark_notified(self, reminder_id: str) -> None:
        record = self.get(reminder_id)
        if record is not None:
            record["notified"] = True
            self._save()

    def upcoming(self, now: float | None = None) -> list[dict]:
        now = time.time() if now is None else now
        return sorted(
            (r for r in self._reminders
             if r["enabled"] and not r["dismissed"] and r["due_at"] >= now),
            key=lambda r: r["due_at"],
        )

    def all(self) -> list[dict]:
        return list(self._reminders)


class ReminderScheduler(QObject):
    """Polls the store; publishes REMINDER_DUE once per reminder."""

    def __init__(
        self,
        bus: E.EventBus,
        store: ReminderStore,
        clock=time.time,
        interval_ms: int = CHECK_INTERVAL_MS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._bus = bus
        self._store = store
        self._clock = clock
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self.check_due)
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._bus.subscribe(E.APP_EXITING, lambda _p: self.shutdown())
        self.check_due()  # catch anything due while we were away
        self._timer.start()

    def shutdown(self) -> None:
        self._timer.stop()
        self._started = False

    def check_due(self, now: float | None = None) -> list[dict]:
        """Fire due reminders; returns the ones fired (for tests)."""
        now = self._clock() if now is None else now
        fired = []
        for record in self._store.all():
            if not record["enabled"] or record["dismissed"] or record["notified"]:
                continue
            if record["due_at"] <= now:
                overdue = record["due_at"] < now - 1.0
                self._store.mark_notified(record["id"])
                self._bus.publish(E.REMINDER_DUE, {
                    "id": record["id"],
                    "title": record["title"],
                    "overdue": overdue,
                })
                fired.append(record)
        return fired
