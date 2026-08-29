from __future__ import annotations

from PIL import Image, ImageOps


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


def apply_exif_orientation(image: Image.Image) -> Image.Image:
    """Return ``image`` with any EXIF orientation tag baked into pixel data.

    Phone/camera JPEGs commonly store the intended viewing rotation in EXIF metadata
    rather than the raw pixel grid. ``Image.open`` does not apply that tag on its own,
    so a portrait photo can decode as sideways pixel data. ``ImageOps.exif_transpose``
    returns a new image with the orientation normalized to "upright" (or an unrotated
    copy when no orientation tag is present); it never mutates the input, and it does
    not touch the file on disk, so the registered/hashed source image is unaffected.
    """

    transposed = ImageOps.exif_transpose(image)
    return transposed if transposed is not None else image.copy()
