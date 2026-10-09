"""Asset loading tests: manifest, frames, graceful failure."""

from pathlib import Path

from doodle_mvp.character.assets import AssetLoader

EXPECTED_ANIMATIONS = {
    "idle", "blink", "yawn", "drag", "poke",
    "happy", "dizzy", "mood_sad", "mood_stressed",
}


def _pixels_differ(pm1, pm2) -> bool:
    img1 = pm1.toImage()
    img2 = pm2.toImage()
    if img1.size() != img2.size():
        return True
    ptr1 = img1.constBits()
    ptr2 = img2.constBits()
    # constBits exposes the raw buffer; compare as bytes.
    return bytes(ptr1) != bytes(ptr2)


def test_manifest_lists_all_expected_animations(assets):
    assert EXPECTED_ANIMATIONS <= set(assets.animation_names)


def test_every_animation_has_loadable_frames(assets):
    for name in EXPECTED_ANIMATIONS:
        assert assets.has_animation(name), name
        frames = assets.frames_for(name)
        assert len(frames) >= 2, f"{name} should have at least 2 frames"
        assert all(not pm.isNull() for pm in frames), name


def test_frames_have_genuine_visual_differences(assets):
    """Each animation must contain at least two visually different frames."""
    for name in EXPECTED_ANIMATIONS:
        frames = assets.frames_for(name)
        assert any(
            _pixels_differ(frames[0], other) for other in frames[1:]
        ), f"{name} frames are all identical"


def test_unknown_animation_handled_gracefully(assets):
    assert not assets.has_animation("does_not_exist")
    assert assets.spec_for("does_not_exist") is None
    assert assets.frames_for("does_not_exist") == []


def test_missing_manifest_handled_gracefully(tmp_path, qapp):
    loader = AssetLoader(assets_dir=tmp_path / "nope")
    assert loader.animation_names == []
    assert loader.frames_for("idle") == []


def test_invalid_manifest_handled_gracefully(tmp_path, qapp):
    d = tmp_path / "bad"
    d.mkdir()
    (d / "manifest.json").write_text("{not valid json", encoding="utf-8")
    loader = AssetLoader(assets_dir=d)
    assert loader.animation_names == []


def test_manifest_file_exists_on_disk():
    manifest = Path(__file__).resolve().parents[1] / "assets" / "panda" / "manifest.json"
    assert manifest.is_file()
