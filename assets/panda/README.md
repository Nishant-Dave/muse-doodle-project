# Panda animation assets (Phase 2A + 2C)

Character artwork is generated from a single parametric rig
(`tools/character_rig.py`) — every frame derives from one master design, so
proportions, patches, fur, and lighting are consistent across expressions by
construction. See `assets/source/DESIGN.md` for the design rationale and
`assets/source/master_960.png` for the high-res master reference.

Regenerate everything (master + runtime frames + manifest):

    python3 tools/generate_assets_v2.py

Requires Pillow (tool-time only, not an app runtime dependency).

Validate the generated assets:

    python3 tools/validate_assets.py

- Master: 960x960 PNG, transparent background.
- Runtime: 240x240 PNG (LANCZOS downscale), matching the desktop window size.
- Previous Phase 1 assets are preserved under `assets/archive/panda_v1/`.

## Animations

| Animation   | Frames | FPS | Loop | Used for |
|-------------|--------|-----|------|----------|
| `idle`      | 4      | 2   | yes  | Default resting state; calm breathing |
| `blink`     | 3      | 10  | no   | Idle personality (also "Okay" mood ack) |
| `yawn`      | 5      | 3   | no   | Idle personality; sleepy reaction |
| `happy`     | 4      | 6   | no   | "Happy" mood reaction; joyful bounce |
| `curious`   | 4      | 4   | no   | Idle personality; head tilt, raised brow |
| `sleepy`    | 3      | 2   | no   | Drowsy reaction; half-mast lids |
| `surprised` | 3      | 8   | no   | Startled reaction (reserved for future use) |
| `dizzy`     | 5      | 5   | no   | After a long (>120px) or slow (>1.5s) drag |
| `sad`       | 3      | 2   | no   | "Sad" mood reaction |
| `stressed`  | 3      | 4   | no   | "Stressed" mood reaction |
| `playful`   | 4      | 6   | no   | Click/poke reaction: wink + wave |
| `drag`      | 2      | 5   | yes  | While the panda is being dragged |
| `walk`      | 6      | 8   | yes  | Wander locomotion: waddle cycle (Phase 2C) |
| `gaze_left` | 4      | 6   | no   | Look left: head turn + shifted gaze (Phase 2C) |
| `gaze_right`| 4      | 6   | no   | Look right: head turn + shifted gaze (Phase 2C) |
| `land`      | 4      | 8   | no   | Landing settle after glide/wander (Phase 2C) |

`manifest.json` maps each animation name to its frame files, fps, loop flag,
and description. `AssetLoader` reads this manifest; unknown names fail
gracefully (warning + no-op).

## Transitions (Phase 2C)

`AnimationPlayer.play(name, loop, fade_ms)` cross-fades from the current
frame to the new animation over `fade_ms` (alpha blend, smoothstep easing,
single reused QTimer). Fades are used only for compatible pose pairs:

| Transition | Fade | Why |
|------------|------|-----|
| idle -> walk (wander start) | 150ms | similar upright poses, clean blend |
| drag -> idle (glide start) | 120ms | softens the pose change |
| walk/idle -> land (arrival) | 100ms | eases into the crouch |

All other transitions (reactions, moods, dizzy) cut directly: cross-fading
incompatible faces would ghost. Interrupted fades cancel cleanly and restart
from the current blended frame.

## Behavior mapping (behavior/engine.py)

- Poke (click) -> `playful`
- Drag start -> `drag` (loop); drag end -> `dizzy` if long/slow, else glide
  (fast) or `idle`; glide/wander arrival -> `land` settle -> `idle`
- Drag start -> `drag` (loop)
- Personality scheduler (weighted 4–9s) -> `blink`, `curious`, `yawn`,
  `sleepy`, `happy`, `playful`, `surprised`, `gaze_left/right`, `wander`
  (cooldowns + history, ~18% calm inactivity)
- Cursor approach -> `gaze_left`/`gaze_right` (side-aware, cooldown 20s)
- Wander -> `walk` loop with facing; arrival -> `land`
- Moods -> happy: `happy`/`playful`, okay: `blink`, sad: `sad`,
  stressed: `stressed`/`yawn`
