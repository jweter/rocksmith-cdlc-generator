from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator.alignment import AlignmentAnchor, AlignmentRegion, AlignmentReport
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.score_fanout import ScoreFanoutEntry, ScoreFanoutManifest
from rocksmith_cdlc_generator.score_preview import load_score_fanout_preview_snapshot
from rocksmith_cdlc_generator.score_role_composition import (
    ScoreRoleCompositionPlan,
    ScoreRoleCompositionSelection,
)
from rocksmith_cdlc_generator.score_role_composition_review import SCORE_ROLE_COMPOSITION_PATH
from rocksmith_cdlc_generator.score_source import (
    ArrangementRole,
    ProjectScoreSource,
    ScoreArrangementMapping,
    ScoreTrackCandidate,
)
from rocksmith_cdlc_generator.song_preview import build_preview_review_queue, build_preview_timeline_window
from rocksmith_cdlc_generator.source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTrack,
    SourceTrustClass,
)


def _build_project(tmp_path: Path) -> Path:
    project = tmp_path / "song"
    (project / "sources" / "score").mkdir(parents=True)
    (project / "sources" / "imported").mkdir(parents=True)
    project.joinpath("project.json").write_text("{}", encoding="utf-8")

    stored = project / "sources" / "score" / "complete.gp5"
    stored.write_bytes(b"synthetic-score-fixture")
    score_sha = sha256_file(stored)
    roles = [ArrangementRole.bass, ArrangementRole.lead, ArrangementRole.rhythm]
    score = ProjectScoreSource(
        source_filename="complete.gp5",
        source_sha256=score_sha,
        source_format="gp5",
        imported_relative_path="sources/score/complete.gp5",
        tracks=[
            ScoreTrackCandidate(source_track_index=index, name=role.value.title(), instrument_hint=role.value, note_count=1)
            for index, role in enumerate(roles)
        ],
        arrangement_mappings=[
            ScoreArrangementMapping(
                role=role,
                source_track_index=index,
                confidence=0.95,
                basis=["fixture"],
                human_confirmed=True,
            )
            for index, role in enumerate(roles)
        ],
    )
    score.write_json(project / "sources" / "score" / "source.json")

    entries: list[ScoreFanoutEntry] = []
    for index, role in enumerate(roles):
        output = project / "sources" / "imported" / f"{role.value}.json"
        ImportedSource(
            provenance=SourceProvenance(
                source_type="guitarpro",
                source_filename="complete.gp5",
                source_sha256=score_sha,
                importer="fixture",
                importer_version="1",
            ),
            beat_times_seconds=[0.0, 0.5, 1.0, 1.5],
            tracks=[
                SourceTrack(
                    source_track_index=index,
                    name=role.value.title(),
                    instrument=role.value,
                    tuning_midi=[40, 45, 50, 55] if role is ArrangementRole.bass else [40, 45, 50, 55, 59, 64],
                    notes=[
                        SourceNoteEvent(
                            start_seconds=0.5 + index * 0.1,
                            duration_seconds=0.25,
                            midi=40 + index,
                            note_name="E2",
                            string_index=0,
                            fret=index,
                            import_confidence=0.7 + index * 0.1,
                            trust_class=SourceTrustClass.symbolic_unverified,
                            review_required=(role is not ArrangementRole.bass),
                        )
                    ],
                )
            ],
        ).write_json(output)
        entries.append(
            ScoreFanoutEntry(
                role=role,
                source_track_index=index,
                output_json=output.relative_to(project).as_posix(),
            )
        )

    manifest = ScoreFanoutManifest(
        score_source_sha256=score_sha,
        score_source_format="gp5",
        arrangements=entries,
    )
    (project / "sources" / "imported" / f"score-fanout-{score_sha[:12]}.json").write_text(
        manifest.model_dump_json(indent=2), encoding="utf-8"
    )
    return project


