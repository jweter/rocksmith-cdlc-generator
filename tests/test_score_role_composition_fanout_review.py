from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator import score_role_composition_fanout_review as fanout_review
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.score_role_composition_fanout_review import (
    SCORE_ROLE_COMPOSITION_FANOUT_PATH,
    compose_and_persist_score_role_composition_fanout,
    load_current_score_role_composition_fanout,
)
from rocksmith_cdlc_generator.score_role_composition_overlap_review import (
    ScoreRoleCompositionOverlapDecisionPlan,
)
from rocksmith_cdlc_generator.score_role_composition_review import record_score_role_composition
from rocksmith_cdlc_generator.score_source import (
    ArrangementRole,
    ProjectScoreSource,
    ScoreArrangementMapping,
    ScoreTrackCandidate,
)
from rocksmith_cdlc_generator.source_import import ImportedSource, SourceNoteEvent, SourceProvenance, SourceTrack
from rocksmith_cdlc_generator.source_intake import (
    AdapterStatus,
    SourceFamily,
    SourceFormat,
    SourceIntakeDescriptor,
    SourceRightsClass,
)
from rocksmith_cdlc_generator.source_workflow import SourceIntakeReceipt

_TRACK_NOTES: dict[int, list[SourceNoteEvent]] = {
    1: [
        SourceNoteEvent(start_seconds=0.0, duration_seconds=0.5, midi=40, import_confidence=1.0),
        SourceNoteEvent(start_seconds=1.0, duration_seconds=0.5, midi=42, import_confidence=1.0),
    ],
    3: [
        SourceNoteEvent(start_seconds=0.5, duration_seconds=0.5, midi=45, import_confidence=1.0),
    ],
}
_OVERLAPPING_TRACK_NOTES: dict[int, list[SourceNoteEvent]] = {
    1: [SourceNoteEvent(start_seconds=1.0, duration_seconds=0.5, midi=52, import_confidence=1.0)],
    3: [SourceNoteEvent(start_seconds=1.0, duration_seconds=0.5, midi=52, import_confidence=1.0)],
}


def _project_with_score(
    tmp_path: Path,
    *,
    rights_class: SourceRightsClass = SourceRightsClass.user_owned_local,
) -> tuple[Path, str]:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text("{}", encoding="utf-8")

    stored = project / "sources" / "score" / "original" / "song.musicxml"
    stored.parent.mkdir(parents=True)
    stored.write_bytes(b"complete-score")
    digest = sha256_file(stored)

    score = ProjectScoreSource(
        source_filename="song.musicxml",
        source_sha256=digest,
        source_format="musicxml",
        imported_relative_path=stored.relative_to(project).as_posix(),
        tracks=[
            ScoreTrackCandidate(source_track_index=0, name="Lead", note_count=10),
            ScoreTrackCandidate(source_track_index=1, name="Rhythm 1", note_count=10),
            ScoreTrackCandidate(source_track_index=2, name="Bass", note_count=10),
            ScoreTrackCandidate(source_track_index=3, name="Rhythm 2", note_count=10),
        ],
        arrangement_mappings=[
            ScoreArrangementMapping(
                role=ArrangementRole.lead,
                source_track_index=0,
                confidence=0.9,
                human_confirmed=True,
            ),
            ScoreArrangementMapping(
                role=ArrangementRole.rhythm,
                source_track_index=1,
                confidence=0.9,
                human_confirmed=True,
            ),
        ],
    )
    score.write_json(project / "sources" / "score" / "source.json")

    descriptor = SourceIntakeDescriptor(
        display_name="song.musicxml",
        source_format=SourceFormat.musicxml,
        family=SourceFamily.notation,
        adapter_status=AdapterStatus.supported,
        rights_class=rights_class,
        local_bytes_available=True,
    )
    receipt = SourceIntakeReceipt(
        descriptor=descriptor,
        route_action="register_score_source",
        route_reason="test score registration",
        source_sha256=digest,
        output_relative_path=stored.relative_to(project).as_posix(),
    )
    receipt_path = project / "sources" / "intake" / f"song-{digest[:12]}-score.json"
    receipt_path.parent.mkdir(parents=True)
    receipt_path.write_text(receipt.model_dump_json(indent=2), encoding="utf-8")
    return project, digest


