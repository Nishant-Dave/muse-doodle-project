"""Generate Doodle Phase 2A assets from the parametric character rig.

    python3 tools/generate_assets_v2.py

Produces:
- assets/source/master_960.png      high-res master character reference
- assets/source/DESIGN.md           design rationale + identity spec
- assets/panda/<anim>/frame_XX.png  240px runtime frames (LANCZOS)
- assets/panda/manifest.json        animation metadata (v2)
- assets/archive/panda_v1/          previous Phase 1 assets, preserved

Requires Pillow (tool-time only, not an app runtime dependency).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from character_rig import CharacterSpec, Pose, render_pose, render_runtime

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSETS = PROJECT_ROOT / "assets"
PANDA = ASSETS / "panda"
SOURCE = ASSETS / "source"
ARCHIVE = ASSETS / "archive" / "panda_v1"

# ------------------------------------------------------------------ poses ---

NEUTRAL = Pose(eye="open", mouth="small", blush=110)

ANIMATIONS: dict[str, dict] = {
    "idle": {
        "fps": 2, "loop": True,
        "description": "Calm breathing idle loop",
        "frames": [
            Pose(eye="open", mouth="small", bob=0),
            Pose(eye="open", mouth="small", bob=3),
            Pose(eye="open", mouth="smile", bob=0),
            Pose(eye="open", mouth="small", bob=2),
        ],
    },
    "blink": {
        "fps": 10, "loop": False,
        "description": "Natural blink: open -> closed -> open",
        "frames": [
            Pose(eye="open", mouth="small"),
            Pose(eye="closed", mouth="small"),
            Pose(eye="open", mouth="small"),
        ],
    },
    "yawn": {
        "fps": 3, "loop": False,
        "description": "Sleepy yawn with coordinated head movement",
        "frames": [
            Pose(eye="sleepy", mouth="small", head_dy=2),
            Pose(eye="sleepy", mouth="o", head_dy=5, extras=("zzz",)),
            Pose(eye="closed", mouth="yawn", tongue=True, head_dy=8, head_tilt=-4,
                 extras=("zzz",)),
            Pose(eye="closed", mouth="yawn", tongue=True, head_dy=6, extras=("zzz",)),
            Pose(eye="open", mouth="small", head_dy=0),
        ],
    },
    "happy": {
        "fps": 6, "loop": False,
        "description": "Joyful bounce: closed happy eyes, lifted cheeks",
        "frames": [
            Pose(eye="happy", mouth="open_smile", tongue=True, cheek_lift=True,
                 blush=210, bob=-8),
            Pose(eye="happy", mouth="smile", cheek_lift=True, blush=210, bob=3),
            Pose(eye="happy", mouth="open_smile", tongue=True, cheek_lift=True,
                 blush=210, bob=-8),
            Pose(eye="open", mouth="smile", blush=150, bob=0),
        ],
    },
    "curious": {
        "fps": 4, "loop": False,
        "description": "Attentive head tilt with raised brow",
        "frames": [
            Pose(eye="curious", mouth="small", brow="raised", ear_perk=0.6),
            Pose(eye="curious", mouth="small", brow="raised", ear_perk=0.8,
                 head_tilt=8, head_dx=10),
            Pose(eye="curious", mouth="o", brow="raised", ear_perk=0.8,
                 head_tilt=8, head_dx=10),
            Pose(eye="open", mouth="small", head_tilt=0, head_dx=0),
        ],
    },
    "sleepy": {
        "fps": 2, "loop": False,
        "description": "Drowsy: half-mast lids, drooping head",
        "frames": [
            Pose(eye="sleepy", mouth="small", head_dy=4),
            Pose(eye="sleepy", mouth="small", head_dy=9, extras=("zzz",)),
            Pose(eye="closed", mouth="small", head_dy=12, extras=("zzz",)),
        ],
    },
    "surprised": {
        "fps": 8, "loop": False,
        "description": "Startled: wide eyes, raised brows, recoil",
        "frames": [
            Pose(eye="wide", mouth="o", brow="raised", head_dy=-10, ear_perk=1.0),
            Pose(eye="wide", mouth="o", brow="raised", head_dy=-6, ear_perk=1.0),
            Pose(eye="open", mouth="small", head_dy=0),
        ],
    },
    "dizzy": {
        "fps": 5, "loop": False,
        "description": "Disoriented after drag, then recovers",
        "frames": [
            Pose(eye="dizzy", mouth="wavy", head_tilt=-10, extras=("stars",)),
            Pose(eye="dizzy", mouth="wavy", head_tilt=10, extras=("stars",)),
            Pose(eye="dizzy", mouth="wavy", head_tilt=-7, extras=("stars",)),
            Pose(eye="sleepy", mouth="small", head_tilt=3),
            Pose(eye="open", mouth="small", head_tilt=0),
        ],
    },
    "sad": {
        "fps": 2, "loop": False,
        "description": "Subdued: droopy lids, sad brows, tear",
        "frames": [
            Pose(eye="sad", mouth="frown", brow="sad", blush=50, head_dy=4),
            Pose(eye="sad", mouth="frown", brow="sad", blush=50, head_dy=8,
                 extras=("tear",)),
            Pose(eye="sad", mouth="frown", brow="sad", blush=60, head_dy=6),
        ],
    },
    "stressed": {
        "fps": 4, "loop": False,
        "description": "Concerned: worried brows, tense wavy mouth",
        "frames": [
            Pose(eye="open", mouth="wavy", brow="concerned", blush=70, bob=-2,
                 extras=("sweat",)),
            Pose(eye="wide", mouth="wavy", brow="concerned", blush=70, bob=2,
                 extras=("sweat",)),
            Pose(eye="open", mouth="small", brow="concerned", blush=80, bob=0),
        ],
    },
    "playful": {
        "fps": 6, "loop": False,
        "description": "Cheeky wink + wave (poke reaction)",
        "frames": [
            Pose(eye="wink", mouth="smirk", blush=170, head_tilt=5),
            Pose(eye="wink", mouth="smirk", blush=190, head_tilt=7, wave=True,
                 extras=("motion",)),
            Pose(eye="wink", mouth="open_smile", tongue=True, blush=190,
                 head_tilt=7, wave=True, extras=("motion",)),
            Pose(eye="happy", mouth="smile", blush=150, head_tilt=0),
        ],
    },
    "drag": {
        "fps": 5, "loop": True,
        "description": "Being held: wide eyes, paws gripping",
        "frames": [
            Pose(eye="wide", mouth="o", bob=-5, ear_perk=0.8),
            Pose(eye="wide", mouth="o", bob=5, ear_perk=0.8),
        ],
    },
}

DESIGN_MD = """# Doodle — Master Character Design (Phase 2A)

