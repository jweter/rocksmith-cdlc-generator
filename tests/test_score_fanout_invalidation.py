from pathlib import Path

from rocksmith_cdlc_generator.reconciliation import ReconciledBassChart, SourceDisagreementReport
from rocksmith_cdlc_generator.score_fanout import _invalidate_stale_bass_derivatives
from rocksmith_cdlc_generator.score_source import (
    ArrangementRole,
    ProjectScoreSource,
    ScoreArrangementMapping,
    ScoreTrackCandidate,
)


_UNBOUND_DOWNSTREAM = (
    "charts/bass_mapped.json",
    "review/bass_mapping_review.json",
    "review/validation_report.json",
    "review/flags.json",
    "review/summary.md",
    "eof/arr_bass_RS2.xml",
    "eof/export_manifest.json",
    "eof/README.md",
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


_CONTENT_SHA = "c" * 64


def _write_derivatives(
    project: Path,
    *,
    source_sha256: str,
    track_index: int,
    content_sha256: str | None = _CONTENT_SHA,
) -> None:
    chart = ReconciledBassChart(
        source_sha256=source_sha256,
        track_index=track_index,
        source_content_sha256=content_sha256,
        onset_tolerance_seconds=0.15,
        verified_onset_tolerance_seconds=0.08,
        notes=[],
    )
    chart_path = project / "charts" / "bass_reconciled.json"
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    chart_path.write_text(chart.model_dump_json(indent=2), encoding="utf-8")

    review = SourceDisagreementReport(
        source_sha256=source_sha256,
        track_index=track_index,
        source_content_sha256=content_sha256,
        disagreements=[],
    )
    review_path = project / "review" / "source_disagreements.json"
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(review.model_dump_json(indent=2), encoding="utf-8")

    for relative in _UNBOUND_DOWNSTREAM:
        path = project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("stale", encoding="utf-8")

    build_dir = project / "build" / "dlcbuilder"
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "song.rs2dlc").write_text("stale", encoding="utf-8")
    (build_dir / "metadata_resolution.json").write_text("stale", encoding="utf-8")
    (build_dir / "preview.wav").write_bytes(b"stale")


def _bass_mapping(score: ProjectScoreSource) -> list[ScoreArrangementMapping]:
    mapping = score.mapping_for(ArrangementRole.bass)
    assert mapping is not None
    return [mapping]


def test_changed_bass_authority_invalidates_old_derivatives(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    score = _score(bass_track=2)
    _write_derivatives(project, source_sha256="b" * 64, track_index=1)

    _invalidate_stale_bass_derivatives(
        project, score=score, mappings=_bass_mapping(score), bass_output_content_sha256=_CONTENT_SHA
    )

    for relative in (
        "charts/bass_reconciled.json",
        "review/source_disagreements.json",
        *_UNBOUND_DOWNSTREAM,
    ):
        assert not (project / relative).exists()
    assert not (project / "build" / "dlcbuilder").exists()


def test_matching_reconciliation_survives_but_unbound_outputs_do_not(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    score = _score(bass_track=2)
    _write_derivatives(project, source_sha256=score.source_sha256, track_index=2)

    _invalidate_stale_bass_derivatives(
        project, score=score, mappings=_bass_mapping(score), bass_output_content_sha256=_CONTENT_SHA
    )

    assert (project / "charts" / "bass_reconciled.json").is_file()
    assert (project / "review" / "source_disagreements.json").is_file()
    for relative in _UNBOUND_DOWNSTREAM:
        assert not (project / relative).exists()
    assert not (project / "build" / "dlcbuilder").exists()


def test_mismatched_disagreement_review_is_removed_even_when_reconciliation_matches(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    score = _score(bass_track=2)
    _write_derivatives(project, source_sha256=score.source_sha256, track_index=2)
    bad_review = SourceDisagreementReport(
        source_sha256="b" * 64,
        track_index=1,
        source_content_sha256=_CONTENT_SHA,
        disagreements=[],
    )
    review_path = project / "review" / "source_disagreements.json"
    review_path.write_text(bad_review.model_dump_json(indent=2), encoding="utf-8")

    _invalidate_stale_bass_derivatives(
        project, score=score, mappings=_bass_mapping(score), bass_output_content_sha256=_CONTENT_SHA
    )

    assert (project / "charts" / "bass_reconciled.json").is_file()
    assert not review_path.exists()


def test_bass_fanout_without_reconciliation_drops_all_unbound_outputs(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    score = _score(bass_track=2)
    for relative in _UNBOUND_DOWNSTREAM:
        path = project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("legacy", encoding="utf-8")
    build_dir = project / "build" / "dlcbuilder"
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "legacy.rs2dlc").write_text("legacy", encoding="utf-8")

    _invalidate_stale_bass_derivatives(
        project, score=score, mappings=_bass_mapping(score), bass_output_content_sha256=_CONTENT_SHA
    )

    for relative in _UNBOUND_DOWNSTREAM:
        assert not (project / relative).exists()
    assert not build_dir.exists()


def test_composed_content_change_invalidates_derivatives_even_when_score_and_track_match(
    tmp_path: Path,
) -> None:
    """Trap 2 (issue #232 design notes): adding a second composed source track leaves the
    confirmed *primary* track index unchanged, so ``(score_sha256, track_index)`` alone
    would incorrectly treat a reconciliation built from the old, narrower composed note
    stream as still current. Binding staleness to the fan-out output's own content hash
    closes that gap.
    """

    project = tmp_path / "song"
    project.mkdir()
    score = _score(bass_track=2)
    _write_derivatives(
        project, source_sha256=score.source_sha256, track_index=2, content_sha256=_CONTENT_SHA
    )

    _invalidate_stale_bass_derivatives(
        project,
        score=score,
        mappings=_bass_mapping(score),
        bass_output_content_sha256="d" * 64,
    )

    assert not (project / "charts" / "bass_reconciled.json").exists()
    assert not (project / "review" / "source_disagreements.json").exists()


def test_legacy_reconciliation_without_a_content_hash_is_treated_as_stale(tmp_path: Path) -> None:
    """A reconciliation persisted before ``source_content_sha256`` existed cannot prove it
    matches the current fan-out output's content, so it is conservatively invalidated
    rather than assumed to still be current on ``(score_sha256, track_index)`` alone.
    """

    project = tmp_path / "song"
    project.mkdir()
    score = _score(bass_track=2)
    _write_derivatives(
        project, source_sha256=score.source_sha256, track_index=2, content_sha256=None
    )

    _invalidate_stale_bass_derivatives(
        project,
        score=score,
        mappings=_bass_mapping(score),
        bass_output_content_sha256=_CONTENT_SHA,
    )

    assert not (project / "charts" / "bass_reconciled.json").exists()
    assert not (project / "review" / "source_disagreements.json").exists()


def test_non_bass_fanout_does_not_touch_bass_derivatives_or_build_state(tmp_path: Path) -> None:
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
    assert (project / "review" / "source_disagreements.json").is_file()
    for relative in _UNBOUND_DOWNSTREAM:
        assert (project / relative).is_file()
    assert (project / "build" / "dlcbuilder" / "song.rs2dlc").is_file()