def _install_fake_musicxml_importer(
    monkeypatch: pytest.MonkeyPatch,
    digest: str,
    *,
    notes_by_track: dict[int, list[SourceNoteEvent]],
) -> list[tuple[int, str]]:
    calls: list[tuple[int, str]] = []

    def fake_import(path: Path, *, part_index: int | None = None, instrument: str = "bass") -> ImportedSource:
        assert part_index is not None
        calls.append((part_index, instrument))
        return ImportedSource(
            provenance=SourceProvenance(
                source_type="musicxml",
                source_filename=path.name,
                source_sha256=digest,
                importer="test",
                importer_version="1",
            ),
            tracks=[
                SourceTrack(
                    source_track_index=part_index,
                    name=f"Track {part_index}",
                    instrument=instrument,
                    notes=notes_by_track[part_index],
                )
            ],
        )

    monkeypatch.setattr(fanout_review, "import_musicxml", fake_import)
    return calls


def _empty_decisions(digest: str) -> ScoreRoleCompositionOverlapDecisionPlan:
    return ScoreRoleCompositionOverlapDecisionPlan(score_sha256=digest, score_format="musicxml")


def test_composes_and_persists_the_full_selected_track_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, digest = _project_with_score(tmp_path)
    calls = _install_fake_musicxml_importer(monkeypatch, digest, notes_by_track=_TRACK_NOTES)
    record_score_role_composition(project, selections={ArrangementRole.rhythm: [1, 3]})

    record = compose_and_persist_score_role_composition_fanout(
        project, role=ArrangementRole.rhythm, decisions=_empty_decisions(digest)
    )

    assert sorted(calls) == [(1, "rhythm"), (3, "rhythm")]
    assert record.source_track_indices == [1, 3]
    assert [item.source_track_index for item in record.track_outputs] == [1, 3]
    for output in record.track_outputs:
        path = project / output.output_json
        assert path.is_file()
        assert sha256_file(path) == output.output_sha256

    # Composed by start time: track 1's 0.0s note, then track 3's 0.5s note, then
    # track 1's 1.0s note.
    assert [(n.source_track_index, n.event_index) for n in record.notes] == [
        (1, 0),
        (3, 0),
        (1, 1),
    ]

    layer = load_current_score_role_composition_fanout(project)
    assert layer is not None
    assert layer.record_for(ArrangementRole.rhythm) == record
    assert (project / SCORE_ROLE_COMPOSITION_FANOUT_PATH).is_file()


def test_unresolved_overlap_blocks_persistence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project, digest = _project_with_score(tmp_path)
    _install_fake_musicxml_importer(monkeypatch, digest, notes_by_track=_OVERLAPPING_TRACK_NOTES)
    record_score_role_composition(project, selections={ArrangementRole.rhythm: [1, 3]})

    with pytest.raises(ValueError, match="unresolved overlap"):
        compose_and_persist_score_role_composition_fanout(
            project, role=ArrangementRole.rhythm, decisions=_empty_decisions(digest)
        )

    assert not (project / SCORE_ROLE_COMPOSITION_FANOUT_PATH).exists()


def test_requires_a_persisted_composition_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project, digest = _project_with_score(tmp_path)
    _install_fake_musicxml_importer(monkeypatch, digest, notes_by_track=_TRACK_NOTES)

    with pytest.raises(ValueError, match="No persisted score role composition plan"):
        compose_and_persist_score_role_composition_fanout(
            project, role=ArrangementRole.rhythm, decisions=_empty_decisions(digest)
        )


def test_role_without_a_current_selection_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, digest = _project_with_score(tmp_path)
    _install_fake_musicxml_importer(monkeypatch, digest, notes_by_track=_TRACK_NOTES)
    record_score_role_composition(project, selections={ArrangementRole.rhythm: [1, 3]})

    with pytest.raises(ValueError, match="lead has no current composition selection"):
        compose_and_persist_score_role_composition_fanout(
            project, role=ArrangementRole.lead, decisions=_empty_decisions(digest)
        )


