from __future__ import annotations

from pathlib import Path

import pytest

import rocksmith_cdlc_generator.arrangement_edit_history as edit_history


def _authority(*, score: str = "1" * 64, fanout: str = "2" * 64, timeline: str = "3" * 64):
    def current(_project: Path, *, timing_bound: bool):
        return {
            "score_sha256": score,
            "score_format": "gp5",
            "fanout_manifest_path": "sources/imported/score-fanout.json",
            "fanout_manifest_sha256": fanout,
            "shared_timeline_path": "analysis/shared_timeline.json" if timing_bound else None,
            "shared_timeline_sha256": timeline if timing_bound else None,
        }

    return current


def test_multi_step_undo_redo_restores_exact_review_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "song"
    project.mkdir()
    monkeypatch.setattr(edit_history, "_current_authority", _authority())

    positions = Path("review/reviewed_positions.json")
    techniques = Path("review/reviewed_techniques.json")
    edit_history.record_arrangement_review_edit(
        project,
        kind="position",
        writes={positions: '{"position":1}\n'},
    )
    edit_history.record_arrangement_review_edit(
        project,
        kind="techniques",
        writes={techniques: '{"technique":"vibrato"}\n'},
    )

    assert (project / positions).read_text(encoding="utf-8") == '{"position":1}\n'
    assert (project / techniques).read_text(encoding="utf-8") == '{"technique":"vibrato"}\n'

    second = edit_history.undo_arrangement_edit(project)
    assert second.kind == "techniques"
    assert not (project / techniques).exists()
    assert (project / positions).read_text(encoding="utf-8") == '{"position":1}\n'

    first = edit_history.undo_arrangement_edit(project)
    assert first.kind == "position"
    assert not (project / positions).exists()

    assert edit_history.redo_arrangement_edit(project).kind == "position"
    assert (project / positions).read_text(encoding="utf-8") == '{"position":1}\n'
    assert edit_history.redo_arrangement_edit(project).kind == "techniques"
    assert (project / techniques).read_text(encoding="utf-8") == '{"technique":"vibrato"}\n'


def test_new_edit_after_undo_clears_redo_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "song"
    project.mkdir()
    monkeypatch.setattr(edit_history, "_current_authority", _authority())
    target = Path("review/reviewed_positions.json")

    edit_history.record_arrangement_review_edit(project, kind="position", writes={target: "one\n"})
    edit_history.record_arrangement_review_edit(project, kind="position", writes={target: "two\n"})
    edit_history.undo_arrangement_edit(project)
    assert (project / target).read_text(encoding="utf-8") == "one\n"

    edit_history.record_arrangement_review_edit(project, kind="position", writes={target: "three\n"})
    history = edit_history.load_current_arrangement_edit_history(project)
    assert len(history.transactions) == 2
    assert history.cursor == 2
    assert not history.can_redo
    assert (project / target).read_text(encoding="utf-8") == "three\n"


def test_undo_refuses_stale_score_fanout_or_timing_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "song"
    project.mkdir()
    target = Path("review/reviewed_event_timing.json")
    monkeypatch.setattr(edit_history, "_current_authority", _authority())
    edit_history.record_arrangement_review_edit(
        project,
        kind="event_timing",
        writes={target: "timing-v1\n"},
        timing_bound=True,
    )

    monkeypatch.setattr(edit_history, "_current_authority", _authority(timeline="4" * 64))
    with pytest.raises(ValueError, match="stale"):
        edit_history.undo_arrangement_edit(project)
    assert (project / target).read_text(encoding="utf-8") == "timing-v1\n"

    monkeypatch.setattr(
        edit_history,
        "_current_authority",
        _authority(score="5" * 64, fanout="6" * 64, timeline="3" * 64),
    )
    with pytest.raises(ValueError, match="stale"):
        edit_history.undo_arrangement_edit(project)
    assert (project / target).read_text(encoding="utf-8") == "timing-v1\n"


