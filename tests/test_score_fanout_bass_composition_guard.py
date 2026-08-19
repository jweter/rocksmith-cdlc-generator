from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator import score_fanout
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.score_fanout import fanout_confirmed_score_mappings
from rocksmith_cdlc_generator.score_mapping_review import confirm_score_mapping
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
from rocksmith_cdlc_generator.source_import import ImportedSource, SourceProvenance, SourceTrack
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


def test_fanout_fails_closed_when_composition_selects_multiple_bass_tracks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, digest = _project_with_confirmed_bass(tmp_path)
    calls = _install_fake_importers(monkeypatch, digest)
    _write_bass_composition_plan(project, digest, bass_track_indices=[2, 3])

    with pytest.raises(ValueError, match="does not yet consume composed multi-track output"):
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
