from __future__ import annotations

from collections.abc import Iterable
import os
from pathlib import Path
import re
import shutil
import tempfile

from PIL import Image

from .hashing import sha256_file
from .official_tab_reference import (
    PAGE_DIRECTORY_RELATIVE_PATH,
    SUPPORTED_IMAGE_SUFFIXES,
    SUPPORTED_PIL_FORMATS,
    OfficialTabReferenceHit,
    OfficialTabReferenceManifest,
    OfficialTabReferenceMapping,
    OfficialTabReferencePage,
    load_reference_manifest,
    manifest_path,
)
from .score_source import ArrangementRole


def normalize_arrangements(
    arrangements: Iterable[ArrangementRole | str],
) -> tuple[ArrangementRole, ...]:
    """Return a non-empty, deduplicated role tuple in canonical enum order."""

    requested = {
        arrangement if isinstance(arrangement, ArrangementRole) else ArrangementRole(arrangement)
        for arrangement in arrangements
    }
    if not requested:
        raise ValueError("Select at least one arrangement for the official TAB page.")
    return tuple(role for role in ArrangementRole if role in requested)


def _verify_supported_image(path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_IMAGE_SUFFIXES:
        raise ValueError("official TAB reference must be a JPG, JPEG, or PNG image")
    try:
        with Image.open(path) as image:
            image_format = (image.format or "").upper()
            if image_format not in SUPPORTED_PIL_FORMATS:
                raise ValueError(f"unsupported official TAB image format: {image_format or 'unknown'}")
            image.verify()
    except (OSError, SyntaxError) as exc:
        raise ValueError(f"official TAB image cannot be decoded: {path.name}") from exc


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-")
    return cleaned or "reference-page"


def _mapping_id(role: ArrangementRole, measure_start: int, measure_end: int) -> str:
    return f"{role.value}-{measure_start}-{measure_end}"


def _write_manifest_atomically(project: Path, manifest: OfficialTabReferenceManifest) -> None:
    """Replace manifest authority only after a complete validated snapshot exists."""

    target = manifest_path(project)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".official-tab-manifest-",
        suffix=".json.tmp",
        dir=target.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(manifest.model_dump_json(indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def register_reference_page_for_arrangements(
    project: Path,
    source_image: Path,
    *,
    arrangements: Iterable[ArrangementRole | str],
    measure_start: int,
    measure_end: int,
    printed_page: str | None = None,
    normalized_bbox: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0),
) -> tuple[OfficialTabReferenceHit, ...]:
    """Register one private page for one or more arrangements as one manifest transaction.

    The complete proposed manifest is validated before any new page copy or manifest
    authority is written. If one selected role conflicts with an existing mapping, no
    other selected role is partially registered.
    """

    project_root = Path(project).resolve()
    source = Path(source_image).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    _verify_supported_image(source)

    roles = normalize_arrangements(arrangements)
    requested_mappings = tuple(
        OfficialTabReferenceMapping(
            mapping_id=_mapping_id(role, measure_start, measure_end),
            arrangement=role,
            measure_start=measure_start,
            measure_end=measure_end,
            normalized_bbox=normalized_bbox,
        )
        for role in roles
    )

    manifest = load_reference_manifest(project_root, verify_files=True)
    digest = sha256_file(source)
    destination = (
        project_root
        / PAGE_DIRECTORY_RELATIVE_PATH
        / f"{digest[:12]}-{_safe_filename(source.name)}"
    )
    relative_path = destination.relative_to(project_root).as_posix()
    clean_printed_page = printed_page.strip() if printed_page and printed_page.strip() else None

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
            printed_page=clean_printed_page,
            mappings=list(requested_mappings),
        )
        pages.append(page)
    else:
        page = pages[existing_index]
        mappings = list(page.mappings)
        for requested in requested_mappings:
            current = next(
                (
                    item
                    for item in mappings
                    if item.arrangement is requested.arrangement
                    and item.measure_start == requested.measure_start
                    and item.measure_end == requested.measure_end
                    and item.normalized_bbox == requested.normalized_bbox
                ),
                None,
            )
            if current is None:
                mappings.append(requested)
        updates: dict[str, object] = {"mappings": mappings}
        if clean_printed_page is not None and clean_printed_page != page.printed_page:
            updates["printed_page"] = clean_printed_page
        page = page.model_copy(update=updates)
        pages[existing_index] = page

    # This is the transaction gate: all role-level overlap and page invariants must pass
    # before a new private image copy or manifest replacement can happen.
    updated = OfficialTabReferenceManifest(pages=pages)

    created_copy = False
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copy2(source, destination)
            created_copy = True
        _verify_supported_image(destination)
        if sha256_file(destination) != digest:
            raise ValueError("official TAB reference copy hash mismatch")
        _write_manifest_atomically(project_root, updated)
    except Exception:
        if created_copy:
            destination.unlink(missing_ok=True)
        raise

    stored_page = next(item for item in updated.pages if item.sha256 == digest)
    hits: list[OfficialTabReferenceHit] = []
    for role in roles:
        mapping = next(
            item
            for item in stored_page.mappings
            if item.arrangement is role
            and item.measure_start == measure_start
            and item.measure_end == measure_end
            and item.normalized_bbox == normalized_bbox
        )
        hits.append(OfficialTabReferenceHit(stored_page, mapping))
    return tuple(hits)
