from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator import score_fanout
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.reconciliation import ReconciledBassChart
from rocksmith_cdlc_generator.score_fanout import fanout_confirmed_score_mappings
from rocksmith_cdlc_generator.score_mapping_review import confirm_score_mapping
from rocksmith_cdlc_generator.score_role_composition import (
    ScoreRoleCompositionPlan,
    ScoreRoleCompositionSelection,
)
from rocksmith_cdlc_generator.score_role_composition_fanout import ComposedSourceNote
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
from rocksmith_cdlc_generator.source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTrack,
    SourceTrustClass,
)
from rocksmith_cdlc_generator.source_intake import (
    AdapterStatus,
    SourceFamily,
    SourceFormat,
    SourceIntakeDescriptor,
    SourceRightsClass,
)
from rocksmith_cdlc_generator.source_workflow import SourceIntakeReceipt


def _project_with_confirmed_bass(tmp_path: Path) -> tuple[Path, str]:
    """A registered score with Lead/Rhythm/Bass confirmed plus an unmapped alt-bass track.

    The alt-bass track (index 3) exists purely so a human composition selection can add a
    second track for Bass ([2, 3]) without referencing an unknown score track.
    """

    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text("{}", encoding="utf-8")

    stored = project / "sources" / "score" / "original" / "song.gp5"
    stored.parent.mkdir(parents=True)
    stored.write_bytes(b"complete-score")
    digest = sha256_file(stored)

    score = ProjectScoreSource(
        source_filename="song.gp5",
        source_sha256=digest,
        source_format="gp5",
        imported_relative_path=stored.relative_to(project).as_posix(),
        tracks=[
            ScoreTrackCandidate(source_track_index=0, name="Lead Guitar", note_count=100),
            ScoreTrackCandidate(source_track_index=1, name="Rhythm Guitar", note_count=120),
            ScoreTrackCandidate(source_track_index=2, name="Bass", note_count=90),
            ScoreTrackCandidate(source_track_index=3, name="Alt Bass", note_count=40),
        ],
        arrangement_mappings=[
            ScoreArrangementMapping(
                role=ArrangementRole.lead,
                source_track_index=0,
                confidence=0.98,
                basis=["track name contains lead"],
                human_confirmed=True,
            ),
            ScoreArrangementMapping(
                role=ArrangementRole.rhythm,
                source_track_index=1,
                confidence=0.95,
                basis=["track name contains rhythm"],
                human_confirmed=True,
            ),
            ScoreArrangementMapping(
                role=ArrangementRole.bass,
                source_track_index=2,
                confidence=1.0,
                basis=["track name contains bass"],
                human_confirmed=True,
            ),
        ],
    )
    score.write_json(project / "sources" / "score" / "source.json")

    descriptor = SourceIntakeDescriptor(
        display_name="song.gp5",
        source_format=SourceFormat.gp5,
        family=SourceFamily.notation,
        adapter_status=AdapterStatus.optional_dependency,
        rights_class=SourceRightsClass.user_owned_local,
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

    # confirm_score_mapping re-confirming the already-human_confirmed mappings above is a
    # no-op, but calling it keeps this fixture aligned with how the same mapping/rights
    # state is normally reached through the reviewed CLI/GUI path.
    confirm_score_mapping(project, role=ArrangementRole.bass, source_track_index=2)

    return project, digest


def _install_fake_importers(monkeypatch: pytest.MonkeyPatch, digest: str) -> list[tuple[str, int]]:
    calls: list[tuple[str, int]] = []

    def fake_import(
        project_dir: Path,
        gp_path: Path,
        *,
        track_index: int | None = None,
        instrument: str = "bass",
    ) -> Path:
        assert track_index is not None
        calls.append((instrument, track_index))
        output = project_dir / "sources" / "imported" / f"fake-{instrument}.json"
        ImportedSource(
            provenance=SourceProvenance(
                source_type="gp5",
                source_filename=gp_path.name,
                source_sha256=digest,
                importer="test",
                importer_version="1",
            ),
            tracks=[
                SourceTrack(source_track_index=track_index, instrument=instrument, notes=[]),
            ],
        ).write_json(output)
        return output

    monkeypatch.setattr(score_fanout, "import_project_guitarpro", fake_import)
    return calls


def _write_bass_composition_plan(
    project: Path, score_sha: str, *, bass_track_indices: list[int]
) -> None:
    plan = ScoreRoleCompositionPlan(
        score_sha256=score_sha,
        score_format="gp5",
        selections=[
            ScoreRoleCompositionSelection(
                role=ArrangementRole.bass, source_track_indices=bass_track_indices
            )
        ],
    )
    plan_path = project / SCORE_ROLE_COMPOSITION_PATH
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(plan.model_dump_json(indent=2) + "\n", encoding="utf-8")


def test_fanout_fails_closed_when_composition_selects_multiple_bass_tracks_with_no_composed_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, digest = _project_with_confirmed_bass(tmp_path)
    calls = _install_fake_importers(monkeypatch, digest)
    _write_bass_composition_plan(project, digest, bass_track_indices=[2, 3])

    with pytest.raises(ValueError, match="no current composed fan-out record exists"):
        fanout_confirmed_score_mappings(project, roles=[ArrangementRole.bass])

    assert calls == []


def test_fanout_of_other_roles_is_unaffected_by_a_bass_only_composition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, digest = _project_with_confirmed_bass(tmp_path)
    calls = _install_fake_importers(monkeypatch, digest)
    _write_bass_composition_plan(project, digest, bass_track_indices=[2, 3])

    # Lead/Rhythm have no composition selection of their own and remain unaffected by a
    # Bass-only multi-track composition plan.
    fanout_confirmed_score_mappings(project, roles=[ArrangementRole.lead])
    fanout_confirmed_score_mappings(project, roles=[ArrangementRole.rhythm])

    assert calls == [("lead", 0), ("rhythm", 1)]


def test_fanout_succeeds_when_composition_plan_only_selects_the_single_primary_bass_track(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, digest = _project_with_confirmed_bass(tmp_path)
    calls = _install_fake_importers(monkeypatch, digest)
    _write_bass_composition_plan(project, digest, bass_track_indices=[2])

    fanout_confirmed_score_mappings(project, roles=[ArrangementRole.bass])

    assert calls == [("bass", 2)]


def test_fanout_ignores_a_stale_or_corrupt_bass_composition_plan_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, digest = _project_with_confirmed_bass(tmp_path)
    calls = _install_fake_importers(monkeypatch, digest)
    plan_path = project / SCORE_ROLE_COMPOSITION_PATH
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text("not valid json", encoding="utf-8")

    # A stale/corrupt composition plan is a workspace-status concern, not something that
    # should block ordinary single-track Bass fan-out.
    fanout_confirmed_score_mappings(project, roles=[ArrangementRole.bass])

    assert calls == [("bass", 2)]


_BASS_TUNING = [28, 33, 38, 43]


def _write_multi_track_bass_composition(
    project: Path, score_sha: str, *, track_indices: list[int]
) -> RoleCompositionFanoutRecord:
    """Persist a composed fan-out record for bass=``track_indices``, mirroring what
    ``compose_and_persist_score_role_composition_fanout`` would have written after a
    human imported every selected track, resolved any overlaps, and composed them --
    without needing a real GuitarPro file to import from. Mirrors
    ``test_shared_guitar_timeline.py``'s ``_write_multi_track_lead_composition``.
    """

    def provenance() -> SourceProvenance:
        return SourceProvenance(
            source_type="gp5",
            source_filename="song.gp5",
            source_sha256=score_sha,
            importer="test",
            importer_version="1",
        )

    track_outputs: list[ComposedTrackOutput] = []
    notes: list[ComposedSourceNote] = []
    for offset, track_index in enumerate(track_indices):
        note = SourceNoteEvent(
            start_seconds=0.1 * offset,
            duration_seconds=0.2,
            midi=_BASS_TUNING[0] + track_index,
            string_index=0,
            fret=track_index,
            import_confidence=1.0,
            trust_class=SourceTrustClass.symbolic_verified,
        )
        source = ImportedSource(
            provenance=provenance(),
            tracks=[
                SourceTrack(
                    source_track_index=track_index,
                    name="bass",
                    instrument="bass",
                    tuning_midi=_BASS_TUNING,
                    notes=[note],
                )
            ],
        )
        output_path = (
            project
            / "sources"
            / "imported"
            / "composition"
            / f"bass-track{track_index}-{score_sha[:12]}.json"
        )
        source.write_json(output_path)
        track_outputs.append(
            ComposedTrackOutput(
                source_track_index=track_index,
                output_json=output_path.relative_to(project).as_posix(),
                output_sha256=sha256_file(output_path),
            )
        )
        notes.append(ComposedSourceNote(source_track_index=track_index, event_index=0, note=note))

    record = RoleCompositionFanoutRecord(
        role=ArrangementRole.bass,
        score_sha256=score_sha,
        score_format="gp5",
        source_track_indices=track_indices,
        track_outputs=track_outputs,
        notes=sorted(notes, key=lambda item: item.note.start_seconds),
    )
    layer = ScoreRoleCompositionFanoutReviewLayer(
        score_sha256=score_sha, score_format="gp5", records=[record]
    )
    layer_path = project / SCORE_ROLE_COMPOSITION_FANOUT_PATH
    layer_path.parent.mkdir(parents=True, exist_ok=True)
    layer_path.write_text(layer.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return record


def test_fanout_consumes_a_current_composed_multi_track_bass_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, digest = _project_with_confirmed_bass(tmp_path)
    calls = _install_fake_importers(monkeypatch, digest)
    _write_bass_composition_plan(project, digest, bass_track_indices=[2, 3])
    _write_multi_track_bass_composition(project, digest, track_indices=[2, 3])

    result = fanout_confirmed_score_mappings(project, roles=[ArrangementRole.bass])

    # The primary track's ordinary GuitarPro importer is never invoked; the already
    # human-composed multi-track note stream is materialized directly instead.
    assert calls == []

    bass_output = Path(result.outputs["bass"])
    assert "composition" in bass_output.parts
    imported = ImportedSource.read_json(bass_output)
    assert imported.provenance.source_sha256 == digest
    assert len(imported.tracks) == 1
    track = imported.tracks[0]
    assert track.source_track_index == 2
    assert track.instrument == "bass"
    # One note from each contributing track, not silently dropped to only the primary.
    assert len(track.notes) == 2
    starts = [note.start_seconds for note in track.notes]
    assert starts == sorted(starts)


def test_set_reviewed_position_accepts_a_composed_bass_selection_after_fanout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bass's composed multi-track fan-out is materialized directly into the score fan-out
    manifest, so ``reviewed_positions.py``'s composed-review gap guard must never fire for
    Bass -- unlike Lead/Rhythm, whose composed materialization the manifest never reflects
    (see ``test_shared_guitar_timeline.py``'s
    ``test_set_reviewed_position_fails_closed_for_an_unmaterialized_composed_lead_selection``).
    """

    from rocksmith_cdlc_generator.reviewed_positions import set_reviewed_position

    project, digest = _project_with_confirmed_bass(tmp_path)
    _install_fake_importers(monkeypatch, digest)
    _write_bass_composition_plan(project, digest, bass_track_indices=[2, 3])
    _write_multi_track_bass_composition(project, digest, track_indices=[2, 3])

    fanout_confirmed_score_mappings(project, roles=[ArrangementRole.bass])

    # The first composed note (track 2, midi 30) is playable open on the tuning's lowest
    # string (28 + 2 = 30).
    layer = set_reviewed_position(
        project,
        arrangement="bass",
        event_index=0,
        string_index=0,
        fret=2,
    )
    assert len(layer.decisions) == 1
    assert layer.decisions[0].midi == 30


def test_composition_narrowed_after_reconciliation_invalidates_stale_bass_derivatives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression test for Trap 2 from the issue #232 design notes: narrowing a bass
    composition selection back to the single confirmed primary track changes the fanned-
    out content at that *same* primary track index. A staleness check bound only to
    ``(score_sha256, track_index)`` would incorrectly treat a reconciliation built from
    the old composed note stream as still current; content-hash binding must not.
    """

    project, digest = _project_with_confirmed_bass(tmp_path)
    _install_fake_importers(monkeypatch, digest)
    _write_bass_composition_plan(project, digest, bass_track_indices=[2, 3])
    _write_multi_track_bass_composition(project, digest, track_indices=[2, 3])

    composed_result = fanout_confirmed_score_mappings(project, roles=[ArrangementRole.bass])
    composed_output = Path(composed_result.outputs["bass"])

    # Persist a Bass reconciliation bound to this exact composed output's content, as
    # `reconcile_project_bass` would after running Bass reconciliation on it.
    reconciled = ReconciledBassChart(
        source_sha256=digest,
        track_index=2,
        source_content_sha256=sha256_file(composed_output),
        onset_tolerance_seconds=0.15,
        verified_onset_tolerance_seconds=0.08,
        notes=[],
    )
    reconciled_path = project / "charts" / "bass_reconciled.json"
    reconciled_path.parent.mkdir(parents=True, exist_ok=True)
    reconciled_path.write_text(reconciled.model_dump_json(indent=2), encoding="utf-8")

    # Narrow the composition selection back to a single track. The next Bass fan-out now
    # produces an ordinary single-track import at the *same* primary track index (2) but
    # with different content.
    _write_bass_composition_plan(project, digest, bass_track_indices=[2])

    fanout_confirmed_score_mappings(project, roles=[ArrangementRole.bass])

    assert not reconciled_path.exists()
