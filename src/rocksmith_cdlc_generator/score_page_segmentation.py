from __future__ import annotations

from pathlib import Path
from statistics import median
from typing import Literal

from PIL import Image, ImageChops, ImageFilter, ImageOps
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .hashing import sha256_file
from .score_page_preprocessing import (
    NormalizedScorePage,
    normalize_registered_score_page,
)


SEGMENTATION_ALGORITHM_ID = "horizontal-ink-system-segmentation"
SEGMENTATION_ALGORITHM_VERSION = "1"


class ScorePageSegmentationError(ValueError):
    pass


class PixelRegion(BaseModel):
    model_config = ConfigDict(frozen=True)

    x0: int = Field(ge=0)
    y0: int = Field(ge=0)
    x1: int = Field(gt=0)
    y1: int = Field(gt=0)

    @model_validator(mode="after")
    def ordered_coordinates(self) -> "PixelRegion":
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            raise ValueError("pixel region must have positive width and height")
        return self

    @property
    def width(self) -> int:
        return self.x1 - self.x0

    @property
    def height(self) -> int:
        return self.y1 - self.y0


class DetectedScoreSystem(BaseModel):
    model_config = ConfigDict(frozen=True)

    system_index: int = Field(ge=0)
    region: PixelRegion
    confidence: float = Field(ge=0.0, le=1.0)
    peak_ink_strength: float = Field(ge=0.0, le=1.0)


