from __future__ import annotations

from PIL import Image


def normalize_quarter_turns(value: int) -> int:
    """Normalize an arbitrary quarter-turn count into the canonical 0..3 range."""

    return int(value) % 4


def rotate_image_quarter_turns(image: Image.Image, quarter_turns: int) -> Image.Image:
    """Return ``image`` rotated counter-clockwise in 90-degree increments.

    The source image is left untouched. A zero-turn request returns a copy so callers
    can safely treat the result as a render-owned image.
    """

    turns = normalize_quarter_turns(quarter_turns)
    if turns == 1:
        return image.transpose(Image.Transpose.ROTATE_90)
    if turns == 2:
        return image.transpose(Image.Transpose.ROTATE_180)
    if turns == 3:
        return image.transpose(Image.Transpose.ROTATE_270)
    return image.copy()
