"""Visual Fix 01 tests: idle identity consistency and real breathing.

- Every idle frame shows the same panda: head/face region is
  pixel-identical across frames (no squash distortion, no shifting).
- Feet stay anchored: the opaque bounding box is identical every frame.
- Breathing is real and localized: mid-cycle frames differ from frame 0,
  but only outside the head region (chest/belly expansion).
- Blink's open frame matches idle frame 0 exactly (no pop on blink).
"""

from PIL import Image, ImageChops

from doodle_mvp.character.assets import AssetLoader


def _idle_frames(assets):
    paths = assets.spec_for("idle").frames
    assert len(paths) == 8
    return [Image.open(str(f)).convert("RGBA") for f in paths]


def _bbox(im):
    px = im.load()
    w, h = im.size
    xs = [x for y in range(h) for x in range(w) if px[x, y][3] > 8]
    ys = [y for y in range(h) for x in range(w) if px[x, y][3] > 8]
    return (min(xs), max(xs), min(ys), max(ys))


def _region_diff(a, b, box):
    d = ImageChops.difference(a.crop(box).convert("L"),
                              b.crop(box).convert("L"))
    return sum(d.getdata())


def test_idle_head_identical_across_frames(qapp, assets):
    frames = _idle_frames(assets)
    w, h = frames[0].size
    head_box = (0, 0, w, int(h * 0.45))
    for i, frame in enumerate(frames[1:], start=1):
        assert _region_diff(frames[0], frame, head_box) == 0, \
            f"frame {i} head differs from frame 0"


def test_idle_feet_anchored(qapp, assets):
    frames = _idle_frames(assets)
    boxes = [_bbox(f) for f in frames]
    assert len(set(boxes)) == 1, f"bounding boxes vary: {set(boxes)}"


def test_idle_breathing_is_localized_chest_expansion(qapp, assets):
    frames = _idle_frames(assets)
    w, h = frames[0].size
    head_box = (0, 0, w, int(h * 0.45))
    # max-inhale frame differs from rest frame ...
    assert _region_diff(frames[0], frames[3], (0, 0, w, h)) > 0
    # ... but the head region does not
    assert _region_diff(frames[0], frames[3], head_box) == 0


def test_blink_open_matches_idle_rest(qapp, assets):
    idle0 = Image.open(str(assets.spec_for("idle").frames[0])).convert("RGB")
    blink0 = Image.open(str(assets.spec_for("blink").frames[0])).convert("RGB")
    d = ImageChops.difference(idle0, blink0)
    assert sum(d.convert("L").getdata()) == 0


def test_idle_loop_returns_to_rest(qapp, assets):
    frames = _idle_frames(assets)
    d = ImageChops.difference(frames[0].convert("RGB"),
                              frames[-1].convert("RGB"))
    assert sum(d.convert("L").getdata()) == 0
