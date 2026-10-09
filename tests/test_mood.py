"""Mood tests: session state and popup interaction."""

from doodle_mvp.mood.mood import VALID_MOODS, MoodState
from doodle_mvp.mood.mood_popup import MoodPopup
from PySide6.QtWidgets import QPushButton


def test_mood_state_defaults_to_unset():
    state = MoodState()
    assert state.current is None
    assert state.label == "Not set"


def test_mood_state_accepts_all_valid_moods():
    state = MoodState()
    for mood in VALID_MOODS:
        assert state.set_mood(mood) is True
        assert state.current == mood


def test_mood_state_rejects_unknown_mood():
    state = MoodState()
    assert state.set_mood("happy") is True
    assert state.set_mood("ecstatic") is False
    assert state.current == "happy"  # unchanged


def test_mood_state_clear():
    state = MoodState()
    state.set_mood("sad")
    state.clear()
    assert state.current is None


def test_popup_emits_chosen_mood(qapp, emitted):
    popup = MoodPopup()
    popup.mood_chosen.connect(emitted.append)
    buttons = popup.findChildren(QPushButton)
    assert len(buttons) == 4  # happy, okay, sad, stressed
    buttons[2].click()  # "Sad"
    assert emitted == ["sad"]
    popup.close()


def test_popup_feedback_then_auto_close(qapp):
    popup = MoodPopup()
    popup.show()
    qapp.processEvents()
    buttons = popup.findChildren(QPushButton)
    buttons[0].click()
    # Buttons hide, feedback shows the confirmation.
    assert all(not b.isVisible() for b in buttons)
    assert "Happy" in popup._feedback.text()
    popup._feedback_timer.timeout.emit()  # simulate the 1.2s timer
    qapp.processEvents()
    assert not popup.isVisible()
    popup.close()


def test_mood_selection_reaches_behavior_engine(qapp, bus, emitted):
    import random

    from doodle_mvp.behavior import events as E
    from doodle_mvp.behavior.engine import BehaviorEngine

    engine = BehaviorEngine(bus, rng=random.Random(42))
    engine.play_requested.connect(lambda name, loop: emitted.append((name, loop)))
    engine.start()
    bus.publish(E.MOOD_SELECTED, {"mood": "stressed"})
    assert emitted[-1] == ("stressed", False)
    engine.shutdown()
