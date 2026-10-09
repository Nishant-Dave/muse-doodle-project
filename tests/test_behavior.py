"""BehaviorEngine tests: priorities, transitions, no conflicting animations."""

from doodle_mvp.behavior import events as E
from doodle_mvp.behavior.engine import DRAGGING, IDLE, REACTING


def _start(engine, emitted):
    engine.play_requested.connect(lambda name, loop: emitted.append((name, loop)))
    engine.static_requested.connect(lambda name: emitted.append(("static:" + name, False)))
    engine.start()
    return emitted


def test_start_plays_idle_loop(engine, emitted):
    _start(engine, emitted)
    assert emitted == [("idle", True)]
    assert engine.state == IDLE


def test_start_is_idempotent(engine, emitted):
    _start(engine, emitted)
    engine.start()
    engine.bus.publish(E.POKE)
    pokes = [e for e in emitted if e[0] == "playful"]
    assert len(pokes) == 1  # no duplicated handlers


def test_poke_plays_once_and_returns_to_idle(engine, emitted):
    _start(engine, emitted)
    engine.handle_poke()
    assert emitted[-1] == ("playful", False)
    assert engine.state == REACTING
    # Repeated poke while reacting is ignored: no stacked animations.
    engine.handle_poke()
    assert emitted[-1] == ("playful", False)
    engine.on_animation_finished("playful")
    assert emitted[-1] == ("idle", True)
    assert engine.state == IDLE


def test_drag_preempts_and_short_drag_returns_to_idle(engine, emitted):
    _start(engine, emitted)
    engine.handle_poke()  # reacting...
    engine.handle_drag_start()  # drag wins
    assert emitted[-1] == ("drag", True)
    assert engine.state == DRAGGING
    engine.handle_poke()  # ignored while dragging
    assert emitted[-1] == ("drag", True)
    engine.handle_drag_end({"distance_px": 10.0, "duration_s": 0.4})
    assert emitted[-1] == ("idle", True)
    assert engine.state == IDLE


def test_long_drag_ends_with_dizzy(engine, emitted):
    _start(engine, emitted)
    engine.handle_drag_start()
    engine.handle_drag_end({"distance_px": 500.0, "duration_s": 0.5})
    assert emitted[-1] == ("dizzy", False)
    assert engine.state == REACTING
    engine.on_animation_finished("dizzy")
    assert emitted[-1] == ("idle", True)


def test_slow_drag_ends_with_dizzy(engine, emitted):
    _start(engine, emitted)
    engine.handle_drag_start()
    engine.handle_drag_end({"distance_px": 5.0, "duration_s": 3.0})
    assert emitted[-1] == ("dizzy", False)


def test_mood_selects_matching_reaction(engine, emitted):
    _start(engine, emitted)
    engine.handle_mood({"mood": "sad"})
    assert emitted[-1] == ("sad", False)
    engine.on_animation_finished("sad")
    engine.handle_mood({"mood": "happy"})
    assert emitted[-1] == ("happy", False)
    engine.on_animation_finished("happy")
    engine.handle_mood({"mood": "stressed"})
    assert emitted[-1] == ("stressed", False)
    engine.on_animation_finished("stressed")
    engine.handle_mood({"mood": "okay"})
    assert emitted[-1] == ("blink", False)


def test_mood_ignored_while_dragging(engine, emitted):
    _start(engine, emitted)
    engine.handle_drag_start()
    engine.handle_mood({"mood": "happy"})
    assert emitted[-1] == ("drag", True)
    assert engine.state == DRAGGING


def test_unknown_mood_ignored(engine, emitted):
    _start(engine, emitted)
    engine.handle_mood({"mood": "ecstatic"})
    assert emitted == [("idle", True)]
    assert engine.state == IDLE


def test_scheduled_activity_plays_personality_one_shot(engine, emitted):
    _start(engine, emitted)
    engine._on_schedule_timeout()
    name, loop = emitted[-1]
    assert name in ("blink", "yawn", "curious", "sleepy", "happy", "playful", "surprised")
    assert loop is False
    assert engine.state == REACTING
    assert name in engine._scheduler.history  # recorded for cooldowns


def test_scheduled_activity_ignored_when_busy(engine, emitted):
    _start(engine, emitted)
    engine.handle_drag_start()
    engine._on_schedule_timeout()
    assert emitted[-1] == ("drag", True)


def test_disabling_animations_shows_static_and_ignores_input(engine, emitted):
    _start(engine, emitted)
    engine.set_animations_enabled(False)
    assert emitted[-1] == ("static:idle", False)
    assert engine.state == IDLE
    engine.handle_poke()
    engine._on_schedule_timeout()
    engine.handle_mood({"mood": "happy"})
    assert emitted[-1] == ("static:idle", False)  # nothing new played
    engine.set_animations_enabled(True)
    assert emitted[-1] == ("idle", True)


def test_events_flow_through_bus(engine, emitted, bus):
    _start(engine, emitted)
    bus.publish(E.POKE)
    assert emitted[-1] == ("playful", False)
    bus.publish(E.DRAG_START)
    assert emitted[-1] == ("drag", True)
    bus.publish(E.DRAG_END, {"distance_px": 1.0, "duration_s": 0.1})
    assert emitted[-1] == ("idle", True)
    bus.publish(E.MOOD_SELECTED, {"mood": "sad"})
    assert emitted[-1] == ("sad", False)
