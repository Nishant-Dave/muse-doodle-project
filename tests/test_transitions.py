"""Cross-fade transition tests: blending, interruption, cleanup."""

from doodle_mvp.character.animation import AnimationPlayer


def _pixels(pixmap):
    return bytes(pixmap.toImage().constBits())


def test_fade_blends_between_animations(qapp, assets, emitted):
    player = AnimationPlayer(assets)
    player.frame_changed.connect(emitted.append)
    assert player.play("idle")
    idle_first = assets.frames_for("idle")[0]
    walk_first = assets.frames_for("walk")[0]
    assert player.play("walk", loop=True, fade_ms=150)
    assert player.is_fading
    mid = player.fade_step(0.5)
    assert mid is not None
    # midpoint is a genuine blend: differs from both endpoints
    assert _pixels(mid) != _pixels(idle_first)
    assert _pixels(mid) != _pixels(walk_first)
    # signal delivery copies the pixmap wrapper; compare pixels, not identity
    assert _pixels(emitted[-1]) == _pixels(mid)
    done = player.fade_step(1.0)
    assert not player.is_fading
    assert _pixels(done) == _pixels(walk_first)
    assert player.current_animation == "walk"
    player.shutdown()


def test_fade_uses_single_timer(qapp, assets):
    player = AnimationPlayer(assets)
    timer = player.timer
    player.play("idle")
    player.play("walk", fade_ms=150)
    assert player.timer is timer  # no second timer created
    player.fade_step(1.0)
    assert player.timer is timer
    player.shutdown()


def test_fade_interruption_starts_from_current_blend(qapp, assets, emitted):
    player = AnimationPlayer(assets)
    player.frame_changed.connect(emitted.append)
    player.play("idle")
    player.play("walk", fade_ms=150)
    player.fade_step(0.5)
    blended = player._current
    # interrupting with a new fade cancels the old one cleanly
    assert player.play("land", loop=False, fade_ms=100)
    assert player.is_fading
    assert player._fade["source"] is blended
    player.fade_step(1.0)
    assert not player.is_fading
    assert player.current_animation == "land"
    player.shutdown()


def test_tick_resolves_active_fade(qapp, assets, emitted):
    player = AnimationPlayer(assets)
    player.frame_changed.connect(emitted.append)
    player.play("idle")
    player.play("walk", fade_ms=150)
    assert player.is_fading
    player.tick()  # deterministic tests resolve the fade, then advance
    assert not player.is_fading
    assert player.current_animation == "walk"
    player.shutdown()


def test_fade_skipped_without_current_frame(qapp, assets):
    player = AnimationPlayer(assets)
    assert player.play("walk", fade_ms=150)  # nothing displayed yet: hard cut
    assert not player.is_fading
    player.shutdown()


def test_fade_skipped_for_identical_frame(qapp, assets):
    player = AnimationPlayer(assets)
    player.play("idle")
    assert player.play("idle", fade_ms=150)  # same first frame: no fade needed
    assert not player.is_fading
    player.shutdown()


def test_stop_and_static_cancel_fade(qapp, assets):
    player = AnimationPlayer(assets)
    player.play("idle")
    player.play("walk", fade_ms=150)
    assert player.is_fading
    player.stop()
    assert not player.is_fading
    player.play("idle")
    player.play("walk", fade_ms=150)
    assert player.show_static("idle")
    assert not player.is_fading
    assert not player.is_playing
    player.shutdown()


def test_unknown_animation_with_fade_fails_gracefully(qapp, assets):
    player = AnimationPlayer(assets)
    player.play("idle")
    assert player.play("nope", fade_ms=150) is False
    assert not player.is_fading
    assert player.current_animation == "idle"
    player.shutdown()


def test_fade_finishes_into_loop_playback(qapp, assets):
    player = AnimationPlayer(assets)
    player.play("idle")
    player.play("walk", fade_ms=120)
    player.fade_step(1.0)
    frames = assets.frames_for("walk")
    assert player.tick() is not None
    assert _pixels(player._current) == _pixels(frames[1])
    player.shutdown()
