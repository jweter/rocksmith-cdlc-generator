from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest
import yaml

from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.private_score_bundle import (
    PrivateScoreBundleError,
    PrivateScoreBundleSpec,
    movement_score_pages,
    register_private_score_bundle,
    registered_manifest_path,
    verify_private_score_bundle,
)


def _write_png(path: Path, value: int) -> None:
    Image.new("L", (12, 12), color=value).save(path)


def _write_spec(path: Path, source_dir: Path) -> None:
    payload = {
        "schema_version": 1,
        "bundle_id": "TEST_Bass_Score",
        "work_title": "Synthetic score",
        "composer": "Test Composer",
        "instrument": "bass",
        "tuning_name": "Drop D",
        "tuning_midi": [38, 45, 50, 55],
        "source_rights_class": "user_owned_local",
        "redistribution_allowed": False,
        "pages": [
            {
                "source_filename": "contents.png",
                "kind": "contents",
                "expected_sha256": sha256_file(source_dir / "contents.png"),
            },
            {
                "source_filename": "page-2.png",
                "kind": "score",
                "printed_page": 2,
                "expected_sha256": sha256_file(source_dir / "page-2.png"),
            },
            {
                "source_filename": "page-3.png",
                "kind": "score",
                "printed_page": 3,
                "expected_sha256": sha256_file(source_dir / "page-3.png"),
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
        "notation_features": ["hammer_on", "pull_off"],
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_register_and_verify_private_score_bundle(tmp_path: Path) -> None:
    source_dir = tmp_path / "private-source"
    source_dir.mkdir()
    _write_png(source_dir / "contents.png", 20)
    _write_png(source_dir / "page-2.png", 40)
    _write_png(source_dir / "page-3.png", 60)
    spec_path = tmp_path / "bundle.yaml"
    _write_spec(spec_path, source_dir)

    project = tmp_path / "project"
    bundle = register_private_score_bundle(project, spec_path, source_dir)

    assert registered_manifest_path(project).is_file()
    assert len(bundle.pages) == 3
    assert [page.printed_page for page in movement_score_pages(bundle, "prelude")] == [2, 3]
    assert all((project / page.relative_path).is_file() for page in bundle.pages)

    verified = verify_private_score_bundle(project)
    assert verified.bundle_id == "TEST_Bass_Score"
    assert verified.tuning_midi == [38, 45, 50, 55]


def test_registration_rejects_source_hash_mismatch(tmp_path: Path) -> None:
    source_dir = tmp_path / "private-source"
    source_dir.mkdir()
    _write_png(source_dir / "contents.png", 20)
    _write_png(source_dir / "page-2.png", 40)
    _write_png(source_dir / "page-3.png", 60)
    spec_path = tmp_path / "bundle.yaml"
    _write_spec(spec_path, source_dir)

    _write_png(source_dir / "page-2.png", 99)

    with pytest.raises(PrivateScoreBundleError, match="hash mismatch for page-2.png"):
        register_private_score_bundle(tmp_path / "project", spec_path, source_dir)


def test_verification_detects_registered_page_mutation(tmp_path: Path) -> None:
    source_dir = tmp_path / "private-source"
    source_dir.mkdir()
    _write_png(source_dir / "contents.png", 20)
    _write_png(source_dir / "page-2.png", 40)
    _write_png(source_dir / "page-3.png", 60)
    spec_path = tmp_path / "bundle.yaml"
    _write_spec(spec_path, source_dir)

    project = tmp_path / "project"
    bundle = register_private_score_bundle(project, spec_path, source_dir)
    score_page = next(page for page in bundle.pages if page.printed_page == 2)
    _write_png(project / score_page.relative_path, 88)

    with pytest.raises(PrivateScoreBundleError, match="changed after registration"):
        verify_private_score_bundle(project)


def test_reregistration_rejects_changed_source_manifest(tmp_path: Path) -> None:
    source_dir = tmp_path / "private-source"
    source_dir.mkdir()
    _write_png(source_dir / "contents.png", 20)
    _write_png(source_dir / "page-2.png", 40)
    _write_png(source_dir / "page-3.png", 60)
    spec_path = tmp_path / "bundle.yaml"
    _write_spec(spec_path, source_dir)

    project = tmp_path / "project"
    register_private_score_bundle(project, spec_path, source_dir)
    spec_path.write_text(spec_path.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")

    with pytest.raises(PrivateScoreBundleError, match="source manifest changed"):
        register_private_score_bundle(project, spec_path, source_dir)


def test_bundle_spec_rejects_movement_referencing_missing_page() -> None:
    with pytest.raises(ValueError, match="references missing score pages"):
        PrivateScoreBundleSpec.model_validate(
            {
                "schema_version": 1,
                "bundle_id": "missing-page",
                "work_title": "Synthetic",
                "composer": "Test",
                "instrument": "bass",
                "tuning_name": "E Standard",
                "tuning_midi": [40, 45, 50, 55],
                "pages": [
                    {"source_filename": "page-2.png", "kind": "score", "printed_page": 2}
                ],
                "movements": [
                    {
                        "movement_id": "movement",
                        "title": "Movement",
                        "start_page": 2,
                        "end_page": 3,
                    }
                ],
            }
        )


def test_committed_bwv1007_bundle_manifest_is_complete() -> None:
    path = Path("benchmarks/private_reference_sets/bwv1007_bass_dropd.yaml")
    spec = PrivateScoreBundleSpec.read_yaml(path)

    assert spec.bundle_id == "BWV1007_Bass_DropD"
    assert spec.instrument == "bass"
    assert spec.tuning_midi == [38, 45, 50, 55]
    assert spec.redistribution_allowed is False
    assert [page.printed_page for page in spec.pages if page.kind == "score"] == list(range(2, 15))
    assert len(spec.pages) == 15
    assert [movement.movement_id for movement in spec.movements] == [
        "prelude",
        "allemande",
        "courante",
        "sarabande",
        "menuet_i",
        "menuet_ii",
        "gigue",
    ]
    assert all(page.expected_sha256 for page in spec.pages)
