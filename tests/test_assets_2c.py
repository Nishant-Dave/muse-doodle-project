"""Phase 2C asset tests: new animations, manifest integrity, validation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from validate_assets import validate


def test_new_animations_in_manifest(assets):
    for name in ("walk", "gaze_left", "gaze_right", "land"):
        assert assets.has_animation(name), f"{name} missing from manifest"
        spec = assets.spec_for(name)
        assert spec is not None
        assert spec.fps > 0
        assert isinstance(spec.loop, bool)
        assert spec.description
        assert len(assets.frames_for(name)) >= 3


def test_walk_is_loop_and_land_is_one_shot(assets):
    assert assets.spec_for("walk").loop is True
    assert assets.spec_for("land").loop is False
    assert assets.spec_for("gaze_left").loop is False
    assert assets.spec_for("gaze_right").loop is False


def test_all_frames_share_dimensions(assets):
    sizes = set()
    for name in assets.animation_names:
        for frame in assets.frames_for(name):
            sizes.add((frame.width(), frame.height()))
    assert sizes == {(240, 240)}


def test_asset_validation_passes_on_real_assets():
    assert validate() == []


def test_gaze_frames_differ_from_neutral(assets):
    def _pixels(p):
        return bytes(p.toImage().constBits())

    idle = _pixels(assets.frames_for("idle")[0])
    gl = _pixels(assets.frames_for("gaze_left")[1])
    gr = _pixels(assets.frames_for("gaze_right")[1])
    assert gl != idle and gr != idle and gl != gr


def test_walk_frames_show_alternation(assets):
    def _pixels(p):
        return bytes(p.toImage().constBits())

    frames = assets.frames_for("walk")
    pix = [_pixels(f) for f in frames]
    assert len(set(pix)) == len(pix)  # every frame visually distinct
