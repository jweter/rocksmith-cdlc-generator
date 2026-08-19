from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from rocksmith_cdlc_generator.alignment import AlignmentAnchor, AlignmentReport
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.reviewed_positions import (
    apply_reviewed_positions,
    load_current_reviewed_positions,
    set_reviewed_position,
)
from rocksmith_cdlc_generator.score_fanout import ScoreFanoutEntry, ScoreFanoutManifest
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
from rocksmith_cdlc_generator.shared_guitar import (
    build_project_shared_guitar_chart,
    load_current_shared_guitar_draft,
    shared_guitar_draft_is_current,
)
from rocksmith_cdlc_generator.shared_timeline import SharedTimeline, promote_shared_timeline
from rocksmith_cdlc_generator.source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTrack,
    SourceTrustClass,
)


def _source(score_sha: str, role: ArrangementRole, track_index: int) -> ImportedSource:
    if role is ArrangementRole.bass:
        tuning = [28, 33, 38, 43]
        note = SourceNoteEvent(
            start_seconds=0.5,
            duration_seconds=0.5,
            midi=40,
            import_confidence=1.0,
        )
    else:
        tuning = [40, 45, 50, 55, 59, 64]
        string_index = 0 if role is ArrangementRole.lead else 1
        fret = 3 if role is ArrangementRole.lead else 2
        midi = tuning[string_index] + fret
        note = SourceNoteEvent(
            start_seconds=0.5,
            duration_seconds=0.5,
            midi=midi,
            string_index=string_index,
            fret=fret,
            import_confidence=1.0,
            trust_class=SourceTrustClass.symbolic_verified,
        )
    return ImportedSource(
        provenance=SourceProvenance(
            source_type="gp5",
            source_filename="song.gp5",
            source_sha256=score_sha,
            importer="test",
            importer_version="1",
        ),
        beat_times_seconds=[0.0, 0.5, 1.0, 1.5, 2.0],
        tracks=[
            SourceTrack(
                source_track_index=track_index,
                name=role.value,
                instrument=role.value,
                tuning_midi=tuning,
                notes=[note],
            )
        ],
    )


