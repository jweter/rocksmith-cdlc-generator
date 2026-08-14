from __future__ import annotations

import json
from pathlib import Path

import pytest

from rocksmith_cdlc_generator.metadata_providers import MetadataCandidate, SelectedMetadata
from rocksmith_cdlc_generator.recording_context import (
    ReviewedRecordingContext,
    build_reviewed_recording_context,
    load_reviewed_recording_context,
)
from rocksmith_cdlc_generator.reference_selection import select_reference_source
from rocksmith_cdlc_generator.reference_sources import add_reference_source


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text("{}", encoding="utf-8")
    return project


def _select_reference(project: Path) -> None:
    url = "https://www.youtube.com/watch?v=abc123"
    add_reference_source(
        project,
        url=url,
        display_name="Official studio upload",
        provider="YouTube",
        version_hint="2011 remaster",
    )
    select_reference_source(project, url=url, confirmation_note="Confirmed intended version")


def _write_selected_metadata(project: Path) -> None:
    selected = SelectedMetadata(
        provider="musicbrainz",
        source_report="metadata/musicbrainz-test.json",
        selected_index=0,
        candidate=MetadataCandidate(
            recording_id="recording-id",
            title="Example Song",
            artist_credit="Example Artist",
            provider_score=1.0,
            duration_ms=180000,
            confidence=0.99,
        ),
    )
    metadata = project / "metadata"
    metadata.mkdir(parents=True, exist_ok=True)
    (metadata / "selected.json").write_text(selected.model_dump_json(indent=2), encoding="utf-8")


def test_context_requires_explicit_human_reference_selection(tmp_path: Path) -> None:
    project = _project(tmp_path)

    with pytest.raises(ValueError, match="human-confirmed reference selection"):
        build_reviewed_recording_context(project)


def test_context_snapshots_reference_and_selected_catalog_metadata(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _select_reference(project)
    _write_selected_metadata(project)

    output = build_reviewed_recording_context(project)
    context = ReviewedRecordingContext.model_validate_json(output.read_text(encoding="utf-8"))

    assert output == project / "metadata" / "recording_context.json"
    assert context.reference_selection.human_confirmed is True
    assert context.reference_selection.provider == "YouTube"
    assert context.reference_selection.version_hint == "2011 remaster"
    assert context.selected_metadata is not None
    assert context.selected_metadata.candidate.recording_id == "recording-id"


def test_context_allows_reference_only_handoff_before_catalog_selection(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _select_reference(project)

    output = build_reviewed_recording_context(project)
    context = load_reviewed_recording_context(project)

    assert output.is_file()
    assert context is not None
    assert context.selected_metadata is None
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert "reference_selection" in payload
    assert "selected_metadata" in payload
