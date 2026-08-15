from pathlib import Path

import pytest

from rocksmith_cdlc_generator.build_presentation import (
    build_presentation_cover_path,
    load_build_presentation,
    save_build_presentation,
)
from rocksmith_cdlc_generator.package_generation import current_package_generation


def test_changed_presentation_invalidates_stale_package_state(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    cover = tmp_path / "cover.png"
    cover.write_bytes(b"png-fixture")
    stale_dlcbuilder = project / "build" / "dlcbuilder"
    stale_staging = project / "build" / "staging"
    stale_dlcbuilder.mkdir(parents=True)
    stale_staging.mkdir(parents=True)
    (stale_dlcbuilder / "old.rs2dlc").write_text("stale", encoding="utf-8")
    (stale_staging / "old.psarc").write_bytes(b"stale")

    before = current_package_generation(project)
    presentation = save_build_presentation(
        project,
        album_name="Ashes of the Wake",
        year=2004,
        cover=cover,
    )
    after = current_package_generation(project)

    assert before != after
    assert not stale_dlcbuilder.exists()
    assert not stale_staging.exists()
    assert presentation.album_name == "Ashes of the Wake"
    assert presentation.year == 2004
    saved_cover = build_presentation_cover_path(project, presentation)
    assert saved_cover == project / "assets" / "cover.png"
    assert saved_cover.read_bytes() == b"png-fixture"


def test_identical_reconfirmation_does_not_advance_package_generation(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"jpeg-fixture")

    first = save_build_presentation(
        project,
        album_name="Album",
        year=2024,
        cover=cover,
    )
    generation = current_package_generation(project)
    second = save_build_presentation(
        project,
        album_name=" Album ",
        year=2024,
        cover=cover,
    )

    assert second == first
    assert current_package_generation(project) == generation


def test_tampered_saved_cover_fails_closed(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    cover = tmp_path / "cover.jpeg"
    cover.write_bytes(b"original")
    presentation = save_build_presentation(
        project,
        album_name="Album",
        year=2025,
        cover=cover,
    )
    saved_cover = project / presentation.cover_path
    saved_cover.write_bytes(b"tampered")

    with pytest.raises(ValueError, match="no longer matches"):
        load_build_presentation(project)


def test_cover_must_be_png_or_jpeg(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    cover = tmp_path / "cover.gif"
    cover.write_bytes(b"gif")

    with pytest.raises(ValueError, match="PNG or JPEG"):
        save_build_presentation(project, album_name="Album", year=2025, cover=cover)