def test_unreviewed_score_rights_stop_before_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, digest = _project_with_score(tmp_path, rights_class=SourceRightsClass.unknown)
    calls = _install_fake_musicxml_importer(monkeypatch, digest, notes_by_track=_TRACK_NOTES)
    record_score_role_composition(project, selections={ArrangementRole.rhythm: [1, 3]})

    with pytest.raises(ValueError, match="rights/provenance still require human review"):
        compose_and_persist_score_role_composition_fanout(
            project, role=ArrangementRole.rhythm, decisions=_empty_decisions(digest)
        )

    assert calls == []


def test_stale_when_composition_track_set_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, digest = _project_with_score(tmp_path)
    _install_fake_musicxml_importer(monkeypatch, digest, notes_by_track=_TRACK_NOTES)
    record_score_role_composition(project, selections={ArrangementRole.rhythm: [1, 3]})
    compose_and_persist_score_role_composition_fanout(
        project, role=ArrangementRole.rhythm, decisions=_empty_decisions(digest)
    )

    # Narrowing the persisted composition plan back to the single primary track must
    # invalidate the previously composed multi-track record.
    record_score_role_composition(project, selections={ArrangementRole.rhythm: [1]})

    with pytest.raises(ValueError, match="stale for the current composition track set"):
        load_current_score_role_composition_fanout(project)


def test_stale_when_a_track_output_changes_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, digest = _project_with_score(tmp_path)
    _install_fake_musicxml_importer(monkeypatch, digest, notes_by_track=_TRACK_NOTES)
    record_score_role_composition(project, selections={ArrangementRole.rhythm: [1, 3]})
    record = compose_and_persist_score_role_composition_fanout(
        project, role=ArrangementRole.rhythm, decisions=_empty_decisions(digest)
    )

    tampered = project / record.track_outputs[0].output_json
    imported = ImportedSource.read_json(tampered)
    imported.warnings.append("changed after composition")
    imported.write_json(tampered)

    with pytest.raises(ValueError, match="stale for current track output content"):
        load_current_score_role_composition_fanout(project)


def test_explicit_recompose_replaces_a_stale_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, digest = _project_with_score(tmp_path)
    _install_fake_musicxml_importer(monkeypatch, digest, notes_by_track=_TRACK_NOTES)
    record_score_role_composition(project, selections={ArrangementRole.rhythm: [1, 3]})
    compose_and_persist_score_role_composition_fanout(
        project, role=ArrangementRole.rhythm, decisions=_empty_decisions(digest)
    )

    record_score_role_composition(project, selections={ArrangementRole.rhythm: [1]})
    with pytest.raises(ValueError, match="stale"):
        load_current_score_role_composition_fanout(project)

    replacement = compose_and_persist_score_role_composition_fanout(
        project, role=ArrangementRole.rhythm, decisions=_empty_decisions(digest)
    )

    assert replacement.source_track_indices == [1]
    layer = load_current_score_role_composition_fanout(project)
    assert layer is not None
    assert layer.record_for(ArrangementRole.rhythm) == replacement


def test_recompose_preserves_other_roles_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, digest = _project_with_score(tmp_path)
    notes = dict(_TRACK_NOTES)
    notes[0] = [SourceNoteEvent(start_seconds=0.0, duration_seconds=0.5, midi=60, import_confidence=1.0)]
    _install_fake_musicxml_importer(monkeypatch, digest, notes_by_track=notes)
    record_score_role_composition(
        project, selections={ArrangementRole.rhythm: [1, 3], ArrangementRole.lead: [0]}
    )

    lead_record = compose_and_persist_score_role_composition_fanout(
        project, role=ArrangementRole.lead, decisions=_empty_decisions(digest)
    )
    rhythm_record = compose_and_persist_score_role_composition_fanout(
        project, role=ArrangementRole.rhythm, decisions=_empty_decisions(digest)
    )

    layer = load_current_score_role_composition_fanout(project)
    assert layer is not None
    assert layer.record_for(ArrangementRole.lead) == lead_record
    assert layer.record_for(ArrangementRole.rhythm) == rhythm_record
    assert len(layer.records) == 2