class ScoreSystemSegmentation(BaseModel):
    """Untrusted geometry candidates for notation/TAB system regions on one page."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    algorithm_id: Literal["horizontal-ink-system-segmentation"] = SEGMENTATION_ALGORITHM_ID
    algorithm_version: str = SEGMENTATION_ALGORITHM_VERSION
    bundle_id: str
    printed_page: int = Field(ge=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    derivative_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    derivative_relative_path: str
    page_size: tuple[int, int]
    systems: list[DetectedScoreSystem]
    warnings: list[str] = Field(default_factory=list)

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path


def _smooth(values: list[float], radius: int = 4) -> list[float]:
    if not values:
        return []
    result: list[float] = []
    for index in range(len(values)):
        start = max(0, index - radius)
        end = min(len(values), index + radius + 1)
        result.append(sum(values[start:end]) / (end - start))
    return result


def _active_runs(values: list[float], threshold: float, *, minimum_height: int) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for index, value in enumerate(values):
        if value >= threshold and start is None:
            start = index
        if start is not None and (value < threshold or index == len(values) - 1):
            end = index if value < threshold else index + 1
            if end - start >= minimum_height:
                runs.append((start, end))
            start = None
    return runs


def _merge_runs(runs: list[tuple[int, int]], *, maximum_gap: int) -> list[tuple[int, int]]:
    merged: list[list[int]] = []
    for start, end in runs:
        if merged and start - merged[-1][1] <= maximum_gap:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def _illumination_corrected_ink(gray: Image.Image) -> Image.Image:
    """Suppress broad lighting gradients while retaining printed strokes.

    Phone photographs of books commonly have strong top-to-bottom illumination changes.
    A broad Gaussian background estimate lets the system detector respond to local dark
    notation/TAB strokes rather than treating the darker half of a page as one region.
    """

    radius = max(8, min(gray.size) // 60)
    background = gray.filter(ImageFilter.GaussianBlur(radius=radius))
    local_darkness = ImageChops.subtract(background, gray)
    return ImageOps.autocontrast(local_darkness, cutoff=1)


def _horizontal_ink_strength(ink: Image.Image) -> list[float]:
    width, height = ink.size
    margin = max(1, round(width * 0.06))
    central = ink.crop((margin, 0, width - margin, height))
    analysis_width = min(320, central.width)
    if central.width != analysis_width:
        central = central.resize((analysis_width, height), Image.Resampling.BILINEAR)

    pixels = list(central.getdata())
    row_width = central.width
    strengths = [
        sum(pixels[row * row_width : (row + 1) * row_width]) / (255.0 * row_width)
        for row in range(height)
    ]
    return _smooth(strengths, radius=4)


def _candidate_system_runs(
    strengths: list[float],
    *,
    page_height: int,
) -> list[tuple[int, int]]:
    # The ink image has broad illumination removed and is contrast-normalized. A low
    # fixed floor is intentionally used so the lighter TAB half of a photographed
    # system stays connected to the standard-notation half. Geometry/height filtering
    # below rejects small text and footer bands.
    active = _active_runs(strengths, 0.015, minimum_height=max(4, page_height // 400))
    merged = _merge_runs(active, maximum_gap=max(18, round(page_height * 0.02)))

    minimum_system_height = max(70, round(page_height * 0.075))
    maximum_system_height = max(minimum_system_height + 1, round(page_height * 0.18))
    edge_guard = round(page_height * 0.02)
    return [
        (start, end)
        for start, end in merged
        if minimum_system_height <= end - start <= maximum_system_height
        and not (start <= edge_guard and end >= page_height * 0.10)
    ]


def detect_score_systems(
    project_dir: Path,
    printed_page: int,
    *,
    expected_system_count: int | None = None,
    max_long_edge: int = 2200,
) -> ScoreSystemSegmentation:
    """Detect notation+TAB system bands on one registered score page.

    Output is deliberately *untrusted geometry*. It becomes useful evidence for N2
    measure segmentation but must not be promoted directly into musical events.
    """

    normalized: NormalizedScorePage = normalize_registered_score_page(
        project_dir,
        printed_page,
        max_long_edge=max_long_edge,
    )
    project_root = Path(project_dir).expanduser().resolve()
    derivative = (project_root / normalized.derivative_relative_path).resolve()
    if not derivative.is_relative_to(project_root) or not derivative.is_file():
        raise ScorePageSegmentationError("normalized derivative is missing or escaped project")
    if sha256_file(derivative) != normalized.derivative_sha256:
        raise ScorePageSegmentationError("normalized derivative changed before segmentation")

    with Image.open(derivative) as opened:
        gray = opened.convert("L")
        width, height = gray.size
        ink = _illumination_corrected_ink(gray)
        strengths = _horizontal_ink_strength(ink)

    runs = _candidate_system_runs(strengths, page_height=height)
    typical_height = median([end - start for start, end in runs]) if runs else 0.0
    systems: list[DetectedScoreSystem] = []
    for index, (start, end) in enumerate(runs):
        band_height = end - start
        height_fit = 1.0 if not typical_height else max(
            0.0,
            1.0 - abs(band_height - typical_height) / max(typical_height, 1.0),
        )
        peak = min(1.0, max(strengths[start:end], default=0.0))
        # Geometry regularity carries most confidence; ink peak prevents very faint
        # page texture from scoring as a strong system candidate.
        confidence = max(0.0, min(1.0, 0.75 * height_fit + 0.25 * min(1.0, peak / 0.12)))
        systems.append(
            DetectedScoreSystem(
                system_index=index,
                region=PixelRegion(x0=0, y0=start, x1=width, y1=end),
                confidence=confidence,
                peak_ink_strength=peak,
            )
        )

    warnings: list[str] = []
    if not systems:
        warnings.append("no_score_systems_detected")
    if expected_system_count is not None and len(systems) != expected_system_count:
        warnings.append(
            f"system_count_mismatch:expected={expected_system_count},detected={len(systems)}"
        )
    if any(system.confidence < 0.60 for system in systems):
        warnings.append("low_confidence_system_geometry")

    result = ScoreSystemSegmentation(
        bundle_id=normalized.bundle_id,
        printed_page=printed_page,
        source_sha256=normalized.source_sha256,
        derivative_sha256=normalized.derivative_sha256,
        derivative_relative_path=normalized.derivative_relative_path,
        page_size=(width, height),
        systems=systems,
        warnings=warnings,
    )
    metadata = derivative.with_name(derivative.stem + "-systems.json")
    result.write_json(metadata)
    return result
