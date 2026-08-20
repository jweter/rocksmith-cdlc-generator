import hashlib
from pathlib import Path

from rocksmith_cdlc_generator.reconciliation import ReconciledBassChart, SourceDisagreementReport
from rocksmith_cdlc_generator.score_fanout import _invalidate_stale_bass_derivatives
from rocksmith_cdlc_generator.score_role_composition import (
    ScoreRoleCompositionPlan,
    ScoreRoleCompositionSelection,
)
from rocksmith_cdlc_generator.score_role_composition_fanout_review import (
    SCORE_ROLE_COMPOSITION_FANOUT_PATH,
    ComposedTrackOutput,
    RoleCompositionFanoutRecord,
    ScoreRoleCompositionFanoutReviewLayer,
)
from rocksmith_cdlc_generator.score_role_composition_review import SCORE_ROLE_COMPOSITION_PATH
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

    review = SourceDisagreementReport(
        source_sha256=source_sha256,
        track_index=track_index,
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

    _invalidate_stale_bass_derivatives(project, score=score, mappings=_bass_mapping(score))

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

    _invalidate_stale_bass_derivatives(project, score=score, mappings=_bass_mapping(score))

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
        disagreements=[],
    )
    review_path = project / "review" / "source_disagreements.json"
    review_path.write_text(bad_review.model_dump_json(indent=2), encoding="utf-8")

    _invalidate_stale_bass_derivatives(project, score=score, mappings=_bass_mapping(score))

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

    _invalidate_stale_bass_derivatives(project, score=score, mappings=_bass_mapping(score))

    for relative in _UNBOUND_DOWNSTREAM:
        assert not (project / relative).exists()
    assert not build_dir.exists()


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


# --- Trap 2 regression: (score_sha256, track_index)-only identity cannot see a score
# role composition selection change that leaves the confirmed primary track index
# unchanged. See docs/score-role-composition-fanout-review.md.


def _write_composition_plan(project: Path, score: ProjectScoreSource, *, bass_track_indices: list[int]) -> None:
    plan = ScoreRoleCompositionPlan(
        score_sha256=score.source_sha256,
        score_format=score.source_format,
        selections=[
            ScoreRoleCompositionSelection(role=ArrangementRole.bass, source_track_indices=bass_track_indices)
        ],
    )
    plan_path = project / SCORE_ROLE_COMPOSITION_PATH
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(plan.model_dump_json(indent=2) + "\n", encoding="utf-8")


def test_composition_selecting_additional_bass_tracks_invalidates_a_matching_reconciliation(
    tmp_path: Path,
) -> None:
    """Under the old (score_sha256, track_index)-only key this reconciliation would have
    been wrongly kept: nothing about the confirmed primary track (2) changed. The fix
    must see that the human has since selected a second source track for Bass via score
    role composition and invalidate the reconciliation built before that happened.
    """

    project = tmp_path / "song"
    project.mkdir()
    score = _score(bass_track=2)
    _write_derivatives(project, source_sha256=score.source_sha256, track_index=2)

    # Sanity check: with no composition selection recorded yet, the reconciliation is
    # (still correctly) treated as current -- unchanged single-track behavior.
    _invalidate_stale_bass_derivatives(project, score=score, mappings=_bass_mapping(score))
    assert (project / "charts" / "bass_reconciled.json").is_file()
    assert (project / "review" / "source_disagreements.json").is_file()

    # A human now composes Bass from two source tracks (primary track 2 plus track 1).
    # The confirmed primary mapping (track 2) never changes.
    _write_composition_plan(project, score, bass_track_indices=[2, 1])

    _invalidate_stale_bass_derivatives(project, score=score, mappings=_bass_mapping(score))

    assert not (project / "charts" / "bass_reconciled.json").exists()
    assert not (project / "review" / "source_disagreements.json").exists()


