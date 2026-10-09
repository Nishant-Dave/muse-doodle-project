"""Parametric 2.5D-look panda character rig for Doodle Phase 2A.

A deterministic, layered software renderer (Pillow) that produces every
animation frame from ONE shared character definition. Because all frames
derive from the same rig, identity (proportions, patches, fur, lighting)
is consistent across expressions by construction.

Style: layered 2D illustration with 3D-style lighting cues (soft key light
from upper-left, ambient occlusion, glossy eyes, fur strand texture). This
is the practical meaning of "2.5D hybrid" achievable with this pipeline;
it is not a 3D render.

Master resolution: 960x960. Runtime assets are downscaled to 240x240
(LANCZOS) by tools/generate_assets_v2.py.

Determinism: all randomness uses a fixed seed; fur strand layout is
computed once and reused verbatim for every frame (no shimmer).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from PIL import Image, ImageDraw, ImageFilter

MASTER = 960
RUNTIME = 240
SEED = 20261009

# ---------------------------------------------------------------- palette ---
WHITE_FUR = (247, 244, 239, 255)
WHITE_SHADE = (233, 227, 215, 255)
WHITE_DEEP = (213, 205, 189, 255)
BLACK_FUR = (48, 44, 50, 255)
BLACK_HI = (78, 72, 84, 255)
BLACK_DEEP = (30, 27, 33, 255)
PATCH = (54, 49, 57, 255)
NOSE = (62, 53, 60, 255)
NOSE_HI = (110, 98, 108, 255)
BLUSH = (244, 168, 170, 255)
TONGUE = (216, 132, 137, 255)
MOUTH_DARK = (74, 55, 61, 255)
EYE_DARK = (26, 21, 25, 255)
LEAF_A = (127, 176, 105, 255)
LEAF_B = (88, 132, 74, 255)
BLUE = (140, 200, 245, 255)
STAR = (255, 214, 100, 255)

_rng = random.Random(SEED)

# ------------------------------------------------------------- pose params ---


@dataclass
class Pose:
    """Everything that may vary between frames of an animation."""

    eye: str = "open"            # open|happy|sleepy|closed|wide|dizzy|sad|wink|curious
    mouth: str = "smile"         # smile|open_smile|o|frown|wavy|yawn|smirk|small
    brow: str = "none"           # none|sad|concerned|raised
    head_tilt: float = 0.0       # degrees, + = clockwise
    head_dx: int = 0
    head_dy: int = 0
    bob: int = 0                 # whole-character vertical offset
    cheek_lift: bool = False     # happy cheeks
    blush: int = 110             # blush alpha
    ear_perk: float = 0.0        # 0..1 raises ears slightly
    wave: bool = False           # right paw raised waving
    extras: tuple = ()           # tear|sweat|zzz|stars|motion|tongue_out
    tongue: bool = False


# ------------------------------------------------------------------ helpers ---

def _new(size: int = MASTER) -> Image.Image:
    return Image.new("RGBA", (size, size), (0, 0, 0, 0))


def _ellipse(layer: Image.Image, cx, cy, rx, ry, fill, rotation: float = 0.0):
    """Axis-aligned or rotated ellipse, drawn on its own layer then merged."""
    if rotation == 0.0:
        d = ImageDraw.Draw(layer)
        d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=fill)
        return
    tmp = _new(layer.size[0])
    d = ImageDraw.Draw(tmp)
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=fill)
    tmp = tmp.rotate(-rotation, resample=Image.BICUBIC, center=(cx, cy))
    layer.alpha_composite(tmp)


def _soft(layer: Image.Image, radius: float) -> Image.Image:
    return layer.filter(ImageFilter.GaussianBlur(radius))


def _vgradient(draw: ImageDraw.ImageDraw, bbox, top, bottom):
    """Vertical gradient fill inside bbox (used for glossy eyes)."""
    x0, y0, x1, y1 = [int(v) for v in bbox]
    h = max(1, y1 - y0)
    for y in range(y0, y1):
        t = (y - y0) / h
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(4))
        draw.line([(x0, y), (x1, y)], fill=c)


def _eye_base(layer: Image.Image, cx, cy, rx, ry, top, bottom):
    """Glossy eye base: vertical gradient clipped to the eye ellipse."""
    grad = _new(layer.size[0])
    d = ImageDraw.Draw(grad)
    _vgradient(d, [cx - rx, cy - ry, cx + rx, cy + ry], top, bottom)
    mask = _new(layer.size[0])
    dm = ImageDraw.Draw(mask)
    dm.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=(255, 255, 255, 255))
    mask = _soft(mask, 3)
    layer.alpha_composite(Image.composite(grad, _new(), mask))


# ------------------------------------------------------- fur strand field ---
# Computed once: silhouette-following strands, identical for every frame.

_strand_cache: list | None = None


def _strand_layout() -> list:
    global _strand_cache
    if _strand_cache is not None:
        return _strand_cache
    rng = random.Random(SEED)
    strands = []

    def edge(cx, cy, rx, ry, rot, n, length, color, a0, a1, jitter=0.35):
        for _ in range(n):
            a = math.radians(rng.uniform(a0, a1))
            # point on rotated ellipse
            ex = rx * math.cos(a)
            ey = ry * math.sin(a)
            rad = math.radians(rot)
            px = cx + ex * math.cos(rad) - ey * math.sin(rad)
            py = cy + ex * math.sin(rad) + ey * math.cos(rad)
            # outward normal direction
            nx = math.cos(a + rad)
            ny = math.sin(a + rad)
            ang = math.atan2(ny, nx) + rng.uniform(-jitter, jitter)
            ln = length * rng.uniform(0.6, 1.3)
            x2 = px + math.cos(ang) * ln
            y2 = py + math.sin(ang) * ln
            strands.append(((px, py, x2, y2), color, rng.uniform(2.5, 5)))

    fur_w = (216, 209, 193, 70)
    fur_b = (96, 90, 102, 70)
    # head silhouette (skip top where tuft lives: angles in degrees, 0=east)
    edge(480, 400, 295, 275, 0, 90, 16, fur_w, 20, 160)
    # cheek fluff zones get denser strands
    edge(480, 400, 300, 280, 0, 40, 20, fur_w, 130, 230)
    edge(480, 400, 300, 280, 0, 40, 20, fur_w, 310, 410)
    # ears
    edge(235, 165, 105, 105, 0, 16, 12, fur_b, 200, 340)
    edge(725, 165, 105, 105, 0, 16, 12, fur_b, 200, 340)
    # torso sides
    edge(480, 730, 235, 215, 0, 50, 15, fur_w, 200, 340)
    # sparse inner flow on white areas (very subtle)
    for _ in range(130):
        x = rng.uniform(300, 660)
        y = rng.uniform(220, 560)
        ln = rng.uniform(10, 26)
        strands.append(((x, y, x + rng.uniform(-4, 4), y + ln),
                        (220, 212, 198, 34), rng.uniform(2, 3.5)))
    _strand_cache = strands
    return strands


def _draw_fur(base: Image.Image):
    layer = _new()
    d = ImageDraw.Draw(layer)
    for (x1, y1, x2, y2), color, w in _strand_layout():
        d.line([(x1, y1), (x2, y2)], fill=color, width=int(w))
    base.alpha_composite(_soft(layer, 1.2))


# ------------------------------------------------------------------- body ---

def _render_body(wave: bool = False) -> Image.Image:
    L = _new()
    # torso
    _ellipse(L, 480, 730, 235, 215, WHITE_FUR)
    # black shoulder saddles (classic panda marking, soft)
    _ellipse(L, 330, 620, 120, 150, BLACK_FUR, rotation=-18)
    _ellipse(L, 630, 620, 120, 150, BLACK_FUR, rotation=18)
    # arms (right arm is replaced by the raised wave arm when waving)
    _ellipse(L, 262, 710, 72, 138, BLACK_FUR, rotation=-14)
    _ellipse(L, 245, 680, 26, 60, BLACK_HI[:3] + (90,), rotation=-14)
    if not wave:
        _ellipse(L, 698, 710, 72, 138, BLACK_FUR, rotation=14)
        _ellipse(L, 715, 680, 26, 60, BLACK_HI[:3] + (90,), rotation=14)
    # feet
    _ellipse(L, 372, 908, 96, 60, BLACK_FUR)
    _ellipse(L, 588, 908, 96, 60, BLACK_FUR)
    _ellipse(L, 350, 892, 40, 22, BLACK_HI[:3] + (110,))
    _ellipse(L, 610, 892, 40, 22, BLACK_HI[:3] + (110,))
    _draw_fur(L)
    return L


def _body_shading(wave: bool = False) -> Image.Image:
    """Lighting overlays for the body, masked to the body silhouette."""
    shade = _new()
    d = ImageDraw.Draw(shade)
    # key light from upper-left
    d.ellipse([120, 420, 560, 860], fill=(255, 255, 255, 30))
    # lower-right falloff
    d.ellipse([420, 620, 900, 1000], fill=(40, 30, 40, 42))
    shade = _soft(shade, 55)
    # ambient occlusion blobs
    ao = _new()
    da = ImageDraw.Draw(ao)
    da.ellipse([300, 560, 420, 700], fill=(30, 22, 30, 70))   # arm/torso L
    if not wave:
        da.ellipse([540, 560, 660, 700], fill=(30, 22, 30, 70))   # arm/torso R
    da.ellipse([380, 880, 580, 960], fill=(30, 22, 30, 60))   # feet shadow
    ao = _soft(ao, 28)
    # mask to body silhouette
    mask = _new()
    dm = ImageDraw.Draw(mask)
    dm.ellipse([480 - 235, 730 - 215, 480 + 235, 730 + 215], fill=(255, 255, 255, 255))
    dm.ellipse([262 - 72, 710 - 138, 262 + 72, 710 + 138], fill=(255, 255, 255, 255))
    if not wave:
        dm.ellipse([698 - 72, 710 - 138, 698 + 72, 710 + 138], fill=(255, 255, 255, 255))
    dm.ellipse([372 - 96, 908 - 60, 372 + 96, 908 + 60], fill=(255, 255, 255, 255))
    dm.ellipse([588 - 96, 908 - 60, 588 + 96, 908 + 60], fill=(255, 255, 255, 255))
    mask = _soft(mask, 6)
    out = _new()
    out.alpha_composite(Image.composite(shade, _new(), mask))
    out.alpha_composite(Image.composite(ao, _new(), mask))
    return out


# ------------------------------------------------------------------- head ---

def _render_head(pose: Pose) -> Image.Image:
    L = _new()
    perk = pose.ear_perk * 14
    # ears
    _ellipse(L, 235, 165 - perk, 105, 105, BLACK_FUR)
    _ellipse(L, 725, 165 - perk, 105, 105, BLACK_FUR)
    _ellipse(L, 235, 170 - perk, 58, 58, BLACK_DEEP)
    _ellipse(L, 725, 170 - perk, 58, 58, BLACK_DEEP)
    # head base
    _ellipse(L, 480, 400, 295, 275, WHITE_FUR)
    # cheek fluff scallops (signature)
    for cx, cy in ((205, 520), (755, 520), (235, 580), (725, 580)):
        _ellipse(L, cx, cy, 62, 58, WHITE_FUR)
    # eye patches: distinctive teardrop, subtly asymmetric (left larger)
    _ellipse(L, 362, 432, 80, 108, PATCH, rotation=-16)
    _ellipse(L, 598, 428, 72, 100, PATCH, rotation=16)
    # patch soft inner shading
    _ellipse(L, 362, 452, 56, 76, (40, 36, 44, 120), rotation=-16)
    _ellipse(L, 598, 448, 50, 70, (40, 36, 44, 120), rotation=16)
    # head tuft (signature): three short curved strokes
    d = ImageDraw.Draw(L)
    for dx, w in ((-22, 11), (0, 13), (22, 11)):
        d.arc([480 + dx - 16, 96, 480 + dx + 16, 160], 235, 305, fill=WHITE_FUR, width=w)
    _draw_fur(L)
    return L


def _head_shading() -> Image.Image:
    shade = _new()
    d = ImageDraw.Draw(shade)
    d.ellipse([180, 80, 620, 480], fill=(255, 255, 255, 34))     # key light
    d.ellipse([420, 300, 860, 700], fill=(48, 36, 48, 40))      # lower-right falloff
    shade = _soft(shade, 55)
    ao = _new()
    da = ImageDraw.Draw(ao)
    da.ellipse([180, 120, 330, 260], fill=(30, 22, 30, 80))     # ear base L
    da.ellipse([630, 120, 780, 260], fill=(30, 22, 30, 80))     # ear base R
    da.ellipse([300, 300, 440, 480], fill=(30, 22, 30, 46))     # patch rim L
    da.ellipse([520, 300, 660, 480], fill=(30, 22, 30, 46))     # patch rim R
    da.ellipse([360, 600, 600, 700], fill=(30, 22, 30, 66))     # under chin
    ao = _soft(ao, 30)
    mask = _new()
    dm = ImageDraw.Draw(mask)
    dm.ellipse([480 - 295, 400 - 275, 480 + 295, 400 + 275], fill=(255, 255, 255, 255))
    dm.ellipse([235 - 105, 165 - 105, 235 + 105, 165 + 105], fill=(255, 255, 255, 255))
    dm.ellipse([725 - 105, 165 - 105, 725 + 105, 165 + 105], fill=(255, 255, 255, 255))
    mask = _soft(mask, 6)
    out = _new()
    out.alpha_composite(Image.composite(shade, _new(), mask))
    out.alpha_composite(Image.composite(ao, _new(), mask))
    return out


# ------------------------------------------------------------------- face ---

def _draw_eye(L: Image.Image, cx, cy, style: str, mirror: bool = False):
    """Glossy panda eye with expression variants. cx,cy = eye center."""
    d = ImageDraw.Draw(L)
    if style == "open":
        _eye_base(L, cx, cy, 52, 62, (58, 50, 58, 255), EYE_DARK)
        d.ellipse([cx - 52, cy - 62, cx + 52, cy + 62], outline=(20, 16, 20, 255), width=5)
        d.ellipse([cx - 30, cy - 44, cx + 6, cy - 8], fill=(255, 255, 255, 215))
        d.ellipse([cx + 12, cy + 14, cx + 30, cy + 32], fill=(255, 255, 255, 255))
    elif style == "happy":  # closed ^ ^
        d.arc([cx - 46, cy - 46, cx + 46, cy + 46], 180, 360, fill=EYE_DARK, width=17)
    elif style == "sleepy":  # half-mast lid
        _eye_base(L, cx, cy, 52, 62, (58, 50, 58, 255), EYE_DARK)
        d.ellipse([cx - 56, cy - 100, cx + 56, cy - 6], fill=PATCH)
        d.line([(cx - 56, cy - 6), (cx + 56, cy - 6)], fill=(20, 16, 20, 255), width=9)
        d.ellipse([cx - 24, cy - 40, cx + 2, cy - 14], fill=(255, 255, 255, 150))
    elif style == "closed":
        d.arc([cx - 44, cy - 30, cx + 44, cy + 48], 195, 345, fill=(20, 16, 20, 255), width=13)
    elif style == "wide":  # surprised: larger + brighter
        _eye_base(L, cx, cy, 62, 72, (70, 60, 70, 255), EYE_DARK)
        d.ellipse([cx - 62, cy - 72, cx + 62, cy + 72], outline=(20, 16, 20, 255), width=5)
        d.ellipse([cx - 34, cy - 52, cx + 8, cy - 10], fill=(255, 255, 255, 235))
        d.ellipse([cx + 14, cy + 16, cx + 34, cy + 36], fill=(255, 255, 255, 255))
    elif style == "dizzy":  # @ spiral-ish
        _eye_base(L, cx, cy, 52, 62, (58, 50, 58, 255), EYE_DARK)
        for r in (34, 22, 11):
            d.arc([cx - r, cy - r, cx + r, cy + r], 20, 300, fill=(255, 255, 255, 220), width=8)
        d.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=(255, 255, 255, 255))
    elif style == "sad":  # droopy lid, lid line slanted down-outward
        _eye_base(L, cx, cy, 52, 62, (52, 46, 52, 255), EYE_DARK)
        s = -1 if mirror else 1
        d.polygon([(cx - 58, cy - 70), (cx + 58, cy - 70 + s * 26),
                   (cx + 58, cy - 34 + s * 26), (cx - 58, cy - 34)], fill=PATCH)
        d.line([(cx - 58, cy - 34), (cx + 58, cy - 34 + s * 26)], fill=(20, 16, 20, 255), width=9)
        d.ellipse([cx - 20, cy - 6, cx + 6, cy + 20], fill=(255, 255, 255, 130))
    elif style == "wink":
        d.arc([cx - 46, cy - 46, cx + 46, cy + 46], 180, 360, fill=EYE_DARK, width=17)
    elif style == "curious":
        _eye_base(L, cx, cy, 54, 62, (62, 54, 62, 255), EYE_DARK)
        d.ellipse([cx - 54, cy - 62, cx + 54, cy + 62], outline=(20, 16, 20, 255), width=5)
        d.ellipse([cx - 28, cy - 52, cx + 8, cy - 16], fill=(255, 255, 255, 225))
        d.ellipse([cx + 12, cy + 8, cx + 30, cy + 26], fill=(255, 255, 255, 255))
    else:
        raise ValueError(f"unknown eye style {style!r}")


def _draw_mouth(d: ImageDraw.ImageDraw, style: str, tongue: bool = False):
    cx, cy = 480, 648
    if style == "smile":
        d.arc([cx - 62, cy - 44, cx + 62, cy + 52], 28, 152, fill=MOUTH_DARK, width=13)
    elif style == "open_smile":
        d.ellipse([cx - 58, cy - 30, cx + 58, cy + 66], fill=MOUTH_DARK)
        if tongue:
            d.ellipse([cx - 30, cy + 6, cx + 30, cy + 58], fill=TONGUE)
    elif style == "o":
        d.ellipse([cx - 26, cy - 14, cx + 26, cy + 38], outline=MOUTH_DARK, width=12)
    elif style == "frown":
        d.arc([cx - 56, cy - 18, cx + 56, cy + 70], 208, 332, fill=MOUTH_DARK, width=13)
    elif style == "wavy":
        pts = [(cx - 66 + i * 12, cy + 16 * math.sin(i * 1.5)) for i in range(12)]
        d.line(pts, fill=MOUTH_DARK, width=12, joint="curve")
    elif style == "yawn":
        d.ellipse([cx - 66, cy - 34, cx + 66, cy + 96], fill=MOUTH_DARK)
        d.ellipse([cx - 44, cy - 18, cx + 44, cy + 70], fill=(96, 70, 76, 255))
        d.ellipse([cx - 32, cy + 18, cx + 32, cy + 88], fill=TONGUE)
    elif style == "smirk":
        d.arc([cx - 62, cy - 44, cx + 62, cy + 52], 28, 140, fill=MOUTH_DARK, width=13)
        d.line([(cx + 40, cy + 30), (cx + 78, cy + 12)], fill=MOUTH_DARK, width=13)
    elif style == "small":
        d.arc([cx - 34, cy - 24, cx + 34, cy + 28], 28, 152, fill=MOUTH_DARK, width=10)
    else:
        raise ValueError(f"unknown mouth style {style!r}")


def _draw_brows(d: ImageDraw.ImageDraw, style: str):
    if style == "none":
        return
    # short soft brow strokes above the patches
    if style == "sad":  # inner ends lifted
        d.line([(300, 296), (392, 262)], fill=(40, 34, 40, 230), width=16)
        d.line([(660, 296), (568, 262)], fill=(40, 34, 40, 230), width=16)
    elif style == "concerned":
        d.line([(306, 288), (392, 252)], fill=(40, 34, 40, 230), width=15)
        d.line([(654, 288), (568, 252)], fill=(40, 34, 40, 230), width=15)
    elif style == "raised":  # curious: left brow up
        d.arc([300, 230, 420, 300], 200, 340, fill=(40, 34, 40, 230), width=15)


def _draw_leaf(d: ImageDraw.ImageDraw):
    """Signature tiny leaf tucked at the right ear base."""
    cx, cy = 648, 108
    d.ellipse([cx - 44, cy - 24, cx + 44, cy + 24], fill=LEAF_A)
    d.ellipse([cx - 44, cy - 24, cx + 2, cy + 24], fill=LEAF_B)
    d.line([(cx - 40, cy), (cx + 40, cy)], fill=(70, 100, 58, 255), width=7)
    d.line([(cx - 52, cy + 26), (cx - 40, cy + 44)], fill=(110, 140, 90, 255), width=9)


def _render_face(pose: Pose) -> Image.Image:
    L = _new()
    d = ImageDraw.Draw(L)
    # muzzle: soft light area around nose/mouth
    d.ellipse([480 - 132, 560 - 84, 480 + 132, 560 + 84], fill=(252, 250, 246, 110))
    # blush
    bl = BLUSH[:3] + (pose.blush,)
    if pose.cheek_lift:
        d.ellipse([250, 520, 350, 580], fill=bl)
        d.ellipse([610, 520, 710, 580], fill=bl)
    else:
        d.ellipse([258, 536, 348, 588], fill=bl)
        d.ellipse([612, 536, 702, 588], fill=bl)
    # eyes
    left_style = "wink" if pose.eye == "wink" else pose.eye
    right_style = "open" if pose.eye == "wink" else pose.eye
    _draw_eye(L, 362, 436, left_style, mirror=False)
    _draw_eye(L, 598, 432, right_style, mirror=True)
    # nose: dimensional rounded triangle
    d.polygon([(480 - 52, 548), (480 + 52, 548), (480, 606)], fill=NOSE)
    d.ellipse([480 - 52, 536, 480 + 52, 586], fill=NOSE)
    d.ellipse([452, 540, 486, 568], fill=NOSE_HI[:3] + (170,))
    # philtrum
    d.line([(480, 600), (480, 628)], fill=MOUTH_DARK, width=10)
    _draw_mouth(d, pose.mouth, tongue=pose.tongue)
    _draw_brows(d, pose.brow)
    _draw_leaf(d)
    # extras anchored to face
    if "tear" in pose.extras:
        _tear(d, 330, 520, 30)
    if "sweat" in pose.extras:
        _tear(d, 700, 330, 34, color=(140, 200, 245, 235))
    return L


def _tear(d: ImageDraw.ImageDraw, cx, cy, s, color=(140, 200, 245, 235)):
    d.ellipse([cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2], fill=color)
    d.polygon([(cx, cy - s * 1.1), (cx - s / 2.4, cy), (cx + s / 2.4, cy)], fill=color)
    d.ellipse([cx - s / 5, cy - s / 6, cx, cy + s / 8], fill=(255, 255, 255, 200))


def _extras_world(pose: Pose) -> Image.Image:
    """Extras positioned in world space (not rotating with head)."""
    L = _new()
    d = ImageDraw.Draw(L)
    if "zzz" in pose.extras:
        for i, (x, y, s) in enumerate(((700, 200, 46), (760, 130, 62), (830, 48, 80))):
            w = 11
            d.line([(x, y), (x + s, y)], fill=(140, 200, 245, 220), width=w)
            d.line([(x + s, y), (x, y + s)], fill=(140, 200, 245, 220), width=w)
            d.line([(x, y + s), (x + s, y + s)], fill=(140, 200, 245, 220), width=w)
    if "stars" in pose.extras:
        for cx, cy, r in ((200, 200, 34), (770, 180, 26), (830, 420, 22)):
            pts = []
            for i in range(8):
                a = math.pi / 4 * i - math.pi / 2
                rr = r if i % 2 == 0 else r * 0.45
                pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
            d.polygon(pts, fill=STAR)
    if "motion" in pose.extras:  # wave motion arcs near raised paw
        for r in (120, 155, 190):
            d.arc([845 - r, 380 - r, 845 + r, 380 + r], 245, 335, fill=(150, 150, 160, 170), width=12)
    return L


def _wave_arm() -> Image.Image:
    """Raised right arm for the playful wave, beside (not over) the head."""
    L = _new()
    _ellipse(L, 795, 495, 56, 135, BLACK_FUR, rotation=14)
    _ellipse(L, 782, 465, 20, 50, BLACK_HI[:3] + (100,), rotation=14)
    # paw pads hint
    d = ImageDraw.Draw(L)
    d.ellipse([765, 368, 815, 412], fill=BLACK_DEEP)
    return L


# ------------------------------------------------------------------ render ---

def render_pose(pose: Pose) -> Image.Image:
    """Render one master-resolution (960px) frame for the given pose."""
    # body (with optional wave arm replacing the resting right arm)
    body = _render_body(pose.wave)
    if pose.wave:
        body.alpha_composite(_wave_arm())
    body.alpha_composite(_body_shading(pose.wave))

    # head group (head + face rotate together around the neck)
    head = _render_head(pose)
    head.alpha_composite(_head_shading())
    head.alpha_composite(_render_face(pose))
    if pose.head_tilt or pose.head_dx or pose.head_dy:
        head = head.rotate(-pose.head_tilt, resample=Image.BICUBIC, center=(480, 640))
        dx, dy = pose.head_dx, pose.head_dy
    else:
        dx, dy = 0, 0
        # (dx/dy still applied below for API consistency)

    canvas = _new()
    if pose.bob:
        by = pose.bob
    else:
        by = 0
    # composite body then head (head offset by dx/dy + bob)
    tmp = _new()
    tmp.alpha_composite(body, (0, by))
    if dx or dy or pose.head_tilt:
        tmp2 = _new()
        tmp2.alpha_composite(head, (dx, dy + by))
        # keep head above body: paste head layer over
        canvas.alpha_composite(tmp)
        canvas.alpha_composite(tmp2)
    else:
        canvas.alpha_composite(tmp)
        canvas.alpha_composite(head, (0, by))
    canvas.alpha_composite(_extras_world(pose))
    return canvas


def render_runtime(pose: Pose) -> Image.Image:
    """Render a 240px runtime frame."""
    return render_pose(pose).resize((RUNTIME, RUNTIME), Image.LANCZOS)


@dataclass
class CharacterSpec:
    """Documents the master design (written to assets/source/DESIGN.md)."""

    name: str = "Doodle"
    species: str = "Giant panda (stylized companion)"
    master_resolution: int = MASTER
    runtime_resolution: int = RUNTIME
    light_direction: str = "soft key light from upper-left, consistent across all frames"
    palette: dict = field(default_factory=lambda: {
        "white fur": "#F7F4EF", "white shade": "#E9E3D7",
        "black fur": "#302C32", "black highlight": "#4E4854",
        "eye patch": "#363139", "nose": "#3E353C",
        "blush": "#F4A8AA", "leaf": "#7FB069 / #588A4A",
    })
    identity: tuple = (
        "Three-stroke fur tuft on crown",
        "Scalloped cheek fluff",
        "Subtly asymmetric eye patches (left slightly larger)",
        "Tiny two-tone leaf tucked at right ear base",
        "Warm-gray white fur, blue-black fur (never pure black)",
    )
