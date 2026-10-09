"""AnimationPlayer tests: frame progression, single timer, graceful failure."""

from PySide6.QtCore import QTimer

from doodle_mvp.character.animation import AnimationPlayer


def test_play_starts_single_timer(player, emitted):
    assert player.play("idle")
    assert player.current_animation == "idle"
    assert player.is_playing
    assert len(player.findChildren(QTimer)) == 1


def test_tick_advances_and_loops(player):
    player.play("idle")  # 3 frames, loop=True
    first = player.timer  # noqa: F841 (kept for clarity)
    player.tick()
    player.tick()
    assert player.is_playing  # still looping
    player.tick()  # wraps to frame 0
    assert player.is_playing
    assert player.current_animation == "idle"


def test_one_shot_emits_finished_and_stops(player, emitted):
    player.animation_finished.connect(lambda name: emitted.append(name))
    assert player.play("blink", loop=False)  # 3 frames
    player.tick()  # frame 1
    player.tick()  # frame 2 (last)
    player.tick()  # past the end -> finished
    assert emitted == ["blink"]
    assert not player.is_playing
    assert player.current_animation is None


def test_unknown_animation_keeps_current_state(player):
    assert player.play("idle")
    assert player.play("nope") is False
    assert player.current_animation == "idle"
    assert player.is_playing


def test_replay_does_not_create_extra_timers(player):
    player.play("idle")
    timer = player.timer
    for _ in range(5):
        player.play("poke")
        player.play("idle")
    assert player.timer is timer
    assert len(player.findChildren(QTimer)) == 1
    assert player.is_playing


def test_frame_changed_emitted_on_play_and_tick(player, emitted):
    player.frame_changed.connect(emitted.append)
    player.play("poke")
    assert len(emitted) == 1  # first frame on play
    player.tick()
    assert len(emitted) == 2


def test_show_static_displays_first_frame_without_timer(player, emitted):
    player.frame_changed.connect(emitted.append)
    assert player.show_static("idle")
    assert not player.is_playing
    assert player.current_animation == "idle"
    assert len(emitted) == 1
    assert player.show_static("nope") is False


def test_shutdown_stops_timer_and_clears_cache(player, assets):
    player.play("idle")
    assert assets.frames_for("idle")  # populates cache
    player.shutdown()
    assert not player.is_playing
    assert player.current_animation is None
    player.shutdown()  # idempotent
