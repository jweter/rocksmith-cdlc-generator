from __future__ import annotations

from pathlib import Path

import pytest

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


def test_score_fanout_preview_supports_all_three_roles(tmp_path: Path) -> None:
    project = _build_project(tmp_path)
    snapshot = load_score_fanout_preview_snapshot(project)

    assert {arr.instrument for arr in snapshot.arrangements} == {"bass", "lead", "rhythm"}
    assert snapshot.beat_times_seconds == [0.0, 0.5, 1.0, 1.5]
    assert sum(arr.note_count for arr in snapshot.arrangements) == 3

    window = build_preview_timeline_window(snapshot, 0.45, 0.9)
    assert len(window.lanes) == 3
    assert sum(len(lane.notes) for lane in window.lanes) == 3

    queue = build_preview_review_queue(snapshot)
    assert [item.instrument for item in queue.items] == ["lead", "rhythm"]
    assert all(item.string_index == 0 for item in queue.items)


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
