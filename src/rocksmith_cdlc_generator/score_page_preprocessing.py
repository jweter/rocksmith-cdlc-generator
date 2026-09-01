from __future__ import annotations

from pathlib import Path
from typing import Literal

from PIL import Image, ImageFilter, ImageOps, ImageStat
from pydantic import BaseModel, ConfigDict, Field

from .hashing import sha256_file
from .private_score_bundle import (
    PrivateScoreBundleError,
    RegisteredPrivateScoreBundle,
    RegisteredPrivateScorePage,
    movement_score_pages,
    verify_private_score_bundle,
)


PREPROCESSED_SCORE_RELATIVE_PATH = Path("derived") / "printed-score" / "preprocessed"
EXIF_ORIENTATION_TAG = 274


class ScorePagePreprocessingError(ValueError):
    pass


class ScorePageQuality(BaseModel):
    """Deterministic, non-authoritative image diagnostics for one source page.

    These diagnostics are intentionally conservative. They are evidence for whether a
    page should proceed into OMR, not a guarantee that recognition will be correct.
    """

    model_config = ConfigDict(frozen=True)

    width: int = Field(ge=1)
    height: int = Field(ge=1)
    short_edge: int = Field(ge=1)
    long_edge: int = Field(ge=1)
    mean_luma: float = Field(ge=0.0, le=255.0)
    contrast_stddev: float = Field(ge=0.0)
    edge_energy: float = Field(ge=0.0)
    warnings: list[str] = Field(default_factory=list)


class NormalizedScorePage(BaseModel):
    """Hash-bound metadata for a derivative page used by recognition stages."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    bundle_id: str
    source_filename: str
    printed_page: int
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    derivative_relative_path: str
    derivative_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_size: tuple[int, int]
    output_size: tuple[int, int]
    output_mode: Literal["L"] = "L"
    exif_orientation_normalized: bool
    max_long_edge: int = Field(ge=256)
    quality: ScorePageQuality

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path


def _project_file(project_dir: Path, relative_path: str) -> Path:
    root = Path(project_dir).expanduser().resolve()
    candidate = (root / relative_path).resolve()
    if not candidate.is_relative_to(root):
        raise ScorePagePreprocessingError("printed score path escaped the project directory")
    return candidate


def _quality_diagnostics(gray: Image.Image) -> ScorePageQuality:
    width, height = gray.size
    stat = ImageStat.Stat(gray)
    mean_luma = float(stat.mean[0])
    contrast_stddev = float(stat.stddev[0])

    # FIND_EDGES provides a lightweight deterministic focus/detail proxy without
    # introducing a heavy OpenCV dependency into the Windows package. It is not a
    # perceptual sharpness score; low values only trigger a conservative warning.
    edge_image = gray.filter(ImageFilter.FIND_EDGES)
    edge_energy = float(ImageStat.Stat(edge_image).mean[0])

    warnings: list[str] = []
    short_edge = min(width, height)
    long_edge = max(width, height)
    if short_edge < 1000:
        warnings.append("low_resolution")
    if contrast_stddev < 20.0:
        warnings.append("low_contrast")
    if mean_luma < 70.0:
        warnings.append("underexposed")
    if mean_luma > 245.0:
        warnings.append("overexposed")
    if edge_energy < 3.0:
        warnings.append("low_edge_detail_possible_blur")

    return ScorePageQuality(
        width=width,
        height=height,
        short_edge=short_edge,
        long_edge=long_edge,
        mean_luma=mean_luma,
        contrast_stddev=contrast_stddev,
        edge_energy=edge_energy,
        warnings=warnings,
    )


def _score_page(bundle: RegisteredPrivateScoreBundle, printed_page: int) -> RegisteredPrivateScorePage:
    page = next(
        (
            item
            for item in bundle.pages
            if item.kind == "score" and item.printed_page == printed_page
        ),
        None,
    )
    if page is None:
        raise KeyError(printed_page)
    return page


def _normalized_destination(project_dir: Path, page: RegisteredPrivateScorePage) -> Path:
    if page.printed_page is None:
        raise ScorePagePreprocessingError("only score pages with printed_page can be normalized")
    filename = f"page-{page.printed_page:03d}-{page.sha256[:12]}-normalized.png"
    return Path(project_dir).expanduser().resolve() / PREPROCESSED_SCORE_RELATIVE_PATH / filename


def normalize_registered_score_page(
    project_dir: Path,
    printed_page: int,
    *,
    max_long_edge: int = 2200,
) -> NormalizedScorePage:
    """Create a deterministic grayscale derivative for later staff/TAB recognition.

    The registered source image is never modified. Source identity is re-verified
    before preprocessing, EXIF orientation is normalized, the working page is resized
    only when necessary, and contrast normalization is applied to the derivative.
    Every result remains tied to the exact source SHA-256 recorded by registration.
    """

    if max_long_edge < 256:
        raise ValueError("max_long_edge must be >= 256")

    project_root = Path(project_dir).expanduser().resolve()
    bundle = verify_private_score_bundle(project_root)
    page = _score_page(bundle, printed_page)
    source = _project_file(project_root, page.relative_path)

    try:
        with Image.open(source) as opened:
            opened.seek(0)
            original_size = opened.size
            orientation = opened.getexif().get(EXIF_ORIENTATION_TAG, 1)
            exif_orientation_normalized = orientation not in (None, 1)
            oriented = ImageOps.exif_transpose(opened)
            gray = oriented.convert("L")
            quality = _quality_diagnostics(gray)

            width, height = gray.size
            long_edge = max(width, height)
            if long_edge > max_long_edge:
                scale = max_long_edge / float(long_edge)
                output_size = (
                    max(1, round(width * scale)),
                    max(1, round(height * scale)),
                )
                gray = gray.resize(output_size, Image.Resampling.LANCZOS)
            else:
                output_size = gray.size

            normalized = ImageOps.autocontrast(gray, cutoff=1)
    except (OSError, SyntaxError) as exc:
        raise PrivateScoreBundleError(
            f"registered printed-score image cannot be decoded: {page.source_filename}"
        ) from exc

    destination = _normalized_destination(project_root, page)
    destination.parent.mkdir(parents=True, exist_ok=True)
    normalized.save(destination, format="PNG", optimize=True)
    derivative_sha256 = sha256_file(destination)

    result = NormalizedScorePage(
        bundle_id=bundle.bundle_id,
        source_filename=page.source_filename,
        printed_page=printed_page,
        source_sha256=page.sha256,
        derivative_relative_path=destination.relative_to(project_root).as_posix(),
        derivative_sha256=derivative_sha256,
        source_size=original_size,
        output_size=output_size,
        exif_orientation_normalized=exif_orientation_normalized,
        max_long_edge=max_long_edge,
        quality=quality,
    )
    result.write_json(destination.with_suffix(".json"))
    return result


def normalize_movement_score_pages(
    project_dir: Path,
    movement_id: str,
    *,
    max_long_edge: int = 2200,
) -> list[NormalizedScorePage]:
    """Normalize the ordered registered pages that contain one movement."""

    project_root = Path(project_dir).expanduser().resolve()
    bundle = verify_private_score_bundle(project_root)
    pages = movement_score_pages(bundle, movement_id)
    return [
        normalize_registered_score_page(
            project_root,
            page.printed_page,
            max_long_edge=max_long_edge,
        )
        for page in pages
        if page.printed_page is not None
    ]