def _recording_alignment() -> AlignmentReport:
    return AlignmentReport(
        source_path="fixture.json",
        source_sha256="a" * 64,
        recording_sha256="b" * 64,
        track_index=0,
        audio_beat_start_index=0,
        global_offset_seconds=1.0,
        anchor_stride_beats=4,
        matched_beats=4,
        rms_residual_seconds=0.0,
        median_abs_residual_seconds=0.0,
        max_abs_residual_seconds=0.0,
        confidence=1.0,
        anchors=[
            AlignmentAnchor(
                source_time_seconds=0.0,
                audio_time_seconds=1.0,
                source_beat_index=0,
                audio_beat_index=0,
                confidence=1.0,
            ),
            AlignmentAnchor(
                source_time_seconds=2.0,
                audio_time_seconds=4.0,
                source_beat_index=3,
                audio_beat_index=3,
                confidence=1.0,
            ),
        ],
        regions=[
            AlignmentRegion(
                source_start_seconds=0.0,
                source_end_seconds=2.0,
                audio_start_seconds=1.0,
                audio_end_seconds=4.0,
                rms_residual_seconds=0.0,
                max_abs_residual_seconds=0.0,
                confidence=1.0,
            )
        ],
    )


def test_score_fanout_preview_supports_all_three_roles_on_recording_clock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _build_project(tmp_path)
    report = _recording_alignment()
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.score_preview.alignment_for_role",
        lambda _project, _role: report,
    )
    snapshot = load_score_fanout_preview_snapshot(project)

    assert {arr.instrument for arr in snapshot.arrangements} == {"bass", "lead", "rhythm"}
    assert snapshot.beat_times_seconds == pytest.approx([1.0, 1.75, 2.5, 3.25])
    assert sum(arr.note_count for arr in snapshot.arrangements) == 3

    bass = next(arr for arr in snapshot.arrangements if arr.instrument == "bass")
    assert bass.notes[0].start_seconds == pytest.approx(1.75)
    assert bass.notes[0].duration_seconds == pytest.approx(0.375)

    window = build_preview_timeline_window(snapshot, 1.7, 2.4)
    assert len(window.lanes) == 3
    assert sum(len(lane.notes) for lane in window.lanes) == 3

    queue = build_preview_review_queue(snapshot)
    assert [item.instrument for item in queue.items] == ["lead", "rhythm"]
    assert [item.start_seconds for item in queue.items] == pytest.approx([1.9, 2.05])
    assert all(item.string_index == 0 for item in queue.items)


def test_score_fanout_preview_requires_current_shared_timeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _build_project(tmp_path)

    def _missing(_project: Path, _role: ArrangementRole) -> AlignmentReport:
        raise ValueError("shared timeline is not current")

    monkeypatch.setattr("rocksmith_cdlc_generator.score_preview.alignment_for_role", _missing)
    with pytest.raises(ValueError, match="shared timeline is not current"):
        load_score_fanout_preview_snapshot(project)


