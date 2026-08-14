from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator.metadata_integration import resolve_build_metadata
from rocksmith_cdlc_generator.metadata_providers import MetadataCandidate, SelectedMetadata
from rocksmith_cdlc_generator.recording_context import ReviewedRecordingContext
from rocksmith_cdlc_generator.reference_selection import ReferenceSelection


def _selected(
    *,
    release_titles: list[str],
    first_release_date: str | None,
) -> SelectedMetadata:
    return SelectedMetadata(
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


def _write_context(
    project: Path,
    *,
    release_titles: list[str],
    first_release_date: str | None,
) -> None:
    metadata = project / "metadata"
    metadata.mkdir(parents=True, exist_ok=True)
    context = ReviewedRecordingContext(
        reference_selection=ReferenceSelection(
            reference_url="https://www.youtube.com/watch?v=abc123",
            display_name="Official studio upload",
            provider="YouTube",
            version_hint="album version",
        ),
        selected_metadata=_selected(
            release_titles=release_titles,
            first_release_date=first_release_date,
        ),
    )
    (metadata / "recording_context.json").write_text(
        context.model_dump_json(indent=2), encoding="utf-8"
    )


def test_reviewed_context_can_supply_unambiguous_album_and_year(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_context(project, release_titles=["Album"], first_release_date="2004-06-01")

    resolved = resolve_build_metadata(project, album_name=None, year=None)

    assert resolved.album_name == "Album"
    assert resolved.year == 2004
    assert resolved.album_source == "reviewed_recording_context"
    assert resolved.year_source == "reviewed_recording_context"
    assert resolved.selected_metadata_path == "metadata/selected.json"
    assert resolved.recording_context_path == "metadata/recording_context.json"


def test_explicit_values_do_not_require_reviewed_context(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    resolved = resolve_build_metadata(project, album_name="My Album", year=1999)

    assert resolved.album_name == "My Album"
    assert resolved.year == 1999
    assert resolved.album_source == "explicit"
    assert resolved.year_source == "explicit"
    assert resolved.recording_context_path is None


def test_selected_json_alone_cannot_silently_supply_build_metadata(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    metadata = project / "metadata"
    metadata.mkdir()
    (metadata / "selected.json").write_text(
        _selected(release_titles=["Unreviewed Album"], first_release_date="2005").model_dump_json(indent=2),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="rebuild reviewed recording context"):
        resolve_build_metadata(project, album_name=None, year=None)


def test_context_snapshot_is_stable_when_selected_json_changes(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_context(project, release_titles=["Reviewed Album"], first_release_date="2004")
    metadata = project / "metadata"
    (metadata / "selected.json").write_text(
        _selected(release_titles=["Later Unreviewed Album"], first_release_date="2010").model_dump_json(indent=2),
        encoding="utf-8",
    )

    resolved = resolve_build_metadata(project, album_name=None, year=None)

    assert resolved.album_name == "Reviewed Album"
    assert resolved.year == 2004


def test_ambiguous_reviewed_release_titles_require_explicit_album(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_context(
        project,
        release_titles=["Original Album", "Deluxe Edition"],
        first_release_date="2004",
    )

    with pytest.raises(ValueError, match="ambiguous"):
        resolve_build_metadata(project, album_name=None, year=None)


def test_invalid_reviewed_release_date_does_not_invent_year(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_context(project, release_titles=["Album"], first_release_date="unknown")

    with pytest.raises(ValueError, match="Release year is required"):
        resolve_build_metadata(project, album_name=None, year=None)
