"""Companion dialogs: focus panel, reminders, scratchpad, notice popup.

All dialogs are plain QDialogs/QWidgets styled like MoodPopup (dark,
rounded, frameless where floating). They talk to the rest of the app
through the event bus and the store/timer objects handed in — no direct
imports of application code.
"""

from __future__ import annotations

import datetime
import logging
import time

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..behavior import events as E
from ..desktop import positioning
from .focus import BREAK, FOCUS, IDLE, PAUSED, FocusTimer
from .reminders import ReminderStore
from .storage import data_dir

log = logging.getLogger(__name__)

DARK_CARD = (
    "background: rgba(40, 36, 40, 235); border-radius: 14px;"
)
BTN = (
    "QPushButton { background: rgba(255,255,255,28); color: white;"
    " border: none; border-radius: 10px; padding: 8px 10px; }"
    "QPushButton:hover { background: rgba(255,255,255,60); }"
    "QPushButton:disabled { background: rgba(255,255,255,10); color: #888; }"
)
LBL = "QLabel { color: white; }"
INPUT = (
    "QLineEdit, QPlainTextEdit, QTextEdit, QDateTimeEdit, QSpinBox {"
    " background: rgba(255,255,255,18); color: white; border: none;"
    " border-radius: 8px; padding: 6px; }"
)


