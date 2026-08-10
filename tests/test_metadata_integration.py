from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator.metadata_integration import resolve_build_metadata
from rocksmith_cdlc_generator.metadata_providers import MetadataCandidate, SelectedMetadata


def _write_selected(
    project: Path,
    *,
    release_titles: list[str],
    first_release_date: str | None,
) -> None:
    metadata = project / "metadata"
    metadata.mkdir(parents=True)
    selected = SelectedMetadata(
        provider="musicbrainz",
        source_report="metadata/musicbrainz-test.json",
        selected_index=0,
        candidate=MetadataCandidate(
            recording_id="recording-id",
            title="Song",
            artist_credit="Artist",
            provider_score=1.0,
            confidence=1.0,
            release_titles=release_titles,
            first_release_date=first_release_date,
        ),
    )
    (metadata / "selected.json").write_text(selected.model_dump_json(indent=2), encoding="utf-8")


def test_selected_metadata_can_supply_unambiguous_album_and_year(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_selected(project, release_titles=["Album"], first_release_date="2004-06-01")

    resolved = resolve_build_metadata(project, album_name=None, year=None)

    assert resolved.album_name == "Album"
    assert resolved.year == 2004
    assert resolved.album_source == "selected_metadata"
    assert resolved.year_source == "selected_metadata"
    assert resolved.selected_metadata_path == "metadata/selected.json"


def test_explicit_values_override_selected_metadata(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_selected(project, release_titles=["Provider Album"], first_release_date="2004")

    resolved = resolve_build_metadata(project, album_name="My Album", year=1999)

    assert resolved.album_name == "My Album"
    assert resolved.year == 1999
    assert resolved.album_source == "explicit"
    assert resolved.year_source == "explicit"


def test_ambiguous_release_titles_require_explicit_album(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_selected(
        project,
        release_titles=["Original Album", "Deluxe Edition"],
        first_release_date="2004",
    )

    with pytest.raises(ValueError, match="ambiguous"):
        resolve_build_metadata(project, album_name=None, year=None)


def test_missing_selected_metadata_requires_explicit_values(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    with pytest.raises(ValueError, match="Album name is required"):
        resolve_build_metadata(project, album_name=None, year=None)


def test_invalid_selected_release_date_does_not_invent_year(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_selected(project, release_titles=["Album"], first_release_date="unknown")

    with pytest.raises(ValueError, match="Release year is required"):
        resolve_build_metadata(project, album_name=None, year=None)
