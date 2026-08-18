from __future__ import annotations

from rocksmith_cdlc_generator.source_import import ImportedSource
from rocksmith_cdlc_generator.source_track_trust_review import record_track_source_trust_acceptance
from rocksmith_cdlc_generator.track_trust_workspace_status import inspect_track_trust_workspace_status
from tests.test_source_track_trust_review import _write_project


def test_unreviewed_eligible_track_is_presented_as_acceptible(tmp_path) -> None:
    project, _output = _write_project(tmp_path)

    status = inspect_track_trust_workspace_status(project)

    assert status.stale_review_detail is None
    assert len(status.tracks) == 1
    item = status.tracks[0]
    assert item.arrangement == "lead"
    assert item.source_track_index == 2
    assert item.source_track_name == "Lead"
    assert item.note_count == 2
    assert item.review_state == "unreviewed"
    assert item.can_accept is True
    assert item.blockers == []
    assert item.acceptance_scope == "imported_note_identity_and_positions"


def test_current_acceptance_is_visible_without_hiding_independent_review(tmp_path) -> None:
    project, output = _write_project(tmp_path)
    record_track_source_trust_acceptance(project, arrangement="lead")

    status = inspect_track_trust_workspace_status(project)

    assert status.tracks[0].review_state == "current"
    assert status.tracks[0].can_accept is True
    imported = ImportedSource.read_json(output)
    assert imported.tracks[0].notes[1].review_required is True
    assert imported.tracks[0].notes[1].techniques == ["tie"]


def test_missing_positions_block_track_acceptance_with_actionable_count(tmp_path) -> None:
    project, _output = _write_project(tmp_path, missing_position=True)

    status = inspect_track_trust_workspace_status(project)

    item = status.tracks[0]
    assert item.review_state == "unreviewed"
    assert item.can_accept is False
    assert item.blockers == ["1 event(s) have unresolved string/fret positions"]


def test_pitch_conflict_blocks_track_acceptance_with_actionable_count(tmp_path) -> None:
    project, _output = _write_project(tmp_path, pitch_conflict=True)

    status = inspect_track_trust_workspace_status(project)

    item = status.tracks[0]
    assert item.can_accept is False
    assert item.blockers == ["1 event(s) have position/pitch conflicts"]


def test_stale_acceptance_is_visible_but_current_track_can_be_reaccepted(tmp_path) -> None:
    project, output = _write_project(tmp_path)
    record_track_source_trust_acceptance(project, arrangement="lead")
    imported = ImportedSource.read_json(output)
    imported.warnings.append("regenerated")
    imported.write_json(output)

    status = inspect_track_trust_workspace_status(project)

    assert status.stale_review_detail is not None
    assert "stale for current fan-out content" in status.stale_review_detail
    item = status.tracks[0]
    assert item.review_state == "stale"
    assert item.can_accept is True
    assert item.blockers == []
