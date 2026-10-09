# Doodle — Master Character Design (Phase 2A)

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
