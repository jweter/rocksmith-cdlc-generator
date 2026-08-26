from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest
from pydantic import ValidationError

from rocksmith_cdlc_generator.eof_measure_review import MeasureWindow
from rocksmith_cdlc_generator.official_tab_reference import (
    OfficialTabReferenceManifest,
    OfficialTabReferenceMapping,
    OfficialTabReferencePage,
    load_reference_manifest,
    reference_for_measure,
    register_reference_page,
    resolve_reference_image,
    seek_seconds_for_measure,
)


def _page(path: Path, *, color: tuple[int, int, int] = (245, 245, 245)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (640, 900), color).save(path)
    return path


def test_register_reference_page_copies_private_image_and_maps_measure(tmp_path: Path) -> None:
    project = tmp_path / "song"
    source = _page(tmp_path / "camera" / "page-12.jpg")

    hit = register_reference_page(
        project,
        source,
        arrangement="lead",
        measure_start=33,
        measure_end=40,
        printed_page="12",
    )

    manifest = load_reference_manifest(project)
    assert len(manifest.pages) == 1
    assert hit.page.printed_page == "12"
    assert hit.page.relative_path.startswith("references/official-tab/pages/")
    assert resolve_reference_image(project, hit.page).is_file()

    current = reference_for_measure(manifest, "lead", 34)
    assert current is not None
    assert current.page.page_id == hit.page.page_id
    assert current.mapping.measure_start == 33
    assert current.mapping.measure_end == 40
    assert reference_for_measure(manifest, "lead", 41) is None
    assert reference_for_measure(manifest, "rhythm", 34) is None


def test_reference_hash_change_fails_closed(tmp_path: Path) -> None:
    project = tmp_path / "song"
    source = _page(tmp_path / "page.png")
    hit = register_reference_page(
        project,
        source,
        arrangement="bass",
        measure_start=1,
        measure_end=8,
    )

    stored = resolve_reference_image(project, hit.page)
    _page(stored, color=(20, 30, 40))

    with pytest.raises(ValueError, match="changed after registration"):
        load_reference_manifest(project, verify_files=True)


def test_reference_path_cannot_escape_project(tmp_path: Path) -> None:
    project = tmp_path / "song"
    outside = _page(tmp_path / "outside.png")
    mapping = OfficialTabReferenceMapping(
        mapping_id="lead-1-4",
        arrangement="lead",
        measure_start=1,
        measure_end=4,
    )

    page = OfficialTabReferencePage(
        page_id="page-test",
        relative_path="references/official-tab/pages/test.png",
        sha256="a" * 64,
        mappings=[mapping],
    )
    escaped = page.model_copy(update={"relative_path": f"../{outside.name}"})

    with pytest.raises(ValueError, match="escaped the project directory"):
        resolve_reference_image(project, escaped)


def test_manifest_rejects_overlapping_ranges_for_same_arrangement() -> None:
    first = OfficialTabReferencePage(
        page_id="page-a",
        relative_path="references/official-tab/pages/a.png",
        sha256="a" * 64,
        mappings=[
            OfficialTabReferenceMapping(
                mapping_id="lead-1-8",
                arrangement="lead",
                measure_start=1,
                measure_end=8,
            )
        ],
    )
    second = OfficialTabReferencePage(
        page_id="page-b",
        relative_path="references/official-tab/pages/b.png",
        sha256="b" * 64,
        mappings=[
            OfficialTabReferenceMapping(
                mapping_id="lead-8-12",
                arrangement="lead",
                measure_start=8,
                measure_end=12,
            )
        ],
    )

    with pytest.raises(ValidationError, match="measure mappings overlap"):
        OfficialTabReferenceManifest(pages=[first, second])


def test_measure_mapping_resolves_existing_shared_clock_start() -> None:
    measures = [
        MeasureWindow(number=33, start_seconds=75.0, end_seconds=77.0, numerator=4, denominator=4),
        MeasureWindow(number=34, start_seconds=77.0, end_seconds=79.0, numerator=4, denominator=4),
        MeasureWindow(number=35, start_seconds=79.0, end_seconds=81.0, numerator=4, denominator=4),
    ]

    assert seek_seconds_for_measure(measures, 34) == pytest.approx(77.0)
    with pytest.raises(ValueError, match="bar 36 is unavailable"):
        seek_seconds_for_measure(measures, 36)
