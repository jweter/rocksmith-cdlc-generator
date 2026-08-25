from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from rocksmith_cdlc_generator.alignment import AlignmentAnchor, AlignmentRegion, AlignmentReport
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.score_fanout import ScoreFanoutEntry, ScoreFanoutManifest
from rocksmith_cdlc_generator.score_source import (
    ArrangementRole,
    ProjectScoreSource,
    ScoreArrangementMapping,
    ScoreTrackCandidate,
)
from rocksmith_cdlc_generator.shared_timeline import (
    alignment_for_role,
    load_current_shared_timeline,
    promote_shared_timeline,
)
from rocksmith_cdlc_generator.source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTempoEvent,
    SourceTrack,
)


def _write_project(tmp_path: Path) -> tuple[Path, ProjectScoreSource, dict[ArrangementRole, Path]]:
    project = tmp_path / "song"
    project.mkdir()
    ProjectManifest(
        project_name="song",
        artist="Artist",
        title="Song",
        arrangement_instruments=["bass", "lead", "rhythm"],
        source_original_path="recording.flac",
        source_project_path="audio/source.flac",
        source_sha256="1" * 64,
        source_metadata=AudioMetadata(
            duration_seconds=180.0,
            sample_rate_hz=44100,
            channels=2,
            codec_name="flac",
            format_name="flac",
        ),
    ).save(project)

    stored = project / "sources" / "score" / "original" / "song.gp5"
    stored.parent.mkdir(parents=True, exist_ok=True)
    stored.write_bytes(b"complete-score")
    score_sha = hashlib.sha256(stored.read_bytes()).hexdigest()
    score = ProjectScoreSource(
        source_filename="song.gp5",
        source_sha256=score_sha,
        source_format="gp5",
        imported_relative_path="sources/score/original/song.gp5",
        tracks=[
            ScoreTrackCandidate(source_track_index=1, name="Bass", instrument_hint="bass", note_count=4),
            ScoreTrackCandidate(source_track_index=2, name="Lead", instrument_hint="lead", note_count=4),
            ScoreTrackCandidate(source_track_index=3, name="Rhythm", instrument_hint="rhythm", note_count=4),
        ],
        arrangement_mappings=[
            ScoreArrangementMapping(role=ArrangementRole.bass, source_track_index=1, confidence=1.0, human_confirmed=True),
            ScoreArrangementMapping(role=ArrangementRole.lead, source_track_index=2, confidence=1.0, human_confirmed=True),
            ScoreArrangementMapping(role=ArrangementRole.rhythm, source_track_index=3, confidence=1.0, human_confirmed=True),
        ],
    )
    contract = project / "sources" / "score" / "source.json"
    score.write_json(contract)

    outputs: dict[ArrangementRole, Path] = {}
    entries: list[ScoreFanoutEntry] = []
    for role, track_index in (
        (ArrangementRole.bass, 1),
        (ArrangementRole.lead, 2),
        (ArrangementRole.rhythm, 3),
    ):
        output = project / "sources" / "imported" / f"score-{role.value}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        ImportedSource(
            provenance=SourceProvenance(
                source_type="guitarpro",
                source_filename="song.gp5",
                source_sha256=score_sha,
                importer="test",
                importer_version="1",
            ),
            tempo_events=[SourceTempoEvent(tick=0, time_seconds=0.0, bpm=120.0)],
            beat_times_seconds=[0.0, 0.5, 1.0, 1.5],
            tracks=[
                SourceTrack(
                    source_track_index=track_index,
                    name=role.value,
                    instrument=role.value,
                    tuning_midi=[28, 33, 38, 43] if role is ArrangementRole.bass else [40, 45, 50, 55, 59, 64],
                    notes=[
                        SourceNoteEvent(
                            start_seconds=0.0,
                            duration_seconds=0.25,
                            midi=40,
                            import_confidence=1.0,
                        )
                    ],
                )
            ],
        ).write_json(output)
        outputs[role] = output
        entries.append(
            ScoreFanoutEntry(
                role=role,
                source_track_index=track_index,
                output_json=output.relative_to(project).as_posix(),
            )
        )

    manifest_path = project / "sources" / "imported" / f"score-fanout-{score_sha[:12]}.json"
    manifest_path.write_text(
        ScoreFanoutManifest(
            score_source_sha256=score_sha,
            score_source_format="gp5",
            arrangements=entries,
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )

    alignment = AlignmentReport(
        source_path=str(outputs[ArrangementRole.bass].resolve()),
        source_sha256=score_sha,
        recording_sha256="1" * 64,
        track_index=1,
        audio_beat_start_index=4,
        global_offset_seconds=2.0,
        anchor_stride_beats=8,
        matched_beats=4,
        rms_residual_seconds=0.01,
        median_abs_residual_seconds=0.01,
        max_abs_residual_seconds=0.02,
        confidence=0.94,
        anchors=[
            AlignmentAnchor(source_time_seconds=0.0, audio_time_seconds=2.0, source_beat_index=0, audio_beat_index=4, confidence=0.95),
            AlignmentAnchor(source_time_seconds=1.5, audio_time_seconds=3.5, source_beat_index=3, audio_beat_index=7, confidence=0.93),
        ],
        regions=[
            AlignmentRegion(
                source_start_seconds=0.0,
                source_end_seconds=1.5,
                audio_start_seconds=2.0,
                audio_end_seconds=3.5,
                rms_residual_seconds=0.01,
                max_abs_residual_seconds=0.02,
                confidence=0.94,
            )
        ],
    )
    alignment.write_json(project / "analysis" / "alignment.json")
    return project, score, outputs


def test_promote_shared_timeline_binds_recording_score_and_all_confirmed_roles(tmp_path: Path) -> None:
    project, score, outputs = _write_project(tmp_path)

    output = promote_shared_timeline(project)
    timeline = load_current_shared_timeline(project)

    assert output == project / "analysis" / "shared_timeline.json"
    assert timeline.recording_sha256 == "1" * 64
    assert timeline.score_sha256 == score.source_sha256
    assert timeline.authority_role is ArrangementRole.bass
    assert timeline.authority_track_index == 1
    assert timeline.authority_output_sha256 == sha256_file(outputs[ArrangementRole.bass])
    assert timeline.human_confirmed is True
    assert timeline.inherited_roles == [ArrangementRole.bass, ArrangementRole.lead, ArrangementRole.rhythm]


def test_lead_and_rhythm_inherit_identical_timing_transform(tmp_path: Path) -> None:
    project, _, outputs = _write_project(tmp_path)
    promote_shared_timeline(project)

    bass = alignment_for_role(project, ArrangementRole.bass)
    lead = alignment_for_role(project, ArrangementRole.lead)
    rhythm = alignment_for_role(project, ArrangementRole.rhythm)

    assert bass.anchors == lead.anchors == rhythm.anchors
    assert bass.regions == lead.regions == rhythm.regions
    assert bass.global_offset_seconds == lead.global_offset_seconds == rhythm.global_offset_seconds
    assert bass.recording_sha256 == lead.recording_sha256 == rhythm.recording_sha256 == "1" * 64
    assert lead.source_path == str(outputs[ArrangementRole.lead].resolve())
    assert lead.track_index == 2
    assert rhythm.source_path == str(outputs[ArrangementRole.rhythm].resolve())
    assert rhythm.track_index == 3


def test_promotion_rejects_alignment_from_non_authoritative_source(tmp_path: Path) -> None:
    project, score, outputs = _write_project(tmp_path)
    alignment_path = project / "analysis" / "alignment.json"
    alignment = AlignmentReport.model_validate_json(alignment_path.read_text(encoding="utf-8"))
    alignment = alignment.model_copy(update={
        "source_path": str(outputs[ArrangementRole.lead].resolve()),
        "track_index": 2,
        "source_sha256": score.source_sha256,
    })
    alignment.write_json(alignment_path)

    with pytest.raises(ValueError, match="authoritative shared-score bass output"):
        promote_shared_timeline(project)


def test_promotion_rejects_alignment_from_previous_recording(tmp_path: Path) -> None:
    project, _, _ = _write_project(tmp_path)
    alignment_path = project / "analysis" / "alignment.json"
    alignment = AlignmentReport.model_validate_json(alignment_path.read_text(encoding="utf-8"))
    alignment.model_copy(update={"recording_sha256": "2" * 64}).write_json(alignment_path)

    with pytest.raises(ValueError, match="recording provenance"):
        promote_shared_timeline(project)


def test_shared_timeline_becomes_stale_when_authority_output_content_changes(tmp_path: Path) -> None:
    project, _, outputs = _write_project(tmp_path)
    promote_shared_timeline(project)

    bass_path = outputs[ArrangementRole.bass]
    imported = ImportedSource.read_json(bass_path)
    imported.model_copy(update={"warnings": ["new importer output"]}).write_json(bass_path)

    with pytest.raises(ValueError, match="authority output content has changed"):
        load_current_shared_timeline(project)


def test_shared_timeline_becomes_stale_when_confirmed_roles_change(tmp_path: Path) -> None:
    project, score, _ = _write_project(tmp_path)
    promote_shared_timeline(project)

    changed = score.model_copy(update={
        "arrangement_mappings": [
            mapping for mapping in score.arrangement_mappings if mapping.role is not ArrangementRole.rhythm
        ]
    })
    changed.write_json(project / "sources" / "score" / "source.json")

    with pytest.raises(ValueError, match="shared timeline is not current|inherited roles"):
        load_current_shared_timeline(project)