def _fmt_hms(total_s: int) -> str:
    total_s = max(0, int(total_s))
    h, rem = divmod(total_s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _style_popup(widget: QWidget) -> None:
    widget.setStyleSheet(f"QWidget {{ {DARK_CARD} }} {LBL} {BTN} {INPUT}")


# ------------------------------------------------------------------ focus ---

class FocusPanel(QDialog):
    """Focus session controls, settings, and today's summary."""

    def __init__(self, timer: FocusTimer, bus: E.EventBus, parent=None) -> None:
        super().__init__(parent)
        self._timer = timer
        self._bus = bus
        self.setWindowTitle("Doodle — Focus")
        self.setMinimumWidth(300)
        _style_popup(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(8)

        self._status = QLabel("Idle")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet(LBL + "font-size: 15px; font-weight: bold;")
        root.addWidget(self._status)

        self._time = QLabel("--:--")
        self._time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._time.setStyleSheet(LBL + "font-size: 30px;")
        root.addWidget(self._time)

        row = QHBoxLayout()
        self._btn_start = QPushButton("&Start")
        self._btn_pause = QPushButton("&Pause")
        self._btn_resume = QPushButton("&Resume")
        self._btn_stop = QPushButton("Sto&p")
        self._btn_skip = QPushButton("S&kip")
        for b in (self._btn_start, self._btn_pause, self._btn_resume,
                  self._btn_stop, self._btn_skip):
            row.addWidget(b)
        root.addLayout(row)
        self._btn_start.clicked.connect(lambda: bus.publish(E.FOCUS_CONTROL, {"action": "start"}))
        self._btn_pause.clicked.connect(lambda: bus.publish(E.FOCUS_CONTROL, {"action": "pause"}))
        self._btn_resume.clicked.connect(lambda: bus.publish(E.FOCUS_CONTROL, {"action": "resume"}))
        self._btn_stop.clicked.connect(lambda: bus.publish(E.FOCUS_CONTROL, {"action": "stop"}))
        self._btn_skip.clicked.connect(lambda: bus.publish(E.FOCUS_CONTROL, {"action": "skip"}))

        form = QFormLayout()
        self._spin_focus = QSpinBox(); self._spin_focus.setRange(1, 180)
        self._spin_break = QSpinBox(); self._spin_break.setRange(1, 60)
        self._spin_long = QSpinBox(); self._spin_long.setRange(1, 120)
        self._spin_sessions = QSpinBox(); self._spin_sessions.setRange(2, 12)
        s = timer._settings
        self._spin_focus.setValue(s.focus_minutes())
        self._spin_break.setValue(s.break_minutes())
        self._spin_long.setValue(s.long_break_minutes())
        self._spin_sessions.setValue(s.sessions_before_long_break())
        form.addRow("Focus (min)", self._spin_focus)
        form.addRow("Break (min)", self._spin_break)
        form.addRow("Long break (min)", self._spin_long)
        form.addRow("Sessions → long break", self._spin_sessions)
        root.addLayout(form)
        for spin, setter in (
            (self._spin_focus, s.set_focus_minutes),
            (self._spin_break, s.set_break_minutes),
            (self._spin_long, s.set_long_break_minutes),
            (self._spin_sessions, s.set_sessions_before_long_break),
        ):
            spin.valueChanged.connect(setter)

        self._history = QLabel("")
        self._history.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._history)

        for ev in (E.FOCUS_STARTED, E.FOCUS_PAUSED, E.FOCUS_RESUMED,
                   E.FOCUS_STOPPED, E.FOCUS_COMPLETED, E.BREAK_STARTED,
                   E.BREAK_COMPLETED, E.FOCUS_TICK):
            bus.subscribe(ev, lambda _p: self.refresh())
        self.refresh()

    def refresh(self) -> None:
        t = self._timer
        state = t.state
        if state == FOCUS:
            self._status.setText("🎯 Focusing")
            self._time.setText(_fmt_hms(t.remaining_s))
        elif state == BREAK:
            self._status.setText("☕ On break")
            self._time.setText(_fmt_hms(t.remaining_s))
        elif state == PAUSED:
            self._status.setText(f"⏸ Paused ({t.active_kind})")
            self._time.setText(_fmt_hms(t.remaining_s))
        else:
            self._status.setText("Idle")
            self._time.setText("--:--")
        self._btn_start.setEnabled(state == IDLE)
        self._btn_pause.setEnabled(state in (FOCUS, BREAK))
        self._btn_resume.setEnabled(state == PAUSED)
        self._btn_stop.setEnabled(state != IDLE)
        self._btn_skip.setEnabled(state != IDLE)
        count, minutes = t.today_summary()
        self._history.setText(f"Today: {count} session(s) · {minutes} min")


# --------------------------------------------------------------- reminders ---

class ReminderDialog(QDialog):
    """Create a reminder: title, due date/time, notes, enabled."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Doodle — New reminder")
        self.setMinimumWidth(320)
        _style_popup(self)
        root = QVBoxLayout(self)
        form = QFormLayout()
        self._title = QLineEdit()
        self._title.setPlaceholderText("Remind me to…")
        self._due = QDateTimeEdit()
        self._due.setCalendarPopup(True)
        self._due.setDisplayFormat("ddd d MMM yyyy, h:mm AP")
        self._due.setMinimumDateTime(
            self._due.dateTime().addSecs(-1)
        )
        default_due = datetime.datetime.now() + datetime.timedelta(minutes=15)
        self._due.setDateTime(default_due)
        self._notes = QPlainTextEdit()
        self._notes.setPlaceholderText("Notes (optional)")
        self._notes.setMaximumHeight(80)
        self._enabled = QCheckBox("Enabled")
        self._enabled.setChecked(True)
        self._enabled.setStyleSheet(LBL)
        form.addRow("Title", self._title)
        form.addRow("Due", self._due)
        form.addRow("Notes", self._notes)
        form.addRow("", self._enabled)
        root.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def result_record(self) -> dict | None:
        title = self._title.text().strip()
        if not title:
            return None
        return {
            "title": title,
            "due_at": self._due.dateTime().toSecsSinceEpoch(),
            "notes": self._notes.toPlainText().strip(),
            "enabled": self._enabled.isChecked(),
        }


class ReminderListDialog(QDialog):
    """Upcoming reminders with dismiss/delete."""

    def __init__(self, store: ReminderStore, bus: E.EventBus, parent=None) -> None:
        super().__init__(parent)
        self._store = store
        self._bus = bus
        self.setWindowTitle("Doodle — Reminders")
        self.setMinimumSize(340, 300)
        _style_popup(self)
        root = QVBoxLayout(self)
        self._list = QListWidget()
        root.addWidget(self._list)
        row = QHBoxLayout()
        self._btn_dismiss = QPushButton("&Dismiss")
        self._btn_delete = QPushButton("De&lete")
        self._btn_new = QPushButton("&New…")
        close = QPushButton("&Close")
        for b in (self._btn_dismiss, self._btn_delete, self._btn_new, close):
            row.addWidget(b)
        root.addLayout(row)
        self._btn_dismiss.clicked.connect(self._dismiss_selected)
        self._btn_delete.clicked.connect(self._delete_selected)
        self._btn_new.clicked.connect(self._new_reminder)
        close.clicked.connect(self.close)
        self.refresh()

    def _selected_id(self) -> str | None:
        item = self._list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def refresh(self) -> None:
        self._list.clear()
        now = time.time()
        for r in self._store.upcoming(now):
            due = datetime.datetime.fromtimestamp(r["due_at"]).strftime("%a %d %b, %H:%M")
            self._list.addItem(f"{due} — {r['title']}")
            self._list.item(self._list.count() - 1).setData(
                Qt.ItemDataRole.UserRole, r["id"])
        if self._list.count() == 0:
            self._list.addItem("No upcoming reminders.")

    def _dismiss_selected(self) -> None:
        rid = self._selected_id()
        if rid and self._store.dismiss(rid):
            self._bus.publish(E.REMINDER_DISMISSED, {"id": rid})
            self.refresh()

    def _delete_selected(self) -> None:
        rid = self._selected_id()
        if rid and self._store.remove(rid):
            self._bus.publish(E.REMINDER_DELETED, {"id": rid})
            self.refresh()

    def _new_reminder(self) -> None:
        dlg = ReminderDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            record = dlg.result_record()
            if record:
                created = self._store.add(**record)
                self._bus.publish(E.REMINDER_CREATED,
                                  {"id": created["id"], "title": created["title"]})
                self.refresh()


# --------------------------------------------------------------- scratchpad ---

class ScratchpadDialog(QDialog):
    """Persistent quick note. Saved automatically on this computer."""

    def __init__(self, path=None, parent=None) -> None:
        super().__init__(parent)
        self._path = path or (data_dir() / "scratchpad.txt")
        self.setWindowTitle("Doodle — Scratchpad")
        self.setMinimumSize(340, 260)
        _style_popup(self)
        root = QVBoxLayout(self)
        hint = QLabel("Quick note — saved automatically on this computer.")
        root.addWidget(hint)
        self._text = QTextEdit()
        try:
            self._text.setPlainText(self._path.read_text(encoding="utf-8"))
        except OSError:
            pass
        root.addWidget(self._text)
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(1500)
        self._save_timer.timeout.connect(self.save_now)
        self._text.textChanged.connect(lambda: self._save_timer.start())

    def save_now(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(self._text.toPlainText(), encoding="utf-8")
        except OSError as exc:
            log.warning("Could not save scratchpad: %s", exc)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._save_timer.stop()
        self.save_now()
        super().closeEvent(event)


# ------------------------------------------------------------ notice popup ---

class NoticePopup(QWidget):
    """Small frameless reminder notification near the panda."""

    dismissed = Signal(str)  # reminder id
    closed = Signal()  # closed by any means (dismiss, timeout, Esc, X)

    AUTO_CLOSE_MS = 30_000

    def __init__(self, parent=None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(260, 150)
        self._reminder_id = ""
        _style_popup(self)
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(8)
        self._title = QLabel("⏰ Reminder")
        self._title.setStyleSheet(LBL + "font-size: 14px; font-weight: bold;")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._title)
        self._message = QLabel("")
        self._message.setWordWrap(True)
        self._message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._message)
        dismiss = QPushButton("&Dismiss")
        dismiss.clicked.connect(self._on_dismiss)
        root.addWidget(dismiss)
        self._auto = QTimer(self)
        self._auto.setSingleShot(True)
        self._auto.timeout.connect(self.close)

    def show_near(self, anchor: QWidget, reminder_id: str, title: str,
                  overdue: bool = False) -> None:
        self._reminder_id = reminder_id
        prefix = "Overdue: " if overdue else ""
        self._message.setText(f"{prefix}{title}")
        top_left = anchor.mapToGlobal(QPoint(0, 0))
        x = top_left.x() + (anchor.width() - self.width()) // 2
        y = top_left.y() - self.height() - 12
        self.move(positioning.clamp_to_screen(self, QPoint(x, y)))
        self.show()
        self.raise_()
        self.activateWindow()
        self._auto.start(self.AUTO_CLOSE_MS)

    def _on_dismiss(self) -> None:
        self.dismissed.emit(self._reminder_id)
        self.close()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.closed.emit()
        super().closeEvent(event)