def _write_project(tmp_path: Path) -> tuple[Path, dict[ArrangementRole, Path]]:
    project = tmp_path / "song"
    project.mkdir()
    recording_sha = "1" * 64
    ProjectManifest(
        project_name="song",
        title="Song",
        arrangement_instruments=["bass", "lead", "rhythm"],
        source_original_path="recording.flac",
        source_project_path="audio/source.flac",
        source_sha256=recording_sha,
        source_metadata=AudioMetadata(
            duration_seconds=180.0,
            sample_rate_hz=44100,
            channels=2,
            codec_name="flac",
            format_name="flac",
        ),
    ).save(project)

    stored_score = project / "sources" / "score" / "original" / "song.gp5"
    stored_score.parent.mkdir(parents=True, exist_ok=True)
    stored_score.write_bytes(b"complete-score")
    score_sha = hashlib.sha256(stored_score.read_bytes()).hexdigest()
    mappings = [
        ScoreArrangementMapping(role=ArrangementRole.bass, source_track_index=1, confidence=1.0, human_confirmed=True),
        ScoreArrangementMapping(role=ArrangementRole.lead, source_track_index=2, confidence=1.0, human_confirmed=True),
        ScoreArrangementMapping(role=ArrangementRole.rhythm, source_track_index=3, confidence=1.0, human_confirmed=True),
    ]
    score = ProjectScoreSource(
        source_filename="song.gp5",
        source_sha256=score_sha,
        source_format="gp5",
        imported_relative_path="sources/score/original/song.gp5",
        tracks=[
            ScoreTrackCandidate(source_track_index=1, name="Bass", instrument_hint="bass", note_count=1),
            ScoreTrackCandidate(source_track_index=2, name="Lead", instrument_hint="lead", note_count=1),
            ScoreTrackCandidate(source_track_index=3, name="Rhythm", instrument_hint="rhythm", note_count=1),
        ],
        arrangement_mappings=mappings,
    )
    score.write_json(project / "sources" / "score" / "source.json")

    outputs: dict[ArrangementRole, Path] = {}
    entries: list[ScoreFanoutEntry] = []
    for role, track_index in ((ArrangementRole.bass, 1), (ArrangementRole.lead, 2), (ArrangementRole.rhythm, 3)):
        output = project / "sources" / "imported" / f"score-{role.value}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        _source(score_sha, role, track_index).write_json(output)
        outputs[role] = output
        entries.append(
            ScoreFanoutEntry(
                role=role,
                source_track_index=track_index,
                output_json=output.relative_to(project).as_posix(),
            )
        )
    (project / "sources" / "imported" / f"score-fanout-{score_sha[:12]}.json").write_text(
        ScoreFanoutManifest(
            score_source_sha256=score_sha,
            score_source_format="gp5",
            arrangements=entries,
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )

    AlignmentReport(
        source_path=str(outputs[ArrangementRole.bass].resolve()),
        source_sha256=score_sha,
        recording_sha256=recording_sha,
        track_index=1,
        audio_beat_start_index=4,
        global_offset_seconds=2.0,
        anchor_stride_beats=8,
        matched_beats=5,
        rms_residual_seconds=0.01,
        median_abs_residual_seconds=0.01,
        max_abs_residual_seconds=0.02,
        confidence=0.95,
        anchors=[
            AlignmentAnchor(source_time_seconds=0.0, audio_time_seconds=2.0, source_beat_index=0, audio_beat_index=4, confidence=0.95),
            AlignmentAnchor(source_time_seconds=2.0, audio_time_seconds=4.0, source_beat_index=4, audio_beat_index=8, confidence=0.95),
        ],
        regions=[],
    ).write_json(project / "analysis" / "alignment.json")
    promote_shared_timeline(project)
    return project, outputs


def test_builds_lead_and_rhythm_from_one_shared_timeline(tmp_path: Path) -> None:
    project, _ = _write_project(tmp_path)

    lead_path = build_project_shared_guitar_chart(project, arrangement="lead")
    rhythm_path = build_project_shared_guitar_chart(project, arrangement="rhythm")
    lead, lead_manifest = load_current_shared_guitar_draft(project, arrangement="lead")
    rhythm, rhythm_manifest = load_current_shared_guitar_draft(project, arrangement="rhythm")

    assert lead_path == project / "charts" / "lead_source.json"
    assert rhythm_path == project / "charts" / "rhythm_source.json"
    assert lead.single_notes[0].start_seconds == pytest.approx(2.5)
    assert rhythm.single_notes[0].start_seconds == pytest.approx(2.5)
    assert lead.alignment_confidence == rhythm.alignment_confidence == pytest.approx(0.95)
    assert lead_manifest.recording_sha256 == rhythm_manifest.recording_sha256 == "1" * 64
    assert lead_manifest.score_sha256 == rhythm_manifest.score_sha256
    assert lead_manifest.shared_timeline_sha256 == rhythm_manifest.shared_timeline_sha256
    assert lead_manifest.position_review_sha256 is None
    assert rhythm_manifest.position_review_sha256 is None
    assert lead_manifest.source_track_index == 2
    assert rhythm_manifest.source_track_index == 3


def test_reviewed_position_is_pitch_checked_and_does_not_mutate_fanout(tmp_path: Path) -> None:
    project, outputs = _write_project(tmp_path)
    source_path = outputs[ArrangementRole.lead]
    source_hash = sha256_file(source_path)

    with pytest.raises(ValueError, match="does not produce the source MIDI pitch"):
        set_reviewed_position(
            project,
            arrangement="lead",
            event_index=0,
            string_index=1,
            fret=0,
        )

    layer = set_reviewed_position(
        project,
        arrangement="lead",
        event_index=0,
        string_index=0,
        fret=3,
    )
    assert sha256_file(source_path) == source_hash
    assert len(layer.decisions) == 1
    assert layer.decisions[0].midi == 43

    source = ImportedSource.read_json(source_path)
    reviewed, applied = apply_reviewed_positions(
        project,
        source,
        arrangement="lead",
        source_track_index=2,
    )
    assert applied == {0}
    assert reviewed.tracks[0].notes[0].string_index == 0
    assert reviewed.tracks[0].notes[0].fret == 3
    assert load_current_reviewed_positions(project) is not None


def test_position_review_change_invalidates_and_rebinds_shared_guitar_draft(tmp_path: Path) -> None:
    project, _ = _write_project(tmp_path)
    build_project_shared_guitar_chart(project, arrangement="lead")
    assert shared_guitar_draft_is_current(project, "lead") is True

    set_reviewed_position(
        project,
        arrangement="lead",
        event_index=0,
        string_index=0,
        fret=3,
    )
    assert shared_guitar_draft_is_current(project, "lead") is False
    with pytest.raises(ValueError, match="reviewed-position layer is stale"):
        load_current_shared_guitar_draft(project, arrangement="lead")

    build_project_shared_guitar_chart(project, arrangement="lead")
    chart, manifest = load_current_shared_guitar_draft(project, arrangement="lead")
    assert shared_guitar_draft_is_current(project, "lead") is True
    assert manifest.position_review_sha256 is not None
    assert chart.single_notes[0].string_index == 0
    assert chart.single_notes[0].fret == 3


def test_shared_guitar_draft_rejects_changed_arrangement_source(tmp_path: Path) -> None:
    project, outputs = _write_project(tmp_path)
    build_project_shared_guitar_chart(project, arrangement="lead")
    assert shared_guitar_draft_is_current(project, "lead") is True

    source = ImportedSource.read_json(outputs[ArrangementRole.lead])
    changed = source.model_copy(update={"warnings": ["changed after draft"]})
    changed.write_json(outputs[ArrangementRole.lead])

    assert shared_guitar_draft_is_current(project, "lead") is False
    with pytest.raises(ValueError, match="source content is stale"):
        load_current_shared_guitar_draft(project, arrangement="lead")


def test_shared_guitar_draft_rejects_changed_timing_transform(tmp_path: Path) -> None:
    project, _ = _write_project(tmp_path)
    build_project_shared_guitar_chart(project, arrangement="lead")
    assert shared_guitar_draft_is_current(project, "lead") is True

    timeline_path = project / "analysis" / "shared_timeline.json"
    timeline = SharedTimeline.read_json(timeline_path)
    timeline.model_copy(update={"global_offset_seconds": timeline.global_offset_seconds + 0.25}).write_json(timeline_path)

    assert shared_guitar_draft_is_current(project, "lead") is False
    with pytest.raises(ValueError, match="timing transform is stale"):
        load_current_shared_guitar_draft(project, arrangement="lead")


def test_rebuilding_guitar_invalidates_export_review_and_package_state(tmp_path: Path) -> None:
    project, _ = _write_project(tmp_path)
    build_project_shared_guitar_chart(project, arrangement="lead")

    stale = [
        project / "review" / "lead_validation_report.json",
        project / "review" / "lead_flags.json",
        project / "review" / "lead_summary.md",
        project / "eof" / "arr_lead_RS2.xml",
        project / "eof" / "lead_export_manifest.json",
        project / "eof" / "LEAD_README.md",
    ]
    for path in stale:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("stale", encoding="utf-8")

    dlcbuilder = project / "build" / "dlcbuilder" / "song.rs2dlc"
    dlcbuilder.parent.mkdir(parents=True, exist_ok=True)
    dlcbuilder.write_text("stale", encoding="utf-8")

    staged_psarc = project / "build" / "staging" / "Song_p.psarc"
    staged_receipt = project / "build" / "staging" / "psarc_receipt.json"
    staged_psarc.parent.mkdir(parents=True, exist_ok=True)
    staged_psarc.write_bytes(b"stale package")
    staged_receipt.write_text('{"safe_for_manual_installation": true}', encoding="utf-8")

    build_project_shared_guitar_chart(project, arrangement="lead")

    assert all(not path.exists() for path in stale)
    assert not (project / "build" / "dlcbuilder").exists()
    assert not (project / "build" / "staging").exists()
    assert not staged_psarc.exists()
    assert not staged_receipt.exists()
    assert (project / "charts" / "lead_source.json").is_file()


def _add_alternate_lead_track(project: Path) -> None:
    """Register an extra candidate score track (id 4) without touching the score's identity.

    The registered score contract's candidate-track list is descriptive metadata, not
    part of the immutable stored score's hash. Extending it here is enough to let a
    composition plan legally reference a second lead-role track index.
    """

    score_path = project / "sources" / "score" / "source.json"
    score = ProjectScoreSource.read_json(score_path)
    updated = score.model_copy(
        update={
            "tracks": [
                *score.tracks,
                ScoreTrackCandidate(
                    source_track_index=4, name="Alt Lead", instrument_hint="lead", note_count=1
                ),
            ]
        }
    )
    updated.write_json(score_path)


def _write_composition_plan(project: Path, score_sha: str, *, lead_track_indices: list[int]) -> None:
    plan = ScoreRoleCompositionPlan(
        score_sha256=score_sha,
        score_format="gp5",
        selections=[
            ScoreRoleCompositionSelection(
                role=ArrangementRole.lead, source_track_indices=lead_track_indices
            )
        ],
    )
    plan_path = project / SCORE_ROLE_COMPOSITION_PATH
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(plan.model_dump_json(indent=2) + "\n", encoding="utf-8")


def test_build_fails_closed_when_composition_selects_multiple_tracks_for_the_role(
    tmp_path: Path,
) -> None:
    project, _ = _write_project(tmp_path)
    score = ProjectScoreSource.read_json(project / "sources" / "score" / "source.json")
    _add_alternate_lead_track(project)
    _write_composition_plan(project, score.source_sha256, lead_track_indices=[2, 4])

    with pytest.raises(ValueError, match="does not yet consume composed multi-track output"):
        build_project_shared_guitar_chart(project, arrangement="lead")

    # Rhythm has no composition selection of its own and remains single-track/unaffected.
    rhythm_path = build_project_shared_guitar_chart(project, arrangement="rhythm")
    assert rhythm_path == project / "charts" / "rhythm_source.json"


def test_build_succeeds_when_composition_plan_only_selects_the_single_primary_track(
    tmp_path: Path,
) -> None:
    project, _ = _write_project(tmp_path)
    score = ProjectScoreSource.read_json(project / "sources" / "score" / "source.json")
    _write_composition_plan(project, score.source_sha256, lead_track_indices=[2])

    lead_path = build_project_shared_guitar_chart(project, arrangement="lead")
    assert lead_path == project / "charts" / "lead_source.json"


def test_build_ignores_a_stale_or_corrupt_composition_plan_file(tmp_path: Path) -> None:
    project, _ = _write_project(tmp_path)
    plan_path = project / SCORE_ROLE_COMPOSITION_PATH
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text("not valid json", encoding="utf-8")

    # A stale/corrupt composition plan is a workspace-status concern, not something that
    # should block ordinary single-track chart building.
    lead_path = build_project_shared_guitar_chart(project, arrangement="lead")
    assert lead_path == project / "charts" / "lead_source.json"


def test_rebuild_fails_closed_if_package_staging_cannot_be_removed(monkeypatch, tmp_path: Path) -> None:
    project, _ = _write_project(tmp_path)
    build_project_shared_guitar_chart(project, arrangement="lead")
    staged = project / "build" / "dlcbuilder" / "song.rs2dlc"
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_text("stale", encoding="utf-8")

    monkeypatch.setattr("rocksmith_cdlc_generator.shared_guitar.shutil.rmtree", lambda path: None)

    with pytest.raises(OSError, match="Failed to invalidate stale package staging"):
        build_project_shared_guitar_chart(project, arrangement="lead")
