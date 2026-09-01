from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw
import yaml

from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.private_score_bundle import register_private_score_bundle
from rocksmith_cdlc_generator.score_page_preprocessing import (
    normalize_movement_score_pages,
    normalize_registered_score_page,
)


def _write_score_page(path: Path, *, size: tuple[int, int] = (1200, 1600)) -> None:
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    # Synthetic staff/TAB-like line groups provide deterministic detail/contrast without
    # embedding any copyrighted notation in the repository fixtures.
    for y in (260, 272, 284, 296, 308, 370, 382, 394, 406):
        draw.line((100, y, size[0] - 100, y), fill="black", width=2)
    for x in (220, 480, 760, 1020):
        draw.line((x, 250, x, 410), fill="black", width=3)
    image.save(path)


def _register_project(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    _write_score_page(source / "page-2.png")
    _write_score_page(source / "page-3.png")

    spec = {
        "schema_version": 1,
        "bundle_id": "SYNTHETIC_PREPROCESSING",
        "work_title": "Synthetic score",
        "composer": "Test",
        "instrument": "bass",
        "tuning_name": "Drop D",
        "tuning_midi": [38, 45, 50, 55],
        "source_rights_class": "user_owned_local",
        "redistribution_allowed": False,
        "pages": [
            {
                "source_filename": "page-2.png",
                "kind": "score",
                "printed_page": 2,
                "expected_sha256": sha256_file(source / "page-2.png"),
            },
            {
                "source_filename": "page-3.png",
                "kind": "score",
                "printed_page": 3,
                "expected_sha256": sha256_file(source / "page-3.png"),
            },
        ],
        "movements": [
            {
                "movement_id": "prelude",
                "title": "Prelude",
                "start_page": 2,
                "end_page": 3,
                "time_signature": "4/4",
            }
        ],
    }
    spec_path = tmp_path / "bundle.yaml"
    spec_path.write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")

    project = tmp_path / "project"
    register_private_score_bundle(project, spec_path, source)
    return project


def test_normalize_registered_page_creates_hash_bound_derivative(tmp_path: Path) -> None:
    project = _register_project(tmp_path)
    registered_source = next((project / "references" / "printed-score" / "pages").glob("*page-2.png"))
    source_sha_before = sha256_file(registered_source)

    result = normalize_registered_score_page(project, 2, max_long_edge=1000)

    derivative = project / result.derivative_relative_path
    metadata = derivative.with_suffix(".json")
    assert derivative.is_file()
    assert metadata.is_file()
    assert result.source_sha256 == source_sha_before
    assert result.derivative_sha256 == sha256_file(derivative)
    assert result.source_size == (1200, 1600)
    assert result.output_size == (750, 1000)
    assert sha256_file(registered_source) == source_sha_before

    with Image.open(derivative) as image:
        assert image.mode == "L"
        assert image.size == (750, 1000)


def test_normalization_records_quality_diagnostics(tmp_path: Path) -> None:
    project = _register_project(tmp_path)

    result = normalize_registered_score_page(project, 2)

    assert result.quality.width == 1200
    assert result.quality.height == 1600
    assert result.quality.short_edge == 1200
    assert result.quality.long_edge == 1600
    assert result.quality.contrast_stddev > 0
    assert result.quality.edge_energy > 0
    assert "low_resolution" not in result.quality.warnings


def test_normalize_movement_preserves_registered_page_order(tmp_path: Path) -> None:
    project = _register_project(tmp_path)

    pages = normalize_movement_score_pages(project, "prelude", max_long_edge=900)

    assert [page.printed_page for page in pages] == [2, 3]
    assert all((project / page.derivative_relative_path).is_file() for page in pages)