def test_new_explicit_edit_replaces_history_whose_old_authority_is_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "song"
    project.mkdir()
    timing = Path("review/reviewed_event_timing.json")
    technique = Path("review/reviewed_techniques.json")
    monkeypatch.setattr(edit_history, "_current_authority", _authority())
    edit_history.record_arrangement_review_edit(
        project,
        kind="event_timing",
        writes={timing: "old-timing\n"},
        timing_bound=True,
    )

    def unavailable(_project: Path, *, timing_bound: bool):
        raise FileNotFoundError("old promoted timing authority is gone")

    monkeypatch.setattr(edit_history, "_current_authority", unavailable)
    edit_history.record_arrangement_review_edit(
        project,
        kind="techniques",
        writes={technique: "new-technique\n"},
        score_sha256="7" * 64,
        score_format="gp5",
        fanout_manifest_path="sources/imported/current-score-fanout.json",
        fanout_manifest_sha256="8" * 64,
    )

    history = edit_history.ArrangementEditHistory.model_validate_json(
        (project / edit_history.HISTORY_PATH).read_text(encoding="utf-8")
    )
    assert len(history.transactions) == 1
    assert history.transactions[0].kind == "techniques"
    assert history.transactions[0].score_sha256 == "7" * 64


def test_stale_review_replacement_undo_does_not_resurrect_obsolete_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "song"
    project.mkdir()
    target = Path("review/reviewed_techniques.json")
    (project / "review").mkdir()
    (project / target).write_text("obsolete-stale-authority\n", encoding="utf-8")
    monkeypatch.setattr(edit_history, "_current_authority", _authority())

    edit_history.record_arrangement_review_edit(
        project,
        kind="techniques",
        writes={target: "current-reviewed-techniques\n"},
        logical_before_overrides={target: None},
    )
    transaction = edit_history.undo_arrangement_edit(project)

    assert transaction.before[0].content is None
    assert not (project / target).exists()
    edit_history.redo_arrangement_edit(project)
    assert (project / target).read_text(encoding="utf-8") == "current-reviewed-techniques\n"


def test_undo_refuses_external_review_layer_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "song"
    project.mkdir()
    monkeypatch.setattr(edit_history, "_current_authority", _authority())
    target = Path("review/reviewed_chords.json")
    edit_history.record_arrangement_review_edit(
        project, kind="chord_identity", writes={target: "accepted\n"}
    )
    (project / target).write_text("external-change\n", encoding="utf-8")

    with pytest.raises(ValueError, match="changed outside"):
        edit_history.undo_arrangement_edit(project)
    assert (project / target).read_text(encoding="utf-8") == "external-change\n"


def test_transaction_can_restore_multiple_review_files_atomically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "song"
    project.mkdir()
    monkeypatch.setattr(edit_history, "_current_authority", _authority())
    first = Path("review/a.json")
    second = Path("review/b.json")
    (project / "review").mkdir()
    (project / first).write_text("a-before\n", encoding="utf-8")

    edit_history.record_arrangement_review_edit(
        project,
        kind="chord_fingering",
        writes={first: "a-after\n", second: "b-after\n"},
    )
    edit_history.undo_arrangement_edit(project)

    assert (project / first).read_text(encoding="utf-8") == "a-before\n"
    assert not (project / second).exists()


def test_failed_multi_file_write_rolls_back_already_applied_review_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "song"
    project.mkdir()
    monkeypatch.setattr(edit_history, "_current_authority", _authority())
    first = Path("review/a.json")
    second = Path("review/b.json")
    (project / "review").mkdir()
    (project / first).write_text("a-before\n", encoding="utf-8")

    real_write = edit_history._write_snapshot

    def fail_second(project_path: Path, snapshot: edit_history.ReviewFileSnapshot) -> None:
        if snapshot.path == second.as_posix() and snapshot.content == "b-after\n":
            raise OSError("simulated second-file failure")
        real_write(project_path, snapshot)

    monkeypatch.setattr(edit_history, "_write_snapshot", fail_second)
    with pytest.raises(OSError, match="second-file failure"):
        edit_history.record_arrangement_review_edit(
            project,
            kind="chord_fingering",
            writes={first: "a-after\n", second: "b-after\n"},
        )

    assert (project / first).read_text(encoding="utf-8") == "a-before\n"
    assert not (project / second).exists()
    assert not (project / edit_history.HISTORY_PATH).exists()
