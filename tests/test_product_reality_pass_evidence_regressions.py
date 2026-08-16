from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.product_reality import (
    add_product_reality_observation,
    finish_product_reality_session,
    load_active_product_reality_session,
    product_reality_pass_evidence_gaps,
    start_product_reality_session,
    start_product_reality_stage,
    stop_product_reality_stage,
)
from rocksmith_cdlc_generator.score_source import ProjectScoreSource, ScoreTrackCandidate


def _project(tmp_path: Path, *, with_score: bool = False) -> Path:
    project = tmp_path / "song"
    project.mkdir()
    ProjectManifest(
        project_name="reality-regression",
        title="Reality Regression",
        arrangement_instruments=["bass", "lead", "rhythm"],
        source_original_path="C:/private/song.wav",
        source_project_path="audio/source.wav",
        source_sha256="a" * 64,
        source_metadata=AudioMetadata(
            duration_seconds=240.0,
            sample_rate_hz=48000,
            channels=2,
            codec_name="pcm_s16le",
            format_name="wav",
        ),
    ).save(project)
    if with_score:
        _write_score(project, "b" * 64)
    return project


def _write_score(project: Path, sha: str) -> None:
    ProjectScoreSource(
        source_filename="score.gp5",
        source_sha256=sha,
        source_format="gp5",
        imported_relative_path="sources/score/score.gp5",
        tracks=[
            ScoreTrackCandidate(
                source_track_index=0,
                name="Bass",
                instrument_hint="bass",
                note_count=10,
            )
        ],
    ).write_json(project / "sources" / "score" / "source.json")


def _record_positive_baseline(project: Path, start: datetime) -> None:
    start_product_reality_stage(
        project,
        name="arrangement review",
        counts_as_editing=True,
        started_at=start + timedelta(minutes=1),
    )
    stop_product_reality_stage(project, completed_at=start + timedelta(minutes=2))
    add_product_reality_observation(
        project,
        area="preview",
        severity="note",
        text="Preview remained responsive.",
        recorded_at=start + timedelta(minutes=3),
    )


def test_pass_refreshes_score_registered_after_session_start(tmp_path: Path) -> None:
    project = _project(tmp_path, with_score=False)
    start = datetime(2026, 8, 16, 8, 0, tzinfo=timezone.utc)
    session = start_product_reality_session(
        project,
        packaged_build_id="windows-472",
        started_at=start,
    )
    assert session.score_sha256 is None

    _write_score(project, "c" * 64)
    _record_positive_baseline(project, start)

    completed, _json_path, _markdown_path = finish_product_reality_session(
        project,
        result="pass",
        reason="Complete baseline evidence recorded.",
        completed_at=start + timedelta(minutes=4),
    )

    assert completed.score_sha256 == "c" * 64
    assert completed.score_format == "gp5"


def test_pass_refreshes_replaced_score_identity(tmp_path: Path) -> None:
    project = _project(tmp_path, with_score=True)
    start = datetime(2026, 8, 16, 8, 0, tzinfo=timezone.utc)
    session = start_product_reality_session(
        project,
        packaged_build_id="windows-472",
        started_at=start,
    )
    assert session.score_sha256 == "b" * 64

    _write_score(project, "d" * 64)
    _record_positive_baseline(project, start)

    completed, _json_path, _markdown_path = finish_product_reality_session(
        project,
        result="pass",
        reason="Complete baseline evidence recorded after score replacement.",
        completed_at=start + timedelta(minutes=4),
    )

    assert completed.score_sha256 == "d" * 64


def test_zero_second_stage_does_not_satisfy_pass_timing_floor(tmp_path: Path) -> None:
    project = _project(tmp_path, with_score=True)
    start = datetime(2026, 8, 16, 8, 0, tzinfo=timezone.utc)
    start_product_reality_session(
        project,
        packaged_build_id="windows-472",
        started_at=start,
    )
    start_product_reality_stage(
        project,
        name="instant review",
        counts_as_editing=True,
        started_at=start + timedelta(minutes=1),
    )
    session = stop_product_reality_stage(
        project,
        completed_at=start + timedelta(minutes=1),
    )
    session = add_product_reality_observation(
        project,
        area="preview",
        severity="note",
        text="No issue observed.",
        recorded_at=start + timedelta(minutes=2),
    )

    gaps = product_reality_pass_evidence_gaps(session)
    assert "completed workflow stage timing" in gaps
    assert "measured human editing interval" in gaps

    with pytest.raises(ValueError, match="PASS requires baseline evidence"):
        finish_product_reality_session(
            project,
            result="pass",
            reason="Should not pass with zero measured time.",
        )
    assert load_active_product_reality_session(project) is not None