def test_score_fanout_preview_fails_closed_for_an_unmaterialized_composed_lead_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression test for the score-role-composition-fanout-review.md audit checklist.

    Lead/Rhythm's composed multi-track note stream is materialized only inside
    ``shared_guitar.py``'s chart-build path, never into the score fan-out manifest this
    preview reads. Silently previewing/accepting review decisions against the single
    confirmed-primary-track fan-out output while a multi-track Lead composition is
    selected would leave the additional composed track's notes invisible to this Song
    Workspace surface, with no signal anything was left out.
    """

    project = _build_project(tmp_path)
    report = _recording_alignment()
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.score_preview.alignment_for_role",
        lambda _project, _role: report,
    )

    score_path = project / "sources" / "score" / "source.json"
    score = ProjectScoreSource.read_json(score_path)
    updated = score.model_copy(
        update={
            "tracks": [
                *score.tracks,
                ScoreTrackCandidate(
                    source_track_index=3, name="Alt Lead", instrument_hint="lead", note_count=1
                ),
            ]
        }
    )
    updated.write_json(score_path)

    plan = ScoreRoleCompositionPlan(
        score_sha256=score.source_sha256,
        score_format=score.source_format,
        selections=[
            ScoreRoleCompositionSelection(role=ArrangementRole.lead, source_track_indices=[1, 3]),
        ],
    )
    plan_path = project / SCORE_ROLE_COMPOSITION_PATH
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(plan.model_dump_json(indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="do not yet support a composed multi-track selection"):
        load_score_fanout_preview_snapshot(project)


def test_score_fanout_preview_accepts_a_composed_bass_selection_reflected_in_the_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bass's composed multi-track fan-out is materialized directly into the score fan-out
    manifest (``score_fanout.py``'s ``_materialize_composed_bass_source``), so the
    composed-review gap guard must never fire for Bass even while a multi-track Bass
    composition is selected -- unlike Lead/Rhythm, whose composed materialization the
    manifest never reflects (see the sibling failure-mode test above).
    """

    project = _build_project(tmp_path)
    report = _recording_alignment()
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.score_preview.alignment_for_role",
        lambda _project, _role: report,
    )

    score_path = project / "sources" / "score" / "source.json"
    score = ProjectScoreSource.read_json(score_path)
    updated = score.model_copy(
        update={
            "tracks": [
                *score.tracks,
                ScoreTrackCandidate(
                    source_track_index=3, name="Alt Bass", instrument_hint="bass", note_count=1
                ),
            ]
        }
    )
    updated.write_json(score_path)

    plan = ScoreRoleCompositionPlan(
        score_sha256=score.source_sha256,
        score_format=score.source_format,
        selections=[
            ScoreRoleCompositionSelection(role=ArrangementRole.bass, source_track_indices=[0, 3]),
        ],
    )
    plan_path = project / SCORE_ROLE_COMPOSITION_PATH
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(plan.model_dump_json(indent=2) + "\n", encoding="utf-8")

    # Materialize the composed Bass output at exactly the path score_fanout.py's
    # _materialize_composed_bass_source would write, and point the already-published score
    # fan-out manifest's bass entry at it -- mirroring what a real composed Bass fan-out
    # run leaves behind.
    composed_path = (
        project / "sources" / "imported" / "composition" / f"bass-composed-{score.source_sha256[:12]}.json"
    )
    composed_path.parent.mkdir(parents=True, exist_ok=True)
    original_bass = ImportedSource.read_json(project / "sources" / "imported" / "bass.json")
    original_bass.write_json(composed_path)

    manifest_path = project / "sources" / "imported" / f"score-fanout-{score.source_sha256[:12]}.json"
    manifest = ScoreFanoutManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    updated_manifest = manifest.model_copy(
        update={
            "arrangements": [
                (
                    entry.model_copy(
                        update={"output_json": composed_path.relative_to(project).as_posix()}
                    )
                    if entry.role is ArrangementRole.bass
                    else entry
                )
                for entry in manifest.arrangements
            ]
        }
    )
    manifest_path.write_text(updated_manifest.model_dump_json(indent=2), encoding="utf-8")

    snapshot = load_score_fanout_preview_snapshot(project)
    assert {arr.instrument for arr in snapshot.arrangements} == {"bass", "lead", "rhythm"}


def test_score_fanout_preview_is_unaffected_by_a_single_track_lead_composition_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _build_project(tmp_path)
    report = _recording_alignment()
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.score_preview.alignment_for_role",
        lambda _project, _role: report,
    )
    score = ProjectScoreSource.read_json(project / "sources" / "score" / "source.json")

    plan = ScoreRoleCompositionPlan(
        score_sha256=score.source_sha256,
        score_format=score.source_format,
        selections=[
            ScoreRoleCompositionSelection(role=ArrangementRole.lead, source_track_indices=[1]),
        ],
    )
    plan_path = project / SCORE_ROLE_COMPOSITION_PATH
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(plan.model_dump_json(indent=2) + "\n", encoding="utf-8")

    snapshot = load_score_fanout_preview_snapshot(project)
    assert {arr.instrument for arr in snapshot.arrangements} == {"bass", "lead", "rhythm"}


def test_score_fanout_preview_ignores_a_stale_or_corrupt_composition_plan_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _build_project(tmp_path)
    report = _recording_alignment()
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.score_preview.alignment_for_role",
        lambda _project, _role: report,
    )
    plan_path = project / SCORE_ROLE_COMPOSITION_PATH
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text("not valid json", encoding="utf-8")

    # A stale/corrupt composition plan is a workspace-status concern, not something that
    # should block ordinary single-track preview.
    snapshot = load_score_fanout_preview_snapshot(project)
    assert {arr.instrument for arr in snapshot.arrangements} == {"bass", "lead", "rhythm"}


def test_score_fanout_preview_rejects_mapping_drift(tmp_path: Path) -> None:
    project = _build_project(tmp_path)
    contract = ProjectScoreSource.read_json(project / "sources" / "score" / "source.json")
    drifted = contract.model_copy(
        update={
            "arrangement_mappings": [
                mapping.model_copy(update={"human_confirmed": False})
                if mapping.role is ArrangementRole.lead
                else mapping
                for mapping in contract.arrangement_mappings
            ]
        }
    )
    drifted.write_json(project / "sources" / "score" / "source.json")

    with pytest.raises(ValueError, match="human-confirmed"):
        load_score_fanout_preview_snapshot(project)
