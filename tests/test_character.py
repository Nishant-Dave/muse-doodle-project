"""PandaCharacter facing tests: mirrored rendering without new assets."""

from doodle_mvp.character.character import PandaCharacter


def _pixels(pixmap):
    return bytes(pixmap.toImage().constBits())


def test_facing_left_mirrors_frame(qapp, assets):
    char = PandaCharacter()
    frames = assets.frames_for("idle")
    char.show_frame(frames[0])
    right_pixels = _pixels(char.pixmap())
    char.set_facing("left")
    left_pixels = _pixels(char.pixmap())
    assert char.facing == "left"
    assert left_pixels != right_pixels  # genuinely mirrored
    assert char.pixmap().size() == frames[0].size()  # same dimensions
    char.set_facing("right")
    assert _pixels(char.pixmap()) == right_pixels  # restored exactly


def test_facing_is_idempotent_and_validated(qapp, assets):
    char = PandaCharacter()
    frames = assets.frames_for("idle")
    char.show_frame(frames[0])
    char.set_facing("left")
    first = _pixels(char.pixmap())
    char.set_facing("left")  # no-op
    assert _pixels(char.pixmap()) == first
    char.set_facing("upside-down")  # invalid: ignored
    assert char.facing == "left"
