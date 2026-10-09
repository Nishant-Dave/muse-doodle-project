# Shimeji Gap Analysis — Doodle Phase 2D

Reference behavior compiled from: the two user-supplied screen recordings
(BMO desktop companion, red crewmate on a web page — both the Shimeji
browser extension), the Shimeji-ee/Shimeji-Desktop projects (documented
required behaviors: **ChaseMouse, Fall, Dragged, Thrown**), and webmeji
(walk/sit/dance/trip, jump to screen edges, hang/climb, fall, hover
reaction, drag). Observed behavior is stated as observed; inferences are
marked *(inference)*.

Doodle's current state verified against the actual repo at `phase-2c`
(98/98 tests). No Shimeji code or artwork is copied; only interaction
principles are reimplemented with Doodle's own panda.

## Comparison matrix

| Interaction / quality | Shimeji reference (observed) | Current Doodle (verified) | Required improvement |
|---|---|---|---|
| Walking & locomotion | Walks L/R with cycle, climbs walls/windows, trips, dances; speed matches cadence *(inference: per-frame step tables)* | 6-frame waddle @8fps, ease-in-out wander ≤~254px, facing via mirror | Directed walk ("come here"); keep conservative — no climbing (no art, wrong for a panda) |
| Falling | Falls with accelerating gravity off surfaces; thrown characters tumble | Glide is flat ease-out; no gravity | Gravity drop: downward fast release → accelerating fall to screen bottom → land settle |
| Drag & throw | Grab → drag → throw with strong momentum | Velocity-tracked release, bounded glide ≤140px/350ms, dizzy on long/slow | Keep bounded (deliberate deviation: control > chaos); add fall branch for downward throws |
| Cursor reactions | Hover → special animation; "sit and face mouse"; "chase mouse" | Gaze L/R on approach, hysteresis + 20s cooldown | Dwell → face cursor (facing flip after ~2.5s lingering) |
| Idle autonomy | Sit/stand/dance/trip chosen randomly; calm pauses | Weighted scheduler: weights, cooldowns, history, 18% inactivity | Adequate; add on-demand "take a walk" |
| Transitions | Mostly hard cuts between sprite poses | Cross-fades for compatible poses (150/120/100ms), cuts elsewhere | Already at/above reference; keep |
| User-triggered actions | Right-click menu: walk-and-sit, jump to wall, pull up, throw, chase mouse… | Menu has toggles only | "Come here" + "Take a walk" menu actions |
| Multi-character | "Split into two", up to 10 pets | Single panda (scope) | Out of scope — not implemented |
| Idle CPU | Lightweight timers | One timer per subsystem, short-lived | Keep; verify no regression |

## Deliberate deviations (not gaps)

- **Bounded momentum.** Shimeji throws fly across the screen; Doodle's glide
  stays ≤140px and falls stop at the screen edge. Predictability is a
  feature for a companion that shares a work desktop.
- **No cursor chasing.** Shimeji's "chase mouse" is fun for a toy, annoying
  for a companion. Doodle gets single-shot "come here" instead.
- **No climbing.** Requires climbing artwork and surface detection; a panda
  scaling your VS Code window adds little.
- **Single panda.** No split/multiply.

## Phase 2D scope (this document's implementation)

1. Gravity drop on downward fast release (mover `fall_to`, ease-in).
2. "Come here" directed walk (menu + tray, interruptible, clamped).
3. "Take a walk" on-demand wander (menu + tray).
4. Cursor dwell → face-the-cursor facing (monitor dwell timer, engine flip).
5. Tests + docs; no new artwork (fall reuses `surprised` loop honestly).