## Identity

Doodle is a stylized giant-panda desktop companion rendered in a layered
2.5D-look: soft 2D illustration with 3D-style lighting cues (upper-left key
light, ambient occlusion, glossy eyes, fur strand texture). It is not a 3D
render and does not pretend to be one.

## Signature attributes (consistent across every frame)

- Three-stroke fur tuft on the crown
- Scalloped cheek fluff
- Subtly asymmetric eye patches (left slightly larger, like real pandas)
- Tiny two-tone leaf tucked at the right ear base
- Warm-gray white fur (#F7F4EF), blue-black fur (#302C32) — never pure black

## Construction

- Master: 960x960 PNG, transparent background (`assets/source/master_960.png`)
- Runtime: 240x240 PNG, LANCZOS downscale (matches desktop window size)
- All frames derive from one parametric rig (`tools/character_rig.py`):
  same proportions, patches, fur layout, and lighting by construction.
- Fur strands use a fixed seed and a single precomputed layout, so there is
  no shimmer between frames.

## Light

Soft key light from upper-left on every frame: highlight blob on forehead/
cheek, falloff toward lower-right, AO at ear bases, patch rims, arm/torso
junctions, and under the chin.

## Expressions

10 states + blink + drag: idle, blink, yawn, happy, curious, sleepy,
surprised, dizzy, sad, stressed, playful, drag. See `assets/panda/README.md`
for the per-animation frame map.
"""


def main() -> None:
    # 1. Preserve Phase 1 assets.
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    if PANDA.exists() and not ARCHIVE.exists():
        shutil.move(str(PANDA), str(ARCHIVE))
        print(f"Archived Phase 1 assets -> {ARCHIVE}")
    PANDA.mkdir(parents=True, exist_ok=True)
    SOURCE.mkdir(parents=True, exist_ok=True)

    # 2. Master asset.
    master = render_pose(NEUTRAL)
    master.save(SOURCE / "master_960.png")
    (SOURCE / "DESIGN.md").write_text(DESIGN_MD, encoding="utf-8")
    print(f"Master saved -> {SOURCE / 'master_960.png'}")

    # 3. Runtime frames + manifest.
    manifest: dict = {}
    total = 0
    for name, spec in ANIMATIONS.items():
        d = PANDA / name
        d.mkdir(parents=True, exist_ok=True)
        files = []
        for i, pose in enumerate(spec["frames"]):
            img = render_runtime(pose)
            fname = f"frame_{i:02d}.png"
            img.save(d / fname)
            files.append(f"{name}/{fname}")
            total += 1
        manifest[name] = {
            "fps": spec["fps"],
            "loop": spec["loop"],
            "description": spec["description"],
            "frames": files,
        }
    (PANDA / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {total} frames / {len(ANIMATIONS)} animations -> {PANDA}")

    spec = CharacterSpec()
    print(f"Design: {spec.name} — {spec.light_direction}")


if __name__ == "__main__":
    main()