def _write_bass_project(tmp_path: Path) -> tuple[Path, ProjectScoreSource]:
    project = tmp_path / "song"
    project.mkdir()
    (project / "project.json").write_text("{}", encoding="utf-8")
    stored_score = project / "sources" / "score" / "original" / "song.gp5"
    stored_score.parent.mkdir(parents=True, exist_ok=True)
    stored_score.write_bytes(b"complete-score")
    score_sha = hashlib.sha256(stored_score.read_bytes()).hexdigest()
    score = ProjectScoreSource(
        source_filename="song.gp5",
        source_sha256=score_sha,
        source_format="gp5",
        imported_relative_path="sources/score/original/song.gp5",
        tracks=[
            ScoreTrackCandidate(source_track_index=i, name=f"Track {i}", note_count=10)
            for i in (1, 2, 3)
        ],
        arrangement_mappings=[
            ScoreArrangementMapping(
                role=ArrangementRole.bass,
                source_track_index=2,
                confidence=1.0,
                basis=["human confirmed"],
                human_confirmed=True,
            )
        ],
    )
    score.write_json(project / "sources" / "score" / "source.json")
    return project, score


def _write_bass_composition_fanout_record(
    project: Path, score: ProjectScoreSource, *, track_indices: list[int]
) -> RoleCompositionFanoutRecord:
    track_outputs: list[ComposedTrackOutput] = []
    for track_index in track_indices:
        content = f"bass-track-{track_index}-content".encode("utf-8")
        output_path = (
            project
            / "sources"
            / "imported"
            / "composition"
            / f"bass-track{track_index}-{score.source_sha256[:12]}.json"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(content)
        track_outputs.append(
            ComposedTrackOutput(
                source_track_index=track_index,
                output_json=output_path.relative_to(project).as_posix(),
                output_sha256=hashlib.sha256(content).hexdigest(),
            )
        )
    record = RoleCompositionFanoutRecord(
        role=ArrangementRole.bass,
        score_sha256=score.source_sha256,
        score_format=score.source_format,
        source_track_indices=track_indices,
        track_outputs=track_outputs,
        notes=[],
    )
    layer = ScoreRoleCompositionFanoutReviewLayer(
        score_sha256=score.source_sha256, score_format=score.source_format, records=[record]
    )
    layer_path = project / SCORE_ROLE_COMPOSITION_FANOUT_PATH
    layer_path.parent.mkdir(parents=True, exist_ok=True)
    layer_path.write_text(layer.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return record


def _record_content_sha256(record: RoleCompositionFanoutRecord) -> str:
    return hashlib.sha256(record.model_dump_json().encode("utf-8")).hexdigest()


def test_growing_a_composed_bass_selection_invalidates_the_older_smaller_composed_reconciliation(
    tmp_path: Path,
) -> None:
    """A reconciliation correctly bound to a 2-track composed fan-out record must go
    stale once the human adds a third source track to the composition, even though the
    persisted fan-out record has not been recomposed yet and the confirmed primary track
    index (2) never changes.
    """

    project, score = _write_bass_project(tmp_path)
    bass = [score.mapping_for(ArrangementRole.bass)]
    assert bass[0] is not None

    _write_composition_plan(project, score, bass_track_indices=[2, 1])
    record = _write_bass_composition_fanout_record(project, score, track_indices=[2, 1])

    chart = ReconciledBassChart(
        source_sha256=score.source_sha256,
        track_index=2,
        onset_tolerance_seconds=0.15,
        verified_onset_tolerance_seconds=0.08,
        notes=[],
        composed_source_track_indices=[2, 1],
        composed_fanout_record_sha256=_record_content_sha256(record),
    )
    chart_path = project / "charts" / "bass_reconciled.json"
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    chart_path.write_text(chart.model_dump_json(indent=2), encoding="utf-8")

    review = SourceDisagreementReport(
        source_sha256=score.source_sha256,
        track_index=2,
        disagreements=[],
        composed_source_track_indices=[2, 1],
        composed_fanout_record_sha256=_record_content_sha256(record),
    )
    review_path = project / "review" / "source_disagreements.json"
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(review.model_dump_json(indent=2), encoding="utf-8")

    # Unchanged composition: the reconciliation still matches the current fan-out
    # content identity and survives.
    _invalidate_stale_bass_derivatives(project, score=score, mappings=bass)
    assert chart_path.is_file()
    assert review_path.is_file()

    # The human grows the composition to three tracks. The persisted fan-out record is
    # not recomposed yet, so it is now stale for the new selection; the reconciliation
    # built from the older, smaller two-track composed stream must go stale too.
    _write_composition_plan(project, score, bass_track_indices=[2, 1, 3])

    _invalidate_stale_bass_derivatives(project, score=score, mappings=bass)

    assert not chart_path.exists()
    assert not review_path.exists()
