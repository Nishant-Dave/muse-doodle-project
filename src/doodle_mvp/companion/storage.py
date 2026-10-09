"""Local data directory + atomic JSON helpers for companion features.

Everything lives under QStandardPaths AppDataLocation/"Doodle"
(Windows: %APPDATA%/Doodle). Writes are atomic (tmp file + os.replace)
so a crash can never leave a half-written file.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QStandardPaths

log = logging.getLogger(__name__)


def data_dir(custom: Path | str | None = None) -> Path:
    """App data directory, created on demand. ``custom`` overrides (tests)."""
    if custom is not None:
        path = Path(custom)
    else:
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        path = Path(base) / "Doodle" if base else Path.home() / ".doodle"
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Ignoring unreadable %s: %s", path, exc)
        return default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp, path)
    except OSError as exc:
        log.warning("Could not write %s: %s", path, exc)
        try:
            os.unlink(tmp)
        except OSError:
            pass
