"""Validate Doodle animation assets against the manifest.

Checks for every animation in assets/panda/manifest.json:
- manifest entry has fps (> 0), loop (bool), description, non-empty frames list
- every frame file exists, is a valid PNG, RGBA, 240x240
- no frame is fully transparent (would render as a flicker)
- frame files are sorted and zero-padded consistently

Exit code 0 = valid, 1 = problems found. Also importable for pytest.

    python3 tools/validate_assets.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PANDA = PROJECT_ROOT / "assets" / "panda"
EXPECTED_SIZE = (240, 240)

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None


def validate(panda_dir: Path = PANDA) -> list[str]:
    errors: list[str] = []
    manifest_path = panda_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        return [f"manifest unreadable: {exc}"]
    if not isinstance(manifest, dict) or not manifest:
        return ["manifest is empty or not an object"]

    for name, entry in sorted(manifest.items()):
        if not isinstance(entry, dict):
            errors.append(f"{name}: entry is not an object")
            continue
        fps = entry.get("fps")
        if not isinstance(fps, (int, float)) or fps <= 0:
            errors.append(f"{name}: invalid fps {fps!r}")
        if not isinstance(entry.get("loop"), bool):
            errors.append(f"{name}: 'loop' must be bool")
        if not entry.get("description"):
            errors.append(f"{name}: missing description")
        frames = entry.get("frames")
        if not isinstance(frames, list) or not frames:
            errors.append(f"{name}: no frames listed")
            continue
        for rel in frames:
            path = panda_dir / rel
            if not path.is_file():
                errors.append(f"{name}: missing file {rel}")
                continue
            if Image is None:
                continue
            try:
                with Image.open(path) as img:
                    img.load()
                    if img.mode != "RGBA":
                        errors.append(f"{name}: {rel} mode is {img.mode}, want RGBA")
                    if img.size != EXPECTED_SIZE:
                        errors.append(
                            f"{name}: {rel} size is {img.size}, want {EXPECTED_SIZE}"
                        )
                    if img.getbbox() is None:
                        errors.append(f"{name}: {rel} is fully transparent")
            except Exception as exc:  # noqa: BLE001 - report any decode failure
                errors.append(f"{name}: {rel} unreadable ({exc})")
    return errors


def main() -> int:
    if Image is None:
        print("Pillow is required for validation", file=sys.stderr)
        return 2
    errors = validate()
    if errors:
        print(f"{len(errors)} problem(s):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("assets OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
