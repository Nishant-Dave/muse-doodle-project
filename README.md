# Doodle — Desktop Companion MVP (Phase 1)

A friendly panda that lives on the Windows desktop. Small, frameless,
transparent, draggable, with idle personality, click reactions, mood
registration, and clean lifecycle. Built with Python + PySide6, no cloud
services, no database, everything local.

This is an independent Phase 1 implementation: desktop shell, animation
system, behavior engine, mood registration, preferences.

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
- **Click / poke** the panda for a playful reaction.
- **Double-click** (or right-click → "How are you feeling?…", or the tray
  icon menu → "Log mood…") to open the mood popup: Happy / Okay / Sad /
  Stressed. The panda reacts and confirms "Saved: … ✓".
- **Right-click** the panda (or tray menu) to toggle **Animations** on/off
  or **Quit**.
- **Tray icon**: Show/Hide, mood, animations toggle, quit.

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

Visual/platform behavior that automated tests cannot verify — run through on
Windows:

- [ ] Launch: panda appears as a floating companion, no title bar, no ugly
      rectangle around the artwork (transparent background).
- [ ] Panda stays above ordinary windows but doesn't block the taskbar.
- [ ] Drag the panda: it follows the cursor with a stable offset, shows the
      drag pose, doesn't jump or get stuck.
- [ ] Release after a short drag: returns to idle smoothly.
- [ ] Release after a long/fast drag: plays the dizzy reaction, then idle.
- [ ] Click/poke: playful surprise → happy bounce, then back to idle.
- [ ] Rapid repeated clicks: no stutter, no stacked animations.
- [ ] Leave idle 1–2 minutes: occasional blinks, rare yawn, never mechanical.
- [ ] Double-click / right-click menu / tray → mood popup opens near panda.
- [ ] Select each mood: panda reacts (happy bounce / blink / sad / stressed)
      and popup confirms "Saved: … ✓", then closes by itself.
- [ ] Popup dismisses by clicking outside it and with Escape.
- [ ] Toggle Animations off: panda freezes on a static frame, idle stops.
      Toggle on: idle animation resumes.
- [ ] Move panda, quit, relaunch: position is restored.
- [ ] Quit via menu/tray: process exits, no lingering python process, no
      timers left running (check Task Manager).
- [ ] Restart: starts in the default/saved state with no errors.

## Project status (honest)

- Implemented and automatically tested: app lifecycle, animation system
  (9 states), drag/click input, behavior priorities, mood registration +
  reactions, QSettings preferences, platform adapter structure, clean
  shutdown. 47/47 tests pass.
- Implemented, needs manual visual verification: transparency, always-on-top
  feel, animation smoothness/feel, tray on Windows (see checklist above).
- Not implemented (out of Phase 1 scope): AI/LLM, journaling, SQLite,
  calendar/browser/email integrations, notifications, cloud sync, installer.
