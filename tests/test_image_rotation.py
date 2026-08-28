from PIL import Image

from rocksmith_cdlc_generator.image_rotation import (
    normalize_quarter_turns,
    rotate_image_quarter_turns,
)


def test_normalize_quarter_turns_wraps_both_directions() -> None:
    assert normalize_quarter_turns(0) == 0
    assert normalize_quarter_turns(4) == 0
    assert normalize_quarter_turns(5) == 1
    assert normalize_quarter_turns(-1) == 3
    assert normalize_quarter_turns(-5) == 3


def test_rotate_image_quarter_turns_preserves_orientation_semantics() -> None:
    image = Image.new("RGB", (2, 3), "black")
    image.putpixel((0, 0), (255, 0, 0))

    left = rotate_image_quarter_turns(image, 1)
    right = rotate_image_quarter_turns(image, -1)

    assert left.size == (3, 2)
    assert right.size == (3, 2)
    assert left.getpixel((0, 1)) == (255, 0, 0)
    assert right.getpixel((2, 0)) == (255, 0, 0)
    assert image.size == (2, 3)
    assert image.getpixel((0, 0)) == (255, 0, 0)


def test_zero_turn_returns_independent_copy() -> None:
    image = Image.new("RGB", (2, 2), "white")
    result = rotate_image_quarter_turns(image, 0)

    result.putpixel((0, 0), (0, 0, 0))

    assert image.getpixel((0, 0)) == (255, 255, 255)
