from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator.score_role_composition_fanout_review import (
    compose_and_persist_score_role_composition_fanout,
)
from rocksmith_cdlc_generator.score_role_composition_review import record_score_role_composition
from rocksmith_cdlc_generator.score_role_composition_workspace_status import (
    inspect_score_role_composition_workspace_status,
)
from rocksmith_cdlc_generator.score_source import ArrangementRole
from tests.test_score_role_composition_fanout_review import (
    _OVERLAPPING_TRACK_NOTES,
    _TRACK_NOTES,
    _empty_decisions,
    _install_fake_musicxml_importer,
    _project_with_score,
)


def _setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, notes=None) -> tuple[Path, str]:
    project, digest = _project_with_score(tmp_path)
    _install_fake_musicxml_importer(monkeypatch, digest, notes_by_track=notes or _TRACK_NOTES)
    return project, digest


def test_bass_with_no_confirmed_mapping_is_unmapped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project, _digest = _setup(tmp_path, monkeypatch)

    status = inspect_score_role_composition_workspace_status(project)

    assert status.plan_stale_detail is None
    assert status.fanout_stale_detail is None
    bass = status.role_item("bass")
    assert bass is not None
    assert bass.state == "unmapped"
    assert bass.is_multi_track is False
    assert bass.selected_source_track_indices == []
    assert bass.blockers == ["bass has no human-confirmed primary score mapping yet"]


def test_mapped_role_without_a_plan_is_single_track(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, _digest = _setup(tmp_path, monkeypatch)

    status = inspect_score_role_composition_workspace_status(project)

    lead = status.role_item("lead")
    assert lead is not None
    assert lead.state == "single_track"
    assert lead.is_multi_track is False
    assert lead.primary_source_track_index == 0
    assert lead.primary_source_track_name == "Lead"
    assert lead.selected_source_track_indices == [0]
    assert lead.selected_source_track_names == ["Lead"]
    assert lead.available_source_track_indices == [1, 2, 3]
    assert lead.available_source_track_names == ["Rhythm 1", "Bass", "Rhythm 2"]
    assert lead.overlap_count is None
    assert lead.blockers == []


def test_multi_track_selection_without_fanout_is_pending_with_overlap_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, _digest = _setup(tmp_path, monkeypatch, notes=_OVERLAPPING_TRACK_NOTES)
    record_score_role_composition(project, selections={ArrangementRole.rhythm: [1, 3]})

    status = inspect_score_role_composition_workspace_status(project)

    rhythm = status.role_item("rhythm")
    assert rhythm is not None
    assert rhythm.state == "multi_track_pending"
    assert rhythm.is_multi_track is True
    assert rhythm.selected_source_track_indices == [1, 3]
    assert rhythm.selected_source_track_names == ["Rhythm 1", "Rhythm 2"]
    assert rhythm.available_source_track_indices == [0, 2]
    assert rhythm.available_source_track_names == ["Lead", "Bass"]
    assert rhythm.overlap_count == 1
    assert rhythm.blockers == []
    # The exact overlap evidence is exposed too, so an in-workspace overlap-decision UI
    # can present it without a separate overlap read.
    assert len(rhythm.overlaps) == 1
    overlap = rhythm.overlaps[0]
    assert overlap.kind == "exact_duplicate"
    assert {overlap.left.source_track_index, overlap.right.source_track_index} == {1, 3}


def test_composed_role_reports_no_overlap_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, digest = _setup(tmp_path, monkeypatch)
    record_score_role_composition(project, selections={ArrangementRole.rhythm: [1, 3]})
    compose_and_persist_score_role_composition_fanout(
        project, role=ArrangementRole.rhythm, decisions=_empty_decisions(digest)
    )

    status = inspect_score_role_composition_workspace_status(project)

    rhythm = status.role_item("rhythm")
    assert rhythm is not None
    assert rhythm.state == "multi_track_composed"
    assert rhythm.overlaps == []


def test_single_track_role_reports_no_overlap_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, _digest = _setup(tmp_path, monkeypatch)

    status = inspect_score_role_composition_workspace_status(project)

    lead = status.role_item("lead")
    assert lead is not None
    assert lead.state == "single_track"
    assert lead.overlaps == []


def test_multi_track_selection_with_matching_fanout_is_composed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, digest = _setup(tmp_path, monkeypatch)
    record_score_role_composition(project, selections={ArrangementRole.rhythm: [1, 3]})
    compose_and_persist_score_role_composition_fanout(
        project, role=ArrangementRole.rhythm, decisions=_empty_decisions(digest)
    )

    status = inspect_score_role_composition_workspace_status(project)

    rhythm = status.role_item("rhythm")
    assert rhythm is not None
    assert rhythm.state == "multi_track_composed"
    assert rhythm.overlap_count is None
    assert rhythm.blockers == []

    # The unrelated lead role stays single-track and untouched by rhythm's composition.
    lead = status.role_item("lead")
    assert lead is not None
    assert lead.state == "single_track"


def test_stale_fanout_falls_back_to_pending_and_surfaces_detail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, digest = _setup(tmp_path, monkeypatch)
    record_score_role_composition(project, selections={ArrangementRole.rhythm: [1, 3]})
    compose_and_persist_score_role_composition_fanout(
        project, role=ArrangementRole.rhythm, decisions=_empty_decisions(digest)
    )

    # Narrowing the plan back to a single track leaves the persisted fan-out stale.
    record_score_role_composition(project, selections={ArrangementRole.rhythm: [1]})

    status = inspect_score_role_composition_workspace_status(project)

    assert status.fanout_stale_detail is not None
    assert "stale for the current composition track set" in status.fanout_stale_detail
    rhythm = status.role_item("rhythm")
    assert rhythm is not None
    # The plan now only selects one track, so rhythm is single-track again rather than
    # granting the stale multi-track fan-out any authority.
    assert rhythm.state == "single_track"
    assert rhythm.selected_source_track_indices == [1]


def test_corrupt_plan_file_is_surfaced_and_roles_fall_back_to_primary_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, _digest = _setup(tmp_path, monkeypatch)
    record_score_role_composition(project, selections={ArrangementRole.rhythm: [1, 3]})
    plan_path = project / "review" / "score_role_composition.json"
    plan_path.write_text("not json", encoding="utf-8")

    status = inspect_score_role_composition_workspace_status(project)

    assert status.plan_stale_detail is not None
    rhythm = status.role_item("rhythm")
    assert rhythm is not None
    assert rhythm.state == "single_track"
    assert rhythm.selected_source_track_indices == [1]
