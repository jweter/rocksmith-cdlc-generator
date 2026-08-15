from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from rocksmith_cdlc_generator.alignment import AlignmentAnchor, AlignmentReport
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.reviewed_event_timing import (
    load_current_reviewed_event_timing,
    set_reviewed_event_timing,
)
from rocksmith_cdlc_generator.score_fanout import ScoreFanoutEntry, ScoreFanoutManifest
from rocksmith_cdlc_generator.score_preview import load_score_fanout_preview_snapshot
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
from rocksmith_cdlc_generator.shared_timeline import promote_shared_timeline
from rocksmith_cdlc_generator.source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTrack,
    SourceTrustClass,
)


def _source(score_sha: str, role: ArrangementRole, track_index: int) -> ImportedSource:
    tuning = [28, 33, 38, 43] if role is ArrangementRole.bass else [40, 45, 50, 55, 59, 64]
    if role is ArrangementRole.bass:
        midi, string_index, fret = 40, None, None
    else:
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


def _project(tmp_path: Path) -> tuple[Path, dict[ArrangementRole, Path]]:
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
            duration_seconds=10.0,
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
    ProjectScoreSource(
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
    ).write_json(project / "sources" / "score" / "source.json")

    outputs: dict[ArrangementRole, Path] = {}
    entries: list[ScoreFanoutEntry] = []
    for role, track_index in ((ArrangementRole.bass, 1), (ArrangementRole.lead, 2), (ArrangementRole.rhythm, 3)):
        output = project / "sources" / "imported" / f"score-{role.value}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        _source(score_sha, role, track_index).write_json(output)
        outputs[role] = output
        entries.append(ScoreFanoutEntry(role=role, source_track_index=track_index, output_json=output.relative_to(project).as_posix()))
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
        audio_beat_start_index=0,
        global_offset_seconds=2.0,
        anchor_stride_beats=8,
        matched_beats=5,
        rms_residual_seconds=0.01,
        median_abs_residual_seconds=0.01,
        max_abs_residual_seconds=0.02,
        confidence=0.95,
        anchors=[
            AlignmentAnchor(source_time_seconds=0.0, audio_time_seconds=2.0, source_beat_index=0, audio_beat_index=0, confidence=0.95),
            AlignmentAnchor(source_time_seconds=2.0, audio_time_seconds=4.0, source_beat_index=4, audio_beat_index=4, confidence=0.95),
        ],
        regions=[],
    ).write_json(project / "analysis" / "alignment.json")
    promote_shared_timeline(project)
    return project, outputs


def test_event_timing_review_is_recording_bound_and_source_immutable(tmp_path: Path) -> None:
    project, outputs = _project(tmp_path)
    lead_source = outputs[ArrangementRole.lead]
    original_sha = sha256_file(lead_source)

    layer = set_reviewed_event_timing(
        project,
        arrangement="lead",
        event_index=0,
        start_seconds=2.625,
        duration_seconds=0.375,
    )

    assert sha256_file(lead_source) == original_sha
    decision = layer.decision_for("lead", 2, 0)
    assert decision is not None
    assert decision.reviewed_start_seconds == pytest.approx(2.625)
    assert decision.reviewed_duration_seconds == pytest.approx(0.375)
    assert load_current_reviewed_event_timing(project) is not None

    with pytest.raises(ValueError, match="beyond the recording duration"):
        set_reviewed_event_timing(
            project,
            arrangement="lead",
            event_index=0,
            start_seconds=9.9,
            duration_seconds=0.2,
        )


def test_preview_uses_current_reviewed_event_timing(tmp_path: Path) -> None:
    project, _outputs = _project(tmp_path)
    before = load_score_fanout_preview_snapshot(project)
    lead_before = next(item for item in before.arrangements if item.instrument == "lead").notes[0]
    assert lead_before.start_seconds == pytest.approx(2.5)

    set_reviewed_event_timing(
        project,
        arrangement="lead",
        event_index=0,
        start_seconds=2.7,
        duration_seconds=0.25,
    )
    after = load_score_fanout_preview_snapshot(project)
    lead_after = next(item for item in after.arrangements if item.instrument == "lead").notes[0]
    assert lead_after.start_seconds == pytest.approx(2.7)
    assert lead_after.duration_seconds == pytest.approx(0.25)


def test_event_timing_edit_stales_then_rebinds_shared_guitar_draft(tmp_path: Path) -> None:
    project, _outputs = _project(tmp_path)
    build_project_shared_guitar_chart(project, arrangement="lead")
    assert shared_guitar_draft_is_current(project, "lead") is True

    set_reviewed_event_timing(
        project,
        arrangement="lead",
        event_index=0,
        start_seconds=2.75,
        duration_seconds=0.2,
    )
    assert shared_guitar_draft_is_current(project, "lead") is False

    build_project_shared_guitar_chart(project, arrangement="lead")
    chart, manifest = load_current_shared_guitar_draft(project, arrangement="lead")
    assert manifest.event_timing_review_sha256 is not None
    assert chart.single_notes[0].start_seconds == pytest.approx(2.75)
    assert chart.single_notes[0].duration_seconds == pytest.approx(0.2)
