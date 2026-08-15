from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator.alignment import AlignmentAnchor, AlignmentRegion, AlignmentReport
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.score_fanout import ScoreFanoutEntry, ScoreFanoutManifest
from rocksmith_cdlc_generator.score_preview import load_score_fanout_preview_snapshot
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
