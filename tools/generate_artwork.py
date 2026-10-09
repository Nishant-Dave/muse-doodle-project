"""Generate the original Doodle Phase 1 panda artwork.

Creates a consistent, cute panda design (240x240 PNG, transparent background)
with genuinely different frames per animation state. Run from the project root:

    python3 tools/generate_artwork.py

Requires Pillow (only needed for this tool, not for the application runtime).

Design notes (kept consistent across all frames):
- Round white head, two black ears, black eye patches.
- Eye styles vary per state: open, closed, happy (^ ^), wide (surprised),
  x_eyes (dizzy), droopy (sleepy/sad).
- Mouth styles vary per state: smile, open (yawn), frown, wavy (stressed).
- Subtle per-frame differences: vertical bob, head tilt, blush strength,
  and state extras (Z letters, sweat drop, tear, stars, motion lines).
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 240
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = PROJECT_ROOT / "assets" / "panda"

# Palette
BLACK = (35, 30, 32, 255)
WHITE = (255, 255, 255, 255)
PATCH = (45, 40, 44, 255)
BLUSH = (255, 150, 160, 150)
MOUTH = (60, 45, 50, 255)
BLUE = (140, 200, 245, 230)
STAR = (255, 215, 90, 255)
MOTION = (150, 150, 160, 160)

LEFT_EYE = (94, 119)
RIGHT_EYE = (146, 119)


def _star(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float, color=STAR) -> None:
    pts = []
    for i in range(8):
        ang = math.pi / 4 * i - math.pi / 2
        rad = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    draw.polygon(pts, fill=color)


def _draw_z(draw: ImageDraw.ImageDraw, x: float, y: float, s: float, color=BLUE) -> None:
    w = 4
    draw.line([(x, y), (x + s, y)], fill=color, width=w)
    draw.line([(x + s, y), (x, y + s)], fill=color, width=w)
    draw.line([(x, y + s), (x + s, y + s)], fill=color, width=w)


def _draw_drop(draw: ImageDraw.ImageDraw, cx: float, cy: float, s: float, color=BLUE) -> None:
    draw.ellipse([cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2], fill=color)
    draw.polygon([(cx, cy - s), (cx - s / 2.4, cy), (cx + s / 2.4, cy)], fill=color)


def _draw_eyes(draw: ImageDraw.ImageDraw, style: str) -> None:
    for cx, cy in (LEFT_EYE, RIGHT_EYE):
        if style == "open":
            draw.ellipse([cx - 10, cy - 13, cx + 10, cy + 13], fill=BLACK)
            draw.ellipse([cx - 6, cy - 10, cx + 1, cy - 3], fill=WHITE)
        elif style == "closed":
            draw.arc([cx - 11, cy - 8, cx + 11, cy + 14], start=200, end=340, fill=BLACK, width=5)
        elif style == "happy":
            draw.arc([cx - 12, cy - 12, cx + 12, cy + 12], start=180, end=360, fill=BLACK, width=6)
        elif style == "wide":
            draw.ellipse([cx - 13, cy - 15, cx + 13, cy + 15], fill=WHITE)
            draw.ellipse([cx - 6, cy - 8, cx + 6, cy + 8], fill=BLACK)
            draw.ellipse([cx - 4, cy - 6, cx + 1, cy - 1], fill=WHITE)
        elif style == "x_eyes":
            o = 9
            draw.line([cx - o, cy - o, cx + o, cy + o], fill=BLACK, width=5)
            draw.line([cx - o, cy + o, cx + o, cy - o], fill=BLACK, width=5)
        elif style == "droopy":
            draw.ellipse([cx - 10, cy - 4, cx + 10, cy + 10], fill=BLACK)
            draw.line([cx - 12, cy - 8, cx + 12, cy - 8], fill=BLACK, width=6)
        else:
            raise ValueError(f"unknown eye style: {style}")


def _draw_mouth(draw: ImageDraw.ImageDraw, style: str) -> None:
    cx, cy = 120, 158
    if style == "smile":
        draw.arc([cx - 20, cy - 14, cx + 20, cy + 16], start=25, end=155, fill=MOUTH, width=4)
    elif style == "open":
        draw.ellipse([cx - 16, cy - 10, cx + 16, cy + 24], fill=MOUTH)
        draw.ellipse([cx - 9, cy + 2, cx + 9, cy + 18], fill=(150, 90, 95, 255))
    elif style == "frown":
        draw.arc([cx - 18, cy - 6, cx + 18, cy + 22], start=205, end=335, fill=MOUTH, width=4)
    elif style == "wavy":
        pts = [(cx - 22 + i * 4, cy + 6 * math.sin(i * 1.4)) for i in range(12)]
        draw.line(pts, fill=MOUTH, width=4, joint="curve")
    elif style == "small":
        draw.arc([cx - 10, cy - 8, cx + 10, cy + 8], start=25, end=155, fill=MOUTH, width=3)
    elif style == "o":
        draw.ellipse([cx - 8, cy - 4, cx + 8, cy + 12], outline=MOUTH, width=4)
    else:
        raise ValueError(f"unknown mouth style: {style}")


def render_frame(
    *,
    eye: str = "open",
    mouth: str = "smile",
    bob: int = 0,
    tilt: float = 0.0,
    blush_alpha: int = 150,
    paws_up: bool = False,
    extras: tuple[str, ...] = (),
    extra_strength: int = 0,
) -> Image.Image:
    """Render one 240x240 RGBA panda frame."""
    layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    # Ears
    d.ellipse([50, 34, 102, 86], fill=BLACK)
    d.ellipse([138, 34, 190, 86], fill=BLACK)
    d.ellipse([64, 48, 92, 76], fill=(90, 80, 88, 255))
    d.ellipse([148, 48, 176, 76], fill=(90, 80, 88, 255))

    # Head
    d.ellipse([44, 50, 196, 210], fill=WHITE)
    d.ellipse([44, 50, 196, 210], outline=(225, 225, 230, 255), width=2)

    # Eye patches
    d.ellipse([70, 94, 118, 144], fill=PATCH)
    d.ellipse([122, 94, 170, 144], fill=PATCH)

    _draw_eyes(d, eye)

    # Nose
    d.ellipse([109, 138, 131, 152], fill=BLACK)
    d.ellipse([113, 140, 121, 146], fill=(255, 255, 255, 120))

    _draw_mouth(d, mouth)

    # Blush
    blush = BLUSH[:3] + (blush_alpha,)
    d.ellipse([62, 148, 90, 164], fill=blush)
    d.ellipse([150, 148, 178, 164], fill=blush)

    # Paws / feet
    if paws_up:
        d.ellipse([22, 132, 62, 186], fill=WHITE, outline=BLACK, width=4)
        d.ellipse([178, 132, 218, 186], fill=WHITE, outline=BLACK, width=4)
    else:
        d.ellipse([76, 196, 112, 224], fill=WHITE, outline=BLACK, width=3)
        d.ellipse([128, 196, 164, 224], fill=WHITE, outline=BLACK, width=3)

    if "zzz" in extras:
        n = 1 + extra_strength
        for i in range(n):
            _draw_z(d, 178 + i * 22, 44 - i * 22, 14 + i * 6)
    if "sweat" in extras:
        _draw_drop(d, 182, 96, 16)
    if "tear" in extras:
        _draw_drop(d, 94, 150, 13)
    if "stars" in extras:
        _star(d, 52, 70, 12)
        _star(d, 190, 66, 9)
        if extra_strength > 0:
            _star(d, 66, 40, 8)
    if "motion" in extras:
        for i, y in enumerate((90, 130, 170)):
            x = 14 + (i % 2) * 6
            d.line([(x, y), (x + 18, y)], fill=MOTION, width=4)

    if tilt:
        layer = layer.rotate(tilt, resample=Image.BICUBIC, center=(120, 130))

    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    canvas.alpha_composite(layer, (0, bob))
    return canvas


# Animation definitions: name -> list of frame keyword dicts.
FRAMES: dict[str, list[dict]] = {
    "idle": [
        {"eye": "open", "mouth": "small", "bob": 0},
        {"eye": "open", "mouth": "small", "bob": 3},
        {"eye": "open", "mouth": "smile", "bob": 0},
    ],
    "blink": [
        {"eye": "open", "mouth": "small", "bob": 0},
        {"eye": "closed", "mouth": "small", "bob": 1},
        {"eye": "open", "mouth": "small", "bob": 0},
    ],
    "yawn": [
        {"eye": "droopy", "mouth": "small", "bob": 0},
        {"eye": "droopy", "mouth": "o", "bob": 1, "extras": ("zzz",), "extra_strength": 0},
        {"eye": "closed", "mouth": "open", "bob": 2, "extras": ("zzz",), "extra_strength": 1},
        {"eye": "closed", "mouth": "open", "bob": 1, "extras": ("zzz",), "extra_strength": 2},
    ],
    "drag": [
        {"eye": "wide", "mouth": "o", "bob": 0, "paws_up": True, "extras": ("motion",)},
        {"eye": "wide", "mouth": "o", "bob": -4, "paws_up": True, "extras": ("motion",)},
    ],
    "poke": [
        {"eye": "wide", "mouth": "o", "bob": -6, "paws_up": True},
        {"eye": "happy", "mouth": "smile", "bob": 2, "blush_alpha": 220},
        {"eye": "happy", "mouth": "smile", "bob": -2, "blush_alpha": 220},
    ],
    "happy": [
        {"eye": "happy", "mouth": "smile", "bob": -6, "blush_alpha": 230},
        {"eye": "happy", "mouth": "open", "bob": 2, "blush_alpha": 230},
        {"eye": "happy", "mouth": "smile", "bob": -6, "blush_alpha": 230},
    ],
    "dizzy": [
        {"eye": "x_eyes", "mouth": "wavy", "tilt": -9, "extras": ("stars",), "extra_strength": 0},
        {"eye": "x_eyes", "mouth": "wavy", "tilt": 9, "extras": ("stars",), "extra_strength": 1},
        {"eye": "x_eyes", "mouth": "wavy", "tilt": -9, "extras": ("stars",), "extra_strength": 1},
        {"eye": "x_eyes", "mouth": "wavy", "tilt": 9, "extras": ("stars",), "extra_strength": 0},
    ],
    "mood_sad": [
        {"eye": "droopy", "mouth": "frown", "bob": 2, "blush_alpha": 60},
        {"eye": "droopy", "mouth": "frown", "bob": 3, "blush_alpha": 60, "extras": ("tear",)},
    ],
    "mood_stressed": [
        {"eye": "wide", "mouth": "wavy", "bob": -2, "extras": ("sweat",)},
        {"eye": "wide", "mouth": "wavy", "bob": 2, "extras": ("sweat",)},
    ],
}

# Manifest: playback metadata per animation.
MANIFEST: dict[str, dict] = {
    "idle": {"fps": 2, "loop": True, "description": "Gentle breathing idle loop"},
    "blink": {"fps": 9, "loop": False, "description": "Quick blink, returns to idle"},
    "yawn": {"fps": 3, "loop": False, "description": "Sleepy yawn with Z letters"},
    "drag": {"fps": 5, "loop": True, "description": "Being held: paws up, wide eyes"},
    "poke": {"fps": 7, "loop": False, "description": "Surprised poke then happy bounce"},
    "happy": {"fps": 6, "loop": False, "description": "Joyful bounce, closed happy eyes"},
    "dizzy": {"fps": 5, "loop": False, "description": "Dizzy after a long/fast drag"},
    "mood_sad": {"fps": 2, "loop": False, "description": "Reaction to 'Sad' mood"},
    "mood_stressed": {"fps": 4, "loop": False, "description": "Reaction to 'Stressed' mood"},
}


def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    manifest_out: dict[str, dict] = {}
    total = 0
    for name, frame_defs in FRAMES.items():
        anim_dir = ASSETS_DIR / name
        anim_dir.mkdir(parents=True, exist_ok=True)
        # Remove stale frames from previous runs.
        for stale in anim_dir.glob("frame_*.png"):
            stale.unlink()
        files = []
        for i, kwargs in enumerate(frame_defs):
            img = render_frame(**kwargs)
            fname = f"frame_{i:02d}.png"
            img.save(anim_dir / fname)
            files.append(f"{name}/{fname}")
            total += 1
        meta = dict(MANIFEST[name])
        meta["frames"] = files
        manifest_out[name] = meta
    with open(ASSETS_DIR / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest_out, f, indent=2)
    print(f"Wrote {total} frames for {len(FRAMES)} animations to {ASSETS_DIR}")


if __name__ == "__main__":
    main()
