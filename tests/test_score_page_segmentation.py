from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw
import yaml

from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.private_score_bundle import register_private_score_bundle
from rocksmith_cdlc_generator.score_page_segmentation import detect_score_systems


def _draw_system(draw: ImageDraw.ImageDraw, *, top: int, width: int) -> None:
    left = 90
    right = width - 90
    for y in (top, top + 12, top + 24, top + 36, top + 48):
        draw.line((left, y, right, y), fill="black", width=2)
    for y in (top + 78, top + 92, top + 106, top + 120):
        draw.line((left, y, right, y), fill="black", width=2)
    for x in (180, 410, 650, 900, 1080):
        draw.line((x, top - 3, x, top + 50), fill="black", width=3)
        draw.line((x, top + 75, x, top + 123), fill="black", width=3)
    # Note-like local detail prevents the fixture from being only horizontal rules.
    for offset in (250, 520, 790):
        draw.ellipse((offset, top + 20, offset + 10, top + 28), fill="black")
        draw.line((offset + 9, top + 22, offset + 9, top - 8), fill="black", width=2)


def _register_synthetic_page(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    path = source / "page-2.png"
    image = Image.new("RGB", (1200, 1600), "white")
    draw = ImageDraw.Draw(image)
    for top in (220, 500, 780, 1060, 1340):
        _draw_system(draw, top=top, width=image.width)
    image.save(path)

    spec = {
        "schema_version": 1,
        "bundle_id": "SYNTHETIC_SEGMENTATION",
        "work_title": "Synthetic score",
        "composer": "Test",
        "instrument": "bass",
        "tuning_name": "Drop D",
        "tuning_midi": [38, 45, 50, 55],
        "source_rights_class": "user_owned_local",
        "redistribution_allowed": False,
        "pages": [
            {
                "source_filename": path.name,
                "kind": "score",
                "printed_page": 2,
                "expected_sha256": sha256_file(path),
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
    spec_path = tmp_path / "bundle.yaml"
    spec_path.write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")
    project = tmp_path / "project"
    register_private_score_bundle(project, spec_path, source)
    return project


def test_detect_score_systems_returns_reading_order_and_provenance(tmp_path: Path) -> None:
    project = _register_synthetic_page(tmp_path)

    result = detect_score_systems(project, 2, expected_system_count=5)

    assert result.printed_page == 2
    assert len(result.systems) == 5
    assert not result.warnings
    assert [system.system_index for system in result.systems] == list(range(5))
    assert [system.region.y0 for system in result.systems] == sorted(
        system.region.y0 for system in result.systems
    )
    assert all(system.region.x0 == 0 for system in result.systems)
    assert all(system.region.x1 == result.page_size[0] for system in result.systems)
    assert all(0.0 <= system.confidence <= 1.0 for system in result.systems)
    assert all(system.confidence >= 0.60 for system in result.systems)
    assert len(result.derivative_sha256) == 64
    assert len(result.source_sha256) == 64


def test_detect_score_systems_surfaces_expected_count_mismatch(tmp_path: Path) -> None:
    project = _register_synthetic_page(tmp_path)

    result = detect_score_systems(project, 2, expected_system_count=4)

    assert len(result.systems) == 5
    assert "system_count_mismatch:expected=4,detected=5" in result.warnings
