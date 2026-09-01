from __future__ import annotations

from pathlib import Path
import wave

from PIL import Image, ImageDraw
import pytest
import yaml

from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.models import ProjectManifest
from rocksmith_cdlc_generator.printed_score_desktop_actions import (
    PrintedScoreDesktopActionError,
    latest_reviewed_fixture,
    recognize_printed_score_for_review,
)
from rocksmith_cdlc_generator.printed_score_project import (
    PrintedScoreProjectError,
    create_printed_score_project,
    is_printed_score_project,
    printed_score_project_authority_path,
    read_printed_score_project_authority,
)
from rocksmith_cdlc_generator.printed_score_project_cli import main as score_project_main
from rocksmith_cdlc_generator.private_score_bundle import verify_private_score_bundle


def _score_page(path: Path, *, marker: int) -> None:
    image = Image.new("L", (320, 480), color=255)
    draw = ImageDraw.Draw(image)
    draw.rectangle((40 + marker, 80, 280, 400), outline=0, width=3)
    draw.text((60, 100 + marker), f"synthetic {marker}", fill=0)
    image.save(path)


def _bundle(tmp_path: Path, *, bad_hash: bool = False) -> tuple[Path, Path]:
    source = tmp_path / "private-pages"
    source.mkdir()
    _score_page(source / "page-2.png", marker=2)
    _score_page(source / "page-3.png", marker=3)

    page2_hash = sha256_file(source / "page-2.png")
    if bad_hash:
        page2_hash = "0" * 64
    payload = {
        "schema_version": 1,
        "bundle_id": "SYNTHETIC_SCORE_PROJECT",
        "work_title": "Synthetic Suite",
        "composer": "Test Composer",
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
                "expected_sha256": page2_hash,
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
                "end_page": 2,
                "time_signature": "4/4",
            },
            {
                "movement_id": "allemande",
                "title": "Allemande",
                "start_page": 3,
                "end_page": 3,
                "time_signature": "4/4",
            },
        ],
    }
    spec = tmp_path / "bundle.yaml"
    spec.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return spec, source


def test_create_printed_score_project_is_desktop_openable_and_private(tmp_path: Path) -> None:
    spec, source = _bundle(tmp_path)
    projects = tmp_path / "projects"

    project = create_printed_score_project(
        spec_path=spec,
        source_dir=source,
        projects_root=projects,
        movement_id="prelude",
    )

    assert is_printed_score_project(project)
    manifest = ProjectManifest.load(project)
    assert manifest.artist == "Test Composer"
    assert manifest.title == "Synthetic Suite — Prelude"
    assert manifest.arrangement_instruments == ["bass"]
    assert manifest.source_metadata.format_name == "printed-score-bootstrap-silence"

    authority = read_printed_score_project_authority(project)
    assert authority["movement_id"] == "prelude"
    assert authority["start_page"] == 2
    assert authority["end_page"] == 2

    bootstrap = project / manifest.source_project_path
    assert bootstrap.is_file()
    assert sha256_file(bootstrap) == manifest.source_sha256
    with wave.open(str(bootstrap), "rb") as handle:
        assert handle.getnchannels() == 1
        assert handle.getframerate() == 44_100
        assert handle.getnframes() == 44_100

    registered = verify_private_score_bundle(project)
    assert registered.bundle_id == "SYNTHETIC_SCORE_PROJECT"
    assert [page.printed_page for page in registered.pages] == [2, 3]
    assert all((project / page.relative_path).is_file() for page in registered.pages)


def test_selected_movement_rejects_recognition_from_other_movement(tmp_path: Path) -> None:
    spec, source = _bundle(tmp_path)
    project = create_printed_score_project(
        spec_path=spec,
        source_dir=source,
        projects_root=tmp_path / "projects",
        movement_id="prelude",
    )

    with pytest.raises(PrintedScoreDesktopActionError, match="outside selected movement"):
        recognize_printed_score_for_review(project, printed_page=3)


def test_legacy_printed_score_project_stays_in_printed_mode_and_fails_closed(tmp_path: Path) -> None:
    spec, source = _bundle(tmp_path)
    project = create_printed_score_project(
        spec_path=spec,
        source_dir=source,
        projects_root=tmp_path / "projects",
        movement_id="prelude",
    )
    printed_score_project_authority_path(project).unlink()

    assert is_printed_score_project(project)
    with pytest.raises(PrintedScoreProjectError, match="must be recreated or migrated"):
        read_printed_score_project_authority(project)


def test_latest_reviewed_fixture_ignores_other_movement_page(tmp_path: Path) -> None:
    spec, source = _bundle(tmp_path)
    project = create_printed_score_project(
        spec_path=spec,
        source_dir=source,
        projects_root=tmp_path / "projects",
        movement_id="prelude",
    )
    recognition = project / "derived" / "printed-score" / "recognition"
    recognition.mkdir(parents=True, exist_ok=True)
    unauthorized = recognition / "page-003-deadbeef0000-reviewed-fixture.json"
    authorized = recognition / "page-002-cafebabe0000-reviewed-fixture.json"
    unauthorized.write_text("{}\n", encoding="utf-8")
    authorized.write_text("{}\n", encoding="utf-8")

    assert latest_reviewed_fixture(project) == authorized


def test_latest_reviewed_fixture_rejects_when_only_other_movement_exists(tmp_path: Path) -> None:
    spec, source = _bundle(tmp_path)
    project = create_printed_score_project(
        spec_path=spec,
        source_dir=source,
        projects_root=tmp_path / "projects",
        movement_id="prelude",
    )
    recognition = project / "derived" / "printed-score" / "recognition"
    recognition.mkdir(parents=True, exist_ok=True)
    (recognition / "page-003-deadbeef0000-reviewed-fixture.json").write_text(
        "{}\n", encoding="utf-8"
    )

    with pytest.raises(PrintedScoreDesktopActionError, match="none belong"):
        latest_reviewed_fixture(project)


def test_project_creation_rejects_non_bass_manifest(tmp_path: Path) -> None:
    spec, source = _bundle(tmp_path)
    payload = yaml.safe_load(spec.read_text(encoding="utf-8"))
    payload["instrument"] = "lead"
    spec.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(PrintedScoreProjectError, match="supports Bass only"):
        create_printed_score_project(
            spec_path=spec,
            source_dir=source,
            projects_root=tmp_path / "projects",
            movement_id="prelude",
        )


def test_list_movements_does_not_require_creation_paths(tmp_path: Path, capsys) -> None:
    spec, _source = _bundle(tmp_path)

    assert score_project_main(["--manifest", str(spec), "--list-movements"]) == 0
    output = capsys.readouterr().out
    assert "prelude\tPrelude\tpages 2-2" in output
    assert "allemande\tAllemande\tpages 3-3" in output


def test_project_creation_rolls_back_if_private_page_hash_is_wrong(tmp_path: Path) -> None:
    spec, source = _bundle(tmp_path, bad_hash=True)
    projects = tmp_path / "projects"

    with pytest.raises(ValueError, match="hash mismatch"):
        create_printed_score_project(
            spec_path=spec,
            source_dir=source,
            projects_root=projects,
            movement_id="prelude",
        )

    assert list(projects.glob("*")) == []


def test_unknown_movement_is_rejected_before_project_is_created(tmp_path: Path) -> None:
    spec, source = _bundle(tmp_path)
    projects = tmp_path / "projects"

    with pytest.raises(PrintedScoreProjectError, match="available: prelude, allemande"):
        create_printed_score_project(
            spec_path=spec,
            source_dir=source,
            projects_root=projects,
            movement_id="missing",
        )

    assert not projects.exists()
