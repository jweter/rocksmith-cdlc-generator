from __future__ import annotations

from pathlib import Path
from typing import Literal

from PIL import Image, ImageFilter
from pydantic import BaseModel, ConfigDict, Field

from .hashing import sha256_file
from .printed_score_project import validate_printed_score_project_page
from .score_page_segmentation import (
    PixelRegion,
    ScorePageSegmentationError,
    _horizontal_ink_strength,
    _illumination_corrected_ink,
    _smooth,
    detect_score_systems,
)


MEASURE_SEGMENTATION_ALGORITHM_ID = "paired-notation-tab-barline-segmentation"
MEASURE_SEGMENTATION_ALGORITHM_VERSION = "1"


class DetectedBarline(BaseModel):
    """Untrusted vertical boundary candidate corroborated across notation and TAB."""

    model_config = ConfigDict(frozen=True)

    x: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    notation_vertical_run: int = Field(ge=0)
    tab_vertical_run: int = Field(ge=0)
    inferred_from_staff_extent: bool = False


class DetectedScoreMeasure(BaseModel):
    model_config = ConfigDict(frozen=True)

    measure_index: int = Field(ge=0)
    system_index: int = Field(ge=0)
    region: PixelRegion
    left_boundary: DetectedBarline
    right_boundary: DetectedBarline
    confidence: float = Field(ge=0.0, le=1.0)
    review_required: bool = False


