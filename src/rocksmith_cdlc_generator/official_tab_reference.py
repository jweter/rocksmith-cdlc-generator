from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
import shutil
from typing import Iterable, Literal

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .hashing import sha256_file
from .score_source import ArrangementRole


MANIFEST_RELATIVE_PATH = Path("references") / "official-tab" / "manifest.json"
PAGE_DIRECTORY_RELATIVE_PATH = Path("references") / "official-tab" / "pages"
SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
SUPPORTED_PIL_FORMATS_BY_SUFFIX = {
    ".jpg": {"JPEG", "MPO"},
    ".jpeg": {"JPEG", "MPO"},
    ".png": {"PNG"},
}


class OfficialTabReferenceMapping(BaseModel):
    """One deterministic score-measure range mapped onto a region of a local page image."""

    model_config = ConfigDict(frozen=True)

    mapping_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9._-]+$")
    arrangement: ArrangementRole
    measure_start: int = Field(ge=1)
    measure_end: int = Field(ge=1)
    # Normalized image coordinates. The first viewer maps the whole page by default;
    # future graphical region mapping can narrow this without changing the manifest.
    normalized_bbox: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)

    @model_validator(mode="after")
    def validate_range_and_bbox(self) -> "OfficialTabReferenceMapping":
        if self.measure_end < self.measure_start:
            raise ValueError("official TAB measure_end must be >= measure_start")
        x0, y0, x1, y1 = self.normalized_bbox
        if not all(0.0 <= value <= 1.0 for value in self.normalized_bbox):
            raise ValueError("official TAB normalized_bbox coordinates must be between 0 and 1")
        if x1 <= x0 or y1 <= y0:
            raise ValueError("official TAB normalized_bbox must have positive width and height")
        return self


class OfficialTabReferencePage(BaseModel):
    """Immutable local page-image evidence plus one or more score mappings."""

    model_config = ConfigDict(frozen=True)

    page_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9._-]+$")
    relative_path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    printed_page: str | None = None
    source_label: str = "Official printed TAB reference"
    mappings: list[OfficialTabReferenceMapping] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_relative_path_and_mapping_ids(self) -> "OfficialTabReferencePage":
        pure = PurePosixPath(self.relative_path.replace("\\", "/"))
        if pure.is_absolute() or ".." in pure.parts:
            raise ValueError("official TAB page path must stay project-relative")
        if len({mapping.mapping_id for mapping in self.mappings}) != len(self.mappings):
            raise ValueError("official TAB mapping IDs must be unique within a page")
        return self


