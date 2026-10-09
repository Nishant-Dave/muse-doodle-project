"""Asset loading: resolves animation frames from disk to QPixmaps.

Assets live in ``<project-root>/assets/panda/<animation>/frame_XX.png`` with
a ``manifest.json`` describing fps/loop per animation. Paths are resolved
relative to this package (with a ``DOODLE_ASSETS_DIR`` override), so loading
works from the launched application, not just the source tree.

Missing or invalid assets are handled gracefully: ``frames_for`` returns an
empty list and logs a warning instead of raising.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtGui import QPixmap

log = logging.getLogger(__name__)

MANIFEST_NAME = "manifest.json"


@dataclass
class AnimationSpec:
    name: str
    frames: list[Path]
    fps: float = 6.0
    loop: bool = True
    description: str = ""


@dataclass
class AssetLoader:
    assets_dir: Path | None = None
    _manifest: dict[str, dict] = field(default_factory=dict, init=False, repr=False)
    _pixmap_cache: dict[str, list[QPixmap]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.assets_dir is None:
            override = os.environ.get("DOODLE_ASSETS_DIR")
            if override:
                self.assets_dir = Path(override)
            else:
                # src/doodle_mvp/character/assets.py -> project root is parents[3].
                self.assets_dir = Path(__file__).resolve().parents[3] / "assets" / "panda"
        self._load_manifest()

    def _load_manifest(self) -> None:
        manifest_path = self.assets_dir / MANIFEST_NAME
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            log.warning("Asset manifest not found: %s", manifest_path)
            return
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Invalid asset manifest %s: %s", manifest_path, exc)
            return
        if not isinstance(raw, dict):
            log.warning("Asset manifest is not an object: %s", manifest_path)
            return
        self._manifest = raw

    @property
    def animation_names(self) -> list[str]:
        return sorted(self._manifest.keys())

    def has_animation(self, name: str) -> bool:
        return name in self._manifest

    def spec_for(self, name: str) -> AnimationSpec | None:
        entry = self._manifest.get(name)
        if not isinstance(entry, dict):
            return None
        frame_files = entry.get("frames", [])
        if not isinstance(frame_files, list) or not frame_files:
            log.warning("Animation %r has no frames listed", name)
            return None
        try:
            fps = float(entry.get("fps", 6.0))
        except (TypeError, ValueError):
            log.warning("Animation %r has invalid fps; using 6.0", name)
            fps = 6.0
        fps = max(0.5, min(fps, 60.0))
        return AnimationSpec(
            name=name,
            frames=[self.assets_dir / f for f in frame_files],
            fps=fps,
            loop=bool(entry.get("loop", True)),
            description=str(entry.get("description", "")),
        )

    def frames_for(self, name: str) -> list[QPixmap]:
        """Load (and cache) the QPixmaps for ``name``; [] if unavailable."""
        if name in self._pixmap_cache:
            return self._pixmap_cache[name]
        spec = self.spec_for(name)
        pixmaps: list[QPixmap] = []
        if spec is not None:
            for path in spec.frames:
                pm = QPixmap(str(path))
                if pm.isNull():
                    log.warning("Could not load frame %s; skipping", path)
                    continue
                pixmaps.append(pm)
        if not pixmaps:
            log.warning("No usable frames for animation %r", name)
        self._pixmap_cache[name] = pixmaps
        return pixmaps

    def clear_cache(self) -> None:
        self._pixmap_cache.clear()
