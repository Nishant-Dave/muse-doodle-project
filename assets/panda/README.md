# Panda animation assets (Phase 2A)

Character artwork is generated from a single parametric rig
(`tools/character_rig.py`) — every frame derives from one master design, so
proportions, patches, fur, and lighting are consistent across expressions by
construction. See `assets/source/DESIGN.md` for the design rationale and
`assets/source/master_960.png` for the high-res master reference.

Regenerate everything (master + runtime frames + manifest):

    python3 tools/generate_assets_v2.py

Requires Pillow (tool-time only, not an app runtime dependency).

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

`manifest.json` maps each animation name to its frame files, fps, loop flag,
and description. `AssetLoader` reads this manifest; unknown names fail
gracefully (warning + no-op).

## Behavior mapping (behavior/engine.py)

- Poke (click) -> `playful`
- Drag start -> `drag` (loop); drag end -> `dizzy` if long/slow, else `idle`
- Idle tick (randomized 4–9s) -> `blink` 70%, `curious` 15%, `yawn` 15%
- Moods -> happy: `happy`, okay: `blink`, sad: `sad`, stressed: `stressed`
