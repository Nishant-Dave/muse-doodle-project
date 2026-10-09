"""Companion subpackage: focus timer, reminders, scratchpad, history.

Local-only utilities that make Doodle a useful desktop companion.
All data stays on this machine (JSON files under the app-data dir).
"""

from .focus import FocusTimer
from .reminders import ReminderScheduler, ReminderStore
from .storage import data_dir

__all__ = ["FocusTimer", "ReminderScheduler", "ReminderStore", "data_dir"]