class OfficialTabReferenceManifest(BaseModel):
    """Project-local official-score image index. It never becomes musical authority."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    pages: list[OfficialTabReferencePage] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_pages_and_non_overlapping_ranges(self) -> "OfficialTabReferenceManifest":
        if len({page.page_id for page in self.pages}) != len(self.pages):
            raise ValueError("official TAB page IDs must be unique")
        if len({page.relative_path for page in self.pages}) != len(self.pages):
            raise ValueError("official TAB page paths must be unique")

        by_role: dict[ArrangementRole, list[tuple[int, int, str]]] = {
            role: [] for role in ArrangementRole
        }
        for page in self.pages:
            for mapping in page.mappings:
                by_role[mapping.arrangement].append(
                    (mapping.measure_start, mapping.measure_end, f"{page.page_id}/{mapping.mapping_id}")
                )
        for role, ranges in by_role.items():
            ordered = sorted(ranges)
            for previous, current in zip(ordered, ordered[1:]):
                if current[0] <= previous[1]:
                    raise ValueError(
                        f"official TAB {role.value} measure mappings overlap: "
                        f"{previous[2]} ({previous[0]}-{previous[1]}) and "
                        f"{current[2]} ({current[0]}-{current[1]})"
                    )
        return self

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path

    @classmethod
    def read_json(cls, path: Path) -> "OfficialTabReferenceManifest":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class OfficialTabReferenceHit:
    page: OfficialTabReferencePage
    mapping: OfficialTabReferenceMapping

    @property
    def label(self) -> str:
        printed = f"page {self.page.printed_page}" if self.page.printed_page else self.page.page_id
        return (
            f"{printed} · {self.mapping.arrangement.value.title()} · "
            f"bars {self.mapping.measure_start}-{self.mapping.measure_end}"
        )


def manifest_path(project: Path) -> Path:
    return Path(project).resolve() / MANIFEST_RELATIVE_PATH


def _project_file(project: Path, relative_path: str, *, must_exist: bool = True) -> Path:
    root = Path(project).resolve()
    candidate = (root / relative_path).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("official TAB reference escaped the project directory")
    if must_exist and not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def _verify_supported_image(path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_IMAGE_SUFFIXES:
        raise ValueError("official TAB reference must be a JPG, JPEG, or PNG image")
    try:
        with Image.open(path) as image:
            image_format = (image.format or "").upper()
            allowed_formats = SUPPORTED_PIL_FORMATS_BY_SUFFIX[suffix]
            if image_format not in allowed_formats:
                raise ValueError(f"unsupported official TAB image format: {image_format or 'unknown'}")
            # Apple/phone JPEGs can be decoded by Pillow as MPO because they contain
            # multiple JPEG pictures/metadata. The viewer intentionally uses the first
            # frame as the printed TAB page, so verify that first decodable image rather
            # than rejecting a perfectly valid .jpg/.jpeg solely because Pillow reports MPO.
            if image_format == "MPO":
                image.seek(0)
            image.verify()
    except (OSError, SyntaxError) as exc:
        raise ValueError(f"official TAB image cannot be decoded: {path.name}") from exc


def resolve_reference_image(
    project: Path,
    page: OfficialTabReferencePage,
    *,
    verify_hash: bool = True,
) -> Path:
    path = _project_file(project, page.relative_path)
    _verify_supported_image(path)
    if verify_hash and sha256_file(path) != page.sha256:
        raise ValueError(f"official TAB reference changed after registration: {path.name}")
    return path


def load_reference_manifest(
    project: Path,
    *,
    required: bool = False,
    verify_files: bool = True,
) -> OfficialTabReferenceManifest:
    path = manifest_path(project)
    if not path.is_file():
        if required:
            raise FileNotFoundError(path)
        return OfficialTabReferenceManifest()
    manifest = OfficialTabReferenceManifest.read_json(path)
    if verify_files:
        for page in manifest.pages:
            resolve_reference_image(project, page)
    return manifest


def save_reference_manifest(project: Path, manifest: OfficialTabReferenceManifest) -> Path:
    # Re-validate the complete immutable snapshot before replacing project state.
    validated = OfficialTabReferenceManifest.model_validate(manifest.model_dump())
    return validated.write_json(manifest_path(project))


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-")
    return cleaned or "reference-page"


def _mapping_id(role: ArrangementRole, measure_start: int, measure_end: int) -> str:
    return f"{role.value}-{measure_start}-{measure_end}"


def register_reference_page_for_arrangements(
    project: Path,
    source_image: Path,
    *,
    arrangements: Iterable[ArrangementRole | str],
    measure_start: int,
    measure_end: int,
    printed_page: str | None = None,
    normalized_bbox: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0),
) -> list[OfficialTabReferenceHit]:
    """Register one private page for multiple roles with one atomic manifest replacement."""

    roles: list[ArrangementRole] = []
    for value in arrangements:
        role = value if isinstance(value, ArrangementRole) else ArrangementRole(value)
        if role not in roles:
            roles.append(role)
    if not roles:
        raise ValueError("at least one official TAB arrangement is required")

    mappings = [
        OfficialTabReferenceMapping(
            mapping_id=_mapping_id(role, measure_start, measure_end),
            arrangement=role,
            measure_start=measure_start,
            measure_end=measure_end,
            normalized_bbox=normalized_bbox,
        )
        for role in roles
    ]

    project_root = Path(project).resolve()
    source = Path(source_image).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    _verify_supported_image(source)

    manifest = load_reference_manifest(project_root, verify_files=True)
    digest = sha256_file(source)

    pages_dir = project_root / PAGE_DIRECTORY_RELATIVE_PATH
    pages_dir.mkdir(parents=True, exist_ok=True)
    destination = pages_dir / f"{digest[:12]}-{_safe_filename(source.name)}"
    if not destination.exists():
        shutil.copy2(source, destination)
    _verify_supported_image(destination)
    if sha256_file(destination) != digest:
        raise ValueError("official TAB reference copy hash mismatch")

    relative_path = destination.relative_to(project_root).as_posix()
    pages = list(manifest.pages)
    existing_index = next(
        (index for index, page in enumerate(pages) if page.sha256 == digest),
        None,
    )
    if existing_index is None:
        page = OfficialTabReferencePage(
            page_id=f"page-{digest[:16]}",
            relative_path=relative_path,
            sha256=digest,
            printed_page=(printed_page.strip() if printed_page and printed_page.strip() else None),
            mappings=mappings,
        )
        pages.append(page)
    else:
        page = pages[existing_index]
        merged_mappings = list(page.mappings)
        for mapping in mappings:
            current = next(
                (
                    item
                    for item in merged_mappings
                    if item.arrangement is mapping.arrangement
                    and item.measure_start == mapping.measure_start
                    and item.measure_end == mapping.measure_end
                    and item.normalized_bbox == mapping.normalized_bbox
                ),
                None,
            )
            if current is None:
                merged_mappings.append(mapping)
        page = page.model_copy(update={"mappings": merged_mappings})
        if printed_page and printed_page.strip() and page.printed_page != printed_page.strip():
            page = page.model_copy(update={"printed_page": printed_page.strip()})
        pages[existing_index] = page

    # Constructing the complete snapshot validates every selected role together. If any
    # mapping conflicts, the existing manifest is untouched; a copied private image may
    # remain as non-authoritative source evidence, consistent with removal semantics.
    updated = OfficialTabReferenceManifest(pages=pages)
    save_reference_manifest(project_root, updated)
    stored_page = next(item for item in updated.pages if item.sha256 == digest)
    return [
        OfficialTabReferenceHit(
            stored_page,
            next(
                item
                for item in stored_page.mappings
                if item.arrangement is role
                and item.measure_start == measure_start
                and item.measure_end == measure_end
                and item.normalized_bbox == normalized_bbox
            ),
        )
        for role in roles
    ]


def register_reference_page(
    project: Path,
    source_image: Path,
    *,
    arrangement: ArrangementRole | str,
    measure_start: int,
    measure_end: int,
    printed_page: str | None = None,
    normalized_bbox: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0),
) -> OfficialTabReferenceHit:
    """Copy one private page into the project and register one deterministic measure range."""

    return register_reference_page_for_arrangements(
        project,
        source_image,
        arrangements=(arrangement,),
        measure_start=measure_start,
        measure_end=measure_end,
        printed_page=printed_page,
        normalized_bbox=normalized_bbox,
    )[0]


def remove_reference_mapping(
    project: Path,
    *,
    page_id: str,
    mapping_id: str,
) -> OfficialTabReferenceManifest:
    """Remove only manifest authority. The copied private image remains on disk intentionally."""

    manifest = load_reference_manifest(project, verify_files=True)
    pages: list[OfficialTabReferencePage] = []
    found = False
    for page in manifest.pages:
        if page.page_id != page_id:
            pages.append(page)
            continue
        remaining = [mapping for mapping in page.mappings if mapping.mapping_id != mapping_id]
        found = len(remaining) != len(page.mappings)
        if remaining:
            pages.append(page.model_copy(update={"mappings": remaining}))
    if not found:
        raise ValueError("official TAB mapping not found")
    updated = OfficialTabReferenceManifest(pages=pages)
    save_reference_manifest(project, updated)
    return updated


def reference_hits_for_role(
    manifest: OfficialTabReferenceManifest,
    arrangement: ArrangementRole | str,
) -> list[OfficialTabReferenceHit]:
    role = arrangement if isinstance(arrangement, ArrangementRole) else ArrangementRole(arrangement)
    hits = [
        OfficialTabReferenceHit(page, mapping)
        for page in manifest.pages
        for mapping in page.mappings
        if mapping.arrangement is role
    ]
    return sorted(hits, key=lambda item: (item.mapping.measure_start, item.mapping.measure_end, item.page.page_id))


def reference_for_measure(
    manifest: OfficialTabReferenceManifest,
    arrangement: ArrangementRole | str,
    measure_number: int,
) -> OfficialTabReferenceHit | None:
    for hit in reference_hits_for_role(manifest, arrangement):
        if hit.mapping.measure_start <= measure_number <= hit.mapping.measure_end:
            return hit
    return None


def seek_seconds_for_measure(measures: Iterable[object], measure_number: int) -> float:
    """Resolve a score bar to the already-authoritative shared recording clock."""

    for measure in measures:
        if int(getattr(measure, "number")) == int(measure_number):
            return float(getattr(measure, "start_seconds"))
    raise ValueError(f"score bar {measure_number} is unavailable on the current shared timeline")
