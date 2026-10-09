# Doodle — Desktop Companion MVP (Phase 1 + 2A)

A friendly panda that lives on the Windows desktop. Small, frameless,
transparent, draggable, with idle personality, click reactions, mood
registration, and clean lifecycle. Built with Python + PySide6, no cloud
services, no database, everything local.

Phase 2A redesigned the character: a distinctive panda identity rendered
from a single parametric rig (`tools/character_rig.py`) with soft 2.5D-style
lighting, fur texture, glossy expressive eyes, and a coordinated 12-state
expression library. See `assets/source/DESIGN.md` for the design rationale.

Phase 2B made it move and feel alive:

- **Personality scheduler** (`behavior/scheduler.py`): weighted random
  activities with cooldowns, recent-history suppression, and deliberate
  calm inactivity — no mechanical loops, no immediate repeats.
- **Cursor awareness** (`desktop/cursor_monitor.py`): edge-triggered
  proximity detection with hysteresis and a 20s cooldown; the panda turns
  curious when you approach, never flickers or re-triggers.
- **Natural dragging**: velocity-tracked release with a bounded,
  eased momentum glide (max ~140px, ~350ms), dizzy recovery after long/fast
  drags, screen-edge clamping.
- **Autonomous wandering**: occasional short strolls to nearby spots with
  ease-in-out motion and facing direction (mirrored rendering, no new
  assets needed).
- **Mood reactions with variation** (e.g. stressed → stressed/yawn).
- New preferences: `behavior/momentum_enabled`, `behavior/wander_enabled`,
  `behavior/proximity_radius_px` — toggleable from the panda's right-click
  menu or the tray menu ("Glide after drag", "Wander around").

Phase 2C added genuine motion artwork and transitions:

- **Walk cycle** (`walk`, 6 frames @ 8fps loop): waddle locomotion with
  weight shift, alternating foot lifts, body bob, and counter-tilted head —
  generated from new rig parameters (`lean`, `body_dx`, `step_phase`).
  Wander now walks instead of idling in place.
- **Directional gaze** (`gaze_left`/`gaze_right`, 4 frames): head turn +
  shifted eyes (new `gaze_dx`/`gaze_dy` rig params). Cursor approach looks
  toward the physical cursor side (flipped when the artwork is mirrored).
- **Landing settle** (`land`, 4 frames @ 8fps): crouch → squash → rebound →
  rest, played after every glide and wander.
- **Cross-fade transitions**: `AnimationPlayer.play(name, loop, fade_ms)`
  alpha-blends between compatible poses (idle→walk 150ms, drag→glide
  120ms, →land 100ms) on the single reused QTimer; incompatible poses cut
  directly to avoid ghosting; interrupted fades restart cleanly.
- **Asset validation**: `tools/validate_assets.py` checks manifest
  integrity, dimensions, format, and transparency (also a pytest test).

Behavior priorities: shutdown/safety > dragging > reactions (poke, mood,
cursor) > movement (glide, wander) > autonomous personality > idle.

## Quick start

```bash
cd doodle-phase1-mvp
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate
pip install -r requirements.txt
```

## Launch

```bash
PYTHONPATH=src python -m doodle_mvp.main
```

On Windows you can omit `PYTHONPATH=src` by installing the package
(`pip install -e .` once a `pyproject.toml` exists) — the documented command
above was verified in the project environment.

