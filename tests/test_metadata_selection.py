from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator.metadata_providers import (
    MetadataCandidate,
    MetadataIdentificationReport,
    SelectedMetadata,
    select_project_metadata,
)


def _report(path: Path) -> Path:
    report = MetadataIdentificationReport(
        query_artist="Example Artist",
        query_title="Example Song",
        query_duration_seconds=180.0,
        request_url="https://musicbrainz.org/ws/2/recording/?query=test&fmt=json&limit=5",
        cache_key="abc123",
        candidates=[
            MetadataCandidate(
                recording_id="first",
                title="Example Song",
                artist_credit="Example Artist",
                provider_score=0.98,
                duration_ms=180000,
                duration_delta_seconds=0.0,
                first_release_date="2001-02-03",
                release_titles=["Example Album"],
                confidence=0.985,
            ),
            MetadataCandidate(
                recording_id="second",
                title="Example Song (Live)",
                artist_credit="Example Artist",
                provider_score=0.92,
                duration_ms=190000,
                duration_delta_seconds=10.0,
                confidence=0.8,
            ),
        ],
    )
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return path


def test_selection_creates_separate_reviewed_artifact(tmp_path: Path) -> None:
    project = tmp_path / "project"
    metadata = project / "metadata"
    metadata.mkdir(parents=True)
    report_path = _report(metadata / "musicbrainz-abc123.json")

    output = select_project_metadata(project, report_path, index=0)
    selected = SelectedMetadata.model_validate_json(output.read_text(encoding="utf-8"))

    assert output == metadata / "selected.json"
    assert selected.source_report == "metadata/musicbrainz-abc123.json"
    assert selected.selected_index == 0
    assert selected.candidate.recording_id == "first"
    assert selected.candidate.release_titles == ["Example Album"]


def test_selection_rejects_out_of_range_candidate(tmp_path: Path) -> None:
    project = tmp_path / "project"
    metadata = project / "metadata"
    metadata.mkdir(parents=True)
    report_path = _report(metadata / "musicbrainz-abc123.json")

    with pytest.raises(IndexError, match="out of range"):
        select_project_metadata(project, report_path, index=4)


def test_selection_rejects_report_outside_project_metadata(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "metadata").mkdir(parents=True)
    external = tmp_path / "external.json"
    _report(external)

    with pytest.raises(ValueError, match="beneath the project's metadata directory"):
        select_project_metadata(project, external, index=0)
