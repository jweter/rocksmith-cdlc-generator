from pathlib import Path

from rocksmith_cdlc_generator.reconciliation import ReconciledBassChart
from rocksmith_cdlc_generator.score_fanout import _invalidate_stale_bass_derivatives
from rocksmith_cdlc_generator.score_source import (
    ArrangementRole,
    ProjectScoreSource,
    ScoreArrangementMapping,
    ScoreTrackCandidate,
)


def _score(*, bass_track: int = 2) -> ProjectScoreSource:
    return ProjectScoreSource(
        source_filename="song.gp5",
        source_sha256="a" * 64,
        source_format="gp5",
        imported_relative_path="sources/score/original/song.gp5",
        tracks=[
            ScoreTrackCandidate(source_track_index=1, name="Legacy Bass", note_count=10),
            ScoreTrackCandidate(source_track_index=2, name="Bass", note_count=10),
        ],
        arrangement_mappings=[
            ScoreArrangementMapping(
                role=ArrangementRole.bass,
                source_track_index=bass_track,
                confidence=1.0,
                basis=["human confirmed"],
                human_confirmed=True,
            )
        ],
    )


def _write_derivatives(project: Path, *, source_sha256: str, track_index: int) -> None:
    chart = ReconciledBassChart(
        source_sha256=source_sha256,
        track_index=track_index,
        onset_tolerance_seconds=0.15,
        verified_onset_tolerance_seconds=0.08,
        notes=[],
    )
    chart_path = project / "charts" / "bass_reconciled.json"
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    chart_path.write_text(chart.model_dump_json(indent=2), encoding="utf-8")

    for relative in (
        "charts/bass_mapped.json",
        "review/source_disagreements.json",
        "review/validation_report.json",
    ):
        path = project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("stale", encoding="utf-8")


def _bass_mapping(score: ProjectScoreSource) -> list[ScoreArrangementMapping]:
    mapping = score.mapping_for(ArrangementRole.bass)
    assert mapping is not None
    return [mapping]


def test_changed_bass_authority_invalidates_old_derivatives(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    score = _score(bass_track=2)
    _write_derivatives(project, source_sha256="b" * 64, track_index=1)

    _invalidate_stale_bass_derivatives(project, score=score, mappings=_bass_mapping(score))

    for relative in (
        "charts/bass_reconciled.json",
        "charts/bass_mapped.json",
        "review/source_disagreements.json",
        "review/validation_report.json",
    ):
        assert not (project / relative).exists()


def test_same_score_and_track_preserve_current_derivatives(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    score = _score(bass_track=2)
    _write_derivatives(project, source_sha256=score.source_sha256, track_index=2)

    _invalidate_stale_bass_derivatives(project, score=score, mappings=_bass_mapping(score))

    for relative in (
        "charts/bass_reconciled.json",
        "charts/bass_mapped.json",
        "review/source_disagreements.json",
        "review/validation_report.json",
    ):
        assert (project / relative).is_file()


def test_bass_fanout_without_reconciliation_drops_unbound_downstream_files(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    score = _score(bass_track=2)
    for relative in ("charts/bass_mapped.json", "review/validation_report.json"):
        path = project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("legacy", encoding="utf-8")

    _invalidate_stale_bass_derivatives(project, score=score, mappings=_bass_mapping(score))

    assert not (project / "charts" / "bass_mapped.json").exists()
    assert not (project / "review" / "validation_report.json").exists()


def test_non_bass_fanout_does_not_touch_bass_derivatives(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    score = _score(bass_track=2)
    _write_derivatives(project, source_sha256="b" * 64, track_index=1)
    lead = ScoreArrangementMapping(
        role=ArrangementRole.lead,
        source_track_index=1,
        confidence=1.0,
        human_confirmed=True,
    )

    _invalidate_stale_bass_derivatives(project, score=score, mappings=[lead])

    assert (project / "charts" / "bass_reconciled.json").is_file()
    assert (project / "charts" / "bass_mapped.json").is_file()