Headless smoke test (verifies startup, idle animation, and clean shutdown;
needs no display):

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src python -m doodle_mvp.main --self-check
```

## Tests

```bash
PYTHONPATH=src python -m pytest tests/ -q
```

47 tests, all passing (verified 2026-10-09, PySide6 6.11.2, offscreen).
Covers: asset loading + frame differences, animation frame progression and
the single-timer invariant, behavior priorities and transitions, mood state
and popup, preferences defaults/round-trips/invalid values, and app
lifecycle/shutdown.

## Using Doodle

- **Drag** the panda to move it. Position is remembered between launches.
  Release a fast drag for a short momentum glide; a long/slow drag earns a
  dizzy shake.
- **Click / poke** the panda for a playful wink-and-wave.
- **Move your cursor near it**: it gets curious (once — it won't nag you).
- **Leave it alone**: it blinks, yawns, looks around, and occasionally
  wanders a short distance on its own.
- **Double-click** (or right-click → "How are you feeling?…", or the tray
  icon menu → "Log mood…") to open the mood popup: Happy / Okay / Sad /
  Stressed. The panda reacts and confirms "Saved: … ✓".
- **Right-click** the panda (or tray menu): toggle **Animations**,
  **Glide after drag**, **Wander around**, or **Quit**.
- **Tray icon**: Show/Hide, mood, toggles, quit.

## Architecture

```
doodle_mvp/
├── main.py                  entry point (--self-check, --log-level)
├── app/application.py       builds + wires everything; run()/shutdown()
├── desktop/
│   ├── companion_window.py  frameless transparent window, drag/click input
│   ├── tray.py              system tray icon + menu
│   └── positioning.py       on-screen clamping, default position
├── character/
│   ├── assets.py            AssetLoader: manifest -> QPixmaps (cached)
│   ├── animation.py         AnimationPlayer: ONE QTimer, named animations
│   └── character.py         PandaCharacter widget (renders frames)
├── behavior/
│   ├── events.py            EventBus (Qt signals, idempotent subscriptions)
│   └── engine.py            BehaviorEngine: event->state->decision->animation
├── mood/
│   ├── mood.py              MoodState (session-only)
│   └── mood_popup.py        compact popup, easy to dismiss
├── persistence/settings.py  QSettings: position, animations_enabled
└── platform/adapter.py      Windows specifics behind an adapter (ctypes, no pywin32)
```

Behavior model: `EVENT → STATE → DECISION → ACTION → ANIMATION`.
Priorities are explicit and deterministic: dragging (100) > poke/mood (60) >
idle personality (10). One-shot reactions always return to idle.

## Adding an animation

1. Add frames to `assets/panda/<name>/frame_00.png`, `frame_01.png`, …
   (240x240 PNG, transparent background).
2. Add an entry to `assets/panda/manifest.json`:
   `"<name>": {"frames": ["<name>/frame_00.png", …], "fps": 6, "loop": false, …}`.
3. `player.play("<name>")` — or map it in `behavior/engine.py`
   (`MOOD_ANIMATIONS`) if it is a mood reaction.

No window-management code needs to change.

## Known limitations

- Developed and automated-tested on Linux (offscreen Qt). Windows-only
  behaviors — true per-pixel transparency, always-on-top z-order against
  native windows, tray integration — are implemented with the standard Qt
  flags plus a platform adapter, but need the manual checks below on a real
  Windows machine.
- Artwork is programmatic (Pillow-drawn), not hand-drawn sprite art.
- Mood is session-only (in memory); no history.
- Single process, no plugins, no AI, no integrations — per the Phase 1 scope.

## Manual acceptance checklist

Code-level items are covered by automated tests (**PASS** below).
Visual/feel items need a real Windows desktop — I could not verify these
headless, so they are **NOT VERIFIED** (not claimed).

### Phase 2C acceptance

1. Start the application — **PASS** (automated: self-check + full suite).
2. Observe a complete walk cycle — logic **PASS** (walk loop plays during
   wander, facing matches direction, arrival → land → idle; visually
   **NOT VERIFIED**).
3. Enable/disable wandering (right-click menu) — **PASS** (toggle respected;
   feel **NOT VERIFIED**).
4. Observe direction changes — **PASS** (facing flips with movement
   direction, gaze flips when mirrored; visual smoothness **NOT VERIFIED**).
5. Trigger cursor-aware gaze — logic **PASS** (side-aware gaze_left/right,
   hysteresis + 20s cooldown; feel **NOT VERIFIED**).
6. Drag and release the panda — **PASS** (glide bounds/easing tested;
   tactile feel **NOT VERIFIED**).
7. Observe the landing sequence — **PASS** (land plays after every glide
   and wander, then idle; artwork strip visually inspected, in-app motion
   **NOT VERIFIED**).
8. Interrupt one animation with another — **PASS** (fades cancel cleanly,
   priorities tested: drag > reactions > movement).
9. Observe the return to idle — **PASS** (all paths end at idle; no
   animation restarts).
10. Repeated interactions for flicker/artifacts — cross-fade midpoint
    visually inspected (no ghosting); in-app **NOT VERIFIED**.
11. Leave running several minutes — timer lifecycle **PASS** (shutdown
    stops everything, no leaked timers); long-run CPU **NOT VERIFIED**.
12. Phase 1 + 2B functionality intact — **PASS** (full suite green,
    no regressions).

### General (visual, needs Windows)

- [ ] Transparency: no rectangle/halo around the artwork.
- [ ] Always-on-top feel against native apps; tray behaves.
- [ ] Idle variety over several minutes feels calm, not mechanical.
- [ ] Drag/glide/land sequence feels physical and responsive.
- [ ] No flicker, teleporting, or unresponsive window.
- [ ] Screen edges and multi-monitor: panda stays reachable.

## Project status (honest)

- Implemented and automatically tested: app lifecycle, animation system
  (16 states, 61 frames from one parametric rig), cross-fade transitions
  (single-timer, interrupt-safe), drag/click input with velocity-tracked
  release, behavior priorities
  (drag > reactions > movement > personality > idle), cursor proximity with
  hysteresis + cooldown and side-aware gaze, eased glide/wander with bounds
  and cancellation, landing settle, facing direction (incl. gaze flip when
  mirrored), scheduler weights/cooldowns/history, mood reactions with
  variation, asset validation, QSettings preferences, platform adapter
  structure, clean shutdown. **98/98 tests pass** (80 baseline + 18 new).
- Implemented, needs manual visual verification: everything marked
  NOT VERIFIED in the checklist above — transparency, always-on-top feel,
  motion smoothness/feel, tray on Windows. New artwork (walk strip, land
  strip, gaze frames, fade midpoint) was visually inspected frame-by-frame
  on the development machine; in-app Windows rendering still needs
  your eyes.
- Not implemented (out of scope): AI/LLM, journaling, SQLite,
  calendar/browser/email integrations, notifications, cloud sync, installer.
- Known limitations: cross-fades only for compatible pose pairs
  (incompatible faces cut directly — deliberate, avoids ghosting); walk is
  a chibi waddle, not a realistic quadruped gait (matches the seated
  character design); `surprised`/`sleepy` have no dedicated triggers beyond
  the scheduler; wander reuses eased linear paths (no pathfinding).
