from __future__ import annotations

from pathlib import Path

import pytest

import rocksmith_cdlc_generator.arrangement_edit_history as edit_history


def _authority(_project: Path, *, timing_bound: bool):
    return {
        "score_sha256": "1" * 64,
        "score_format": "gp5",
        "fanout_manifest_path": "sources/imported/score-fanout.json",
        "fanout_manifest_sha256": "2" * 64,
        "shared_timeline_path": "analysis/shared_timeline.json" if timing_bound else None,
        "shared_timeline_sha256": "3" * 64 if timing_bound else None,
    }


def test_undo_refuses_drift_in_earlier_applied_managed_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "song"
    project.mkdir()
    monkeypatch.setattr(edit_history, "_current_authority", _authority)
    positions = Path("review/reviewed_positions.json")
    techniques = Path("review/reviewed_techniques.json")

    edit_history.record_arrangement_review_edit(
        project, kind="position", writes={positions: "position-v1\n"}
    )
    edit_history.record_arrangement_review_edit(
        project, kind="techniques", writes={techniques: "technique-v1\n"}
    )
    (project / positions).write_text("external-position-change\n", encoding="utf-8")

    with pytest.raises(ValueError, match="changed outside history"):
        edit_history.undo_arrangement_edit(project)

    assert (project / positions).read_text(encoding="utf-8") == "external-position-change\n"
    assert (project / techniques).read_text(encoding="utf-8") == "technique-v1\n"


def test_redo_refuses_drift_in_other_applied_managed_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "song"
    project.mkdir()
    monkeypatch.setattr(edit_history, "_current_authority", _authority)
    positions = Path("review/reviewed_positions.json")
    techniques = Path("review/reviewed_techniques.json")

    edit_history.record_arrangement_review_edit(
        project, kind="position", writes={positions: "position-v1\n"}
    )
    edit_history.record_arrangement_review_edit(
        project, kind="techniques", writes={techniques: "technique-v1\n"}
    )
    edit_history.undo_arrangement_edit(project)
    (project / positions).write_text("external-position-change\n", encoding="utf-8")

    with pytest.raises(ValueError, match="changed outside history"):
        edit_history.redo_arrangement_edit(project)

    assert (project / positions).read_text(encoding="utf-8") == "external-position-change\n"
    assert not (project / techniques).exists()


def test_redo_still_validates_next_transactions_before_state_for_new_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "song"
    project.mkdir()
    monkeypatch.setattr(edit_history, "_current_authority", _authority)
    positions = Path("review/reviewed_positions.json")
    techniques = Path("review/reviewed_techniques.json")

    edit_history.record_arrangement_review_edit(
        project, kind="position", writes={positions: "position-v1\n"}
    )
    edit_history.record_arrangement_review_edit(
        project, kind="techniques", writes={techniques: "technique-v1\n"}
    )
    edit_history.undo_arrangement_edit(project)
    (project / techniques).write_text("external-technique-change\n", encoding="utf-8")

    with pytest.raises(ValueError, match="changed outside history"):
        edit_history.redo_arrangement_edit(project)

    assert (project / positions).read_text(encoding="utf-8") == "position-v1\n"
    assert (project / techniques).read_text(encoding="utf-8") == "external-technique-change\n"