class ScoreMeasureSegmentation(BaseModel):
    """Reading-ordered, untrusted measure geometry for a normalized printed page."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    algorithm_id: Literal["paired-notation-tab-barline-segmentation"] = (
        MEASURE_SEGMENTATION_ALGORITHM_ID
    )
    algorithm_version: str = MEASURE_SEGMENTATION_ALGORITHM_VERSION
    bundle_id: str
    printed_page: int = Field(ge=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    derivative_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    derivative_relative_path: str
    page_size: tuple[int, int]
    measures: list[DetectedScoreMeasure]
    warnings: list[str] = Field(default_factory=list)

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path


def _longest_vertical_run(image: Image.Image, x: int, *, threshold: int = 64) -> int:
    pixels = image.load()
    longest = 0
    current = 0
    for y in range(image.height):
        if pixels[x, y] >= threshold:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _cluster_x_candidates(
    candidates: list[tuple[int, int, int]],
    *,
    maximum_gap: int = 15,
) -> list[tuple[int, int, int]]:
    """Merge nearby x candidates created by thick/slanted printed barlines."""

    if not candidates:
        return []
    candidates = sorted(candidates)
    clusters: list[list[tuple[int, int, int]]] = [[candidates[0]]]
    for candidate in candidates[1:]:
        if candidate[0] - clusters[-1][-1][0] <= maximum_gap:
            clusters[-1].append(candidate)
        else:
            clusters.append([candidate])
    return [
        max(cluster, key=lambda item: min(item[1], item[2]))
        for cluster in clusters
    ]


def _paired_barline_candidates(system_ink: Image.Image) -> list[DetectedBarline]:
    """Find x positions with sustained vertical ink in both notation and TAB bands.

    A note stem can be strongly vertical in standard notation, but normally has no
    corresponding long vertical stroke in the TAB band. Requiring both bands sharply
    reduces the chance of promoting note stems as measure boundaries.
    """

    height = system_ink.height
    notation = system_ink.crop((0, round(height * 0.02), system_ink.width, round(height * 0.58)))
    tab = system_ink.crop((0, round(height * 0.58), system_ink.width, round(height * 0.98)))

    notation = notation.filter(ImageFilter.MaxFilter(5))
    tab = tab.filter(ImageFilter.MaxFilter(5))

    min_notation_run = max(12, round(notation.height * 0.18))
    min_tab_run = max(12, round(tab.height * 0.25))
    x_start = round(system_ink.width * 0.05)
    x_end = round(system_ink.width * 0.95)

    candidates: list[tuple[int, int, int]] = []
    for x in range(x_start, x_end):
        notation_run = _longest_vertical_run(notation, x)
        tab_run = _longest_vertical_run(tab, x)
        if notation_run >= min_notation_run and tab_run >= min_tab_run:
            candidates.append((x, notation_run, tab_run))

    clustered = _cluster_x_candidates(candidates)
    result: list[DetectedBarline] = []
    for x, notation_run, tab_run in clustered:
        notation_strength = min(1.0, notation_run / max(1, notation.height * 0.45))
        tab_strength = min(1.0, tab_run / max(1, tab.height * 0.55))
        confidence = min(notation_strength, tab_strength)
        result.append(
            DetectedBarline(
                x=x,
                confidence=confidence,
                notation_vertical_run=notation_run,
                tab_vertical_run=tab_run,
            )
        )
    return result


def _tab_staff_right_extent(system_ink: Image.Image) -> int:
    """Infer the right edge of a wrapped system when no final barline is printed.

    The TAB staff contributes low but sustained horizontal ink across the playable
    width. A wide x-smoothed projection is robust to fret digits and local note detail.
    """

    height = system_ink.height
    tab = system_ink.crop((0, round(height * 0.58), system_ink.width, round(height * 0.98)))
    pixels = list(tab.getdata())
    width = tab.width
    column_strength = [
        sum(pixels[y * width + x] for y in range(tab.height)) / (255.0 * tab.height)
        for x in range(width)
    ]
    smoothed = _smooth(column_strength, radius=max(8, round(width * 0.018)))

    threshold = 0.03
    minimum_span = max(80, round(width * 0.08))
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for x, strength in enumerate(smoothed):
        if strength >= threshold and start is None:
            start = x
        if start is not None and (strength < threshold or x == width - 1):
            end = x if strength < threshold else x + 1
            if end - start >= minimum_span:
                runs.append((start, end))
            start = None

    if not runs:
        return round(width * 0.90)
    return max(end for _start, end in runs)


def _system_measure_boundaries(system_ink: Image.Image) -> tuple[list[DetectedBarline], list[str]]:
    candidates = _paired_barline_candidates(system_ink)
    warnings: list[str] = []
    width = system_ink.width

    if not candidates:
        return [], ["no_paired_barline_candidates"]

    left_candidates = [item for item in candidates if item.x <= width * 0.30]
    if not left_candidates:
        warnings.append("no_confident_left_barline")
        left = candidates[0]
    else:
        left = max(left_candidates, key=lambda item: item.confidence)

    inferred_right_x = _tab_staff_right_extent(system_ink)
    right_candidates = [item for item in candidates if item.x >= width * 0.78]
    if right_candidates:
        right = max(right_candidates, key=lambda item: item.confidence)
    else:
        right = DetectedBarline(
            x=inferred_right_x,
            confidence=0.65,
            notation_vertical_run=0,
            tab_vertical_run=0,
            inferred_from_staff_extent=True,
        )
        warnings.append("right_boundary_inferred_from_tab_staff_extent")

    if right.x <= left.x:
        return [], warnings + ["invalid_system_horizontal_extent"]

    internal = [
        item
        for item in candidates
        if item.x > left.x + width * 0.12 and item.x < right.x - width * 0.12
    ]
    internal.sort(key=lambda item: item.x)

    boundaries = [left, *internal, right]
    deduplicated: list[DetectedBarline] = []
    for boundary in boundaries:
        if deduplicated and boundary.x - deduplicated[-1].x < max(12, round(width * 0.015)):
            if boundary.confidence > deduplicated[-1].confidence:
                deduplicated[-1] = boundary
        else:
            deduplicated.append(boundary)
    return deduplicated, warnings


def segment_score_measures(
    project_dir: Path,
    printed_page: int,
    *,
    limit: int = 8,
    expected_system_count: int | None = None,
    max_long_edge: int = 2200,
) -> ScoreMeasureSegmentation:
    """Segment up to ``limit`` measures using paired notation/TAB barline evidence."""

    if limit < 1:
        raise ValueError("limit must be >= 1")

    # This function is the shared gateway used by both desktop and CLI recognition.
    # Enforce movement authority here so alternate entry points cannot generate
    # recognition candidates for pages outside the selected project movement.
    validate_printed_score_project_page(project_dir, printed_page)

    systems = detect_score_systems(
        project_dir,
        printed_page,
        expected_system_count=expected_system_count,
        max_long_edge=max_long_edge,
    )
    project_root = Path(project_dir).expanduser().resolve()
    derivative = (project_root / systems.derivative_relative_path).resolve()
    if not derivative.is_relative_to(project_root) or not derivative.is_file():
        raise ScorePageSegmentationError("normalized derivative is missing or escaped project")
    if sha256_file(derivative) != systems.derivative_sha256:
        raise ScorePageSegmentationError("normalized derivative changed before measure segmentation")

    with Image.open(derivative) as opened:
        gray = opened.convert("L")
        ink_page = _illumination_corrected_ink(gray)

    measures: list[DetectedScoreMeasure] = []
    warnings = list(systems.warnings)
    for system in systems.systems:
        if len(measures) >= limit:
            break
        region = system.region
        system_ink = ink_page.crop((region.x0, region.y0, region.x1, region.y1))
        boundaries, system_warnings = _system_measure_boundaries(system_ink)
        warnings.extend(f"system_{system.system_index}:{warning}" for warning in system_warnings)
        if len(boundaries) < 2:
            continue

        for left, right in zip(boundaries, boundaries[1:]):
            if len(measures) >= limit:
                break
            if right.x <= left.x:
                continue
            confidence = min(system.confidence, left.confidence, right.confidence)
            review_required = (
                confidence < 0.75
                or left.inferred_from_staff_extent
                or right.inferred_from_staff_extent
            )
            measures.append(
                DetectedScoreMeasure(
                    measure_index=len(measures),
                    system_index=system.system_index,
                    region=PixelRegion(
                        x0=region.x0 + left.x,
                        y0=region.y0,
                        x1=region.x0 + right.x,
                        y1=region.y1,
                    ),
                    left_boundary=left,
                    right_boundary=right,
                    confidence=confidence,
                    review_required=review_required,
                )
            )

    if not measures:
        warnings.append("no_measures_segmented")
    if len(measures) < limit:
        warnings.append(f"measure_limit_not_reached:requested={limit},segmented={len(measures)}")

    result = ScoreMeasureSegmentation(
        bundle_id=systems.bundle_id,
        printed_page=printed_page,
        source_sha256=systems.source_sha256,
        derivative_sha256=systems.derivative_sha256,
        derivative_relative_path=systems.derivative_relative_path,
        page_size=systems.page_size,
        measures=measures,
        warnings=warnings,
    )
    metadata = derivative.with_name(derivative.stem + "-measures.json")
    result.write_json(metadata)
    return result
