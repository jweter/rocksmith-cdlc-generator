from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw
import yaml

from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.private_score_bundle import register_private_score_bundle
from rocksmith_cdlc_generator.score_measure_segmentation import segment_score_measures


def _draw_system(draw: ImageDraw.ImageDraw, *, top: int, width: int) -> None:
    left = 90
    right = width - 90
    for y in (top, top + 12, top + 24, top + 36, top + 48):
        draw.line((left, y, right, y), fill="black", width=2)
    for y in (top + 78, top + 92, top + 106, top + 120):
        draw.line((left, y, right, y), fill="black", width=2)

    # Five aligned barlines create four deterministic synthetic measures. They are
    # drawn independently in notation and TAB, matching the corroboration rule used by
    # the real detector without embedding copyrighted music in the test fixture.
    for x in (180, 410, 650, 900, 1080):
        draw.line((x, top - 3, x, top + 50), fill="black", width=3)
        draw.line((x, top + 75, x, top + 123), fill="black", width=3)

    # Notation-only vertical stems must not become barlines because there is no aligned
    # TAB vertical stroke at these x positions.
    for x in (300, 540, 780):
        draw.ellipse((x, top + 20, x + 10, top + 28), fill="black")
        draw.line((x + 9, top + 22, x + 9, top - 10), fill="black", width=2)


def _register_page(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    page = source / "page-2.png"
    image = Image.new("RGB", (1200, 1600), "white")
    draw = ImageDraw.Draw(image)
    for top in (220, 500, 780, 1060, 1340):
        _draw_system(draw, top=top, width=image.width)
    image.save(page)

    manifest = {
        "schema_version": 1,
        "bundle_id": "SYNTHETIC_MEASURE_SEGMENTATION",
        "work_title": "Synthetic score",
        "composer": "Test",
        "instrument": "bass",
        "tuning_name": "Drop D",
        "tuning_midi": [38, 45, 50, 55],
        "source_rights_class": "user_owned_local",
        "redistribution_allowed": False,
        "pages": [
            {
                "source_filename": page.name,
                "kind": "score",
                "printed_page": 2,
                "expected_sha256": sha256_file(page),
            }
        ],
        "movements": [
            {
                "movement_id": "prelude",
                "title": "Prelude",
                "start_page": 2,
                "end_page": 2,
                "time_signature": "4/4",
            }
        ],
    }
    manifest_path = tmp_path / "bundle.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    project = tmp_path / "project"
    register_private_score_bundle(project, manifest_path, source)
    return project


def test_segment_first_eight_measures_uses_paired_barline_evidence(tmp_path: Path) -> None:
    project = _register_page(tmp_path)

    result = segment_score_measures(project, 2, limit=8, expected_system_count=5)

    assert len(result.measures) == 8
    assert [measure.measure_index for measure in result.measures] == list(range(8))
    assert [measure.system_index for measure in result.measures] == [0, 0, 0, 0, 1, 1, 1, 1]
    assert all(measure.region.x1 > measure.region.x0 for measure in result.measures)
    assert all(measure.region.y1 > measure.region.y0 for measure in result.measures)
    assert all(measure.region.x1 <= result.page_size[0] for measure in result.measures)
    assert all(measure.region.y1 <= result.page_size[1] for measure in result.measures)
    assert all(not measure.left_boundary.inferred_from_staff_extent for measure in result.measures)
    assert all(not measure.right_boundary.inferred_from_staff_extent for measure in result.measures)

    # The notation-only stems at x ~= 300/540/780 must not create extra measures.
    first_system = [measure for measure in result.measures if measure.system_index == 0]
    assert len(first_system) == 4


def test_measure_limit_is_explicit_and_stable(tmp_path: Path) -> None:
    project = _register_page(tmp_path)

    result = segment_score_measures(project, 2, limit=4, expected_system_count=5)

    assert len(result.measures) == 4
    assert all(measure.system_index == 0 for measure in result.measures)
    assert not any(warning.startswith("measure_limit_not_reached") for warning in result.warnings)
