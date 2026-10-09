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

Items marked **(auto)** are covered by automated tests. Items marked
**(visual)** need your eyes on a real Windows desktop.

- [ ] **(visual)** Launch: panda appears floating, transparent, no title bar.
- [ ] **(visual)** Leave idle several minutes: blinks, occasional yawn /
      curious tilt / rare playful moment; long calm pauses; nothing
      mechanical or repetitive.
- [ ] **(visual)** Move cursor slowly toward it: curious reaction once, then
      calm while cursor stays.
- [ ] **(visual)** Move cursor rapidly past it: at most one reaction, no
      flicker or animation spam.
- [ ] **(auto)** Cursor hysteresis/cooldown logic (tests/test_cursor.py).
- [ ] **(visual)** Hover, click, poke repeatedly: playful wink+wave each
      poke, no stacked/stuttering animations.
- [ ] **(visual)** Drag slowly across screen: follows with stable offset,
      drag pose, no lag or jumping.
- [ ] **(visual)** Release a fast drag: short eased glide that settles
      (bounded ~140px); release a long/slow drag: dizzy then idle.
- [ ] **(auto)** Glide bounds, easing shape, cancellation, wander target
      bounds (tests/test_mover.py, test_behavior_2b.py).
- [ ] **(visual)** Interrupt a wander with a drag or click: movement stops
      immediately, reaction plays.
- [ ] **(visual)** Select each mood: matching reaction with slight
      variation; returns to idle naturally.
- [ ] **(visual)** Wander: occasionally strolls a short distance facing the
      right way; never leaves the screen or covers your work aggressively.
- [ ] **(visual)** Toggle "Glide after drag" / "Wander around" off in the
      right-click menu: behavior stops; toggle back on: resumes.
- [ ] **(visual)** Leave running 30+ minutes: no slowdown, no runaway
      timers, no CPU spin (check Task Manager).
- [ ] **(visual)** Screen edges and multi-monitor: panda stays reachable.
- [ ] **(auto)** Timer cleanup on shutdown; no duplicated handlers;
      animation never restarts back-to-back (tests/test_lifecycle.py,
      test_behavior_2b.py).
- [ ] **(visual)** No flickering, teleporting, or unresponsive window at
      any point.

## Project status (honest)

- Implemented and automatically tested: app lifecycle, animation system
  (12 states, 43 frames from one parametric rig), drag/click input with
  velocity-tracked release, behavior priorities
  (drag > reactions > movement > personality > idle), cursor proximity with
  hysteresis + cooldown, eased glide/wander with bounds and cancellation,
  facing direction, scheduler weights/cooldowns/history, mood reactions
  with variation, QSettings preferences, platform adapter structure, clean
  shutdown. **80/80 tests pass** (47 baseline + 33 new).
- Implemented, needs manual visual verification: everything marked
  (visual) in the checklist above — transparency, always-on-top feel,
  motion smoothness/feel, tray on Windows. Motion logic is unit-tested;
  how it *feels* needs your eyes.
- Not implemented (out of scope): AI/LLM, journaling, SQLite,
  calendar/browser/email integrations, notifications, cloud sync, installer.
- Known limitations: no true frame blending (transitions are paced
  one-shots, not cross-fades — stated honestly, not claimed); gaze is the
  curious head-tilt reaction (assets have no directional pupils);
  `surprised`/`sleepy` exist but have no autonomous trigger beyond the
  scheduler; wander uses the idle loop (no walk-cycle artwork).
