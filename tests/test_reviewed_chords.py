from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import rocksmith_cdlc_generator.reviewed_chords as reviewed_chords


def _patch_authority(
    monkeypatch: pytest.MonkeyPatch,
    project: Path,
    *,
    starts: dict[int, float] | None = None,
) -> None:
    fanout = project / "sources" / "imported" / "score-fanout.json"
    fanout.parent.mkdir(parents=True, exist_ok=True)
    fanout.write_text("fanout-authority\n", encoding="utf-8")
    score = SimpleNamespace(source_sha256="1" * 64, source_format="gp5")
    entry = SimpleNamespace(source_track_index=2)
    track = SimpleNamespace()
    source_starts = starts or {0: 1.0, 1: 1.04, 2: 2.0}
    notes = {
        index: SimpleNamespace(start_seconds=start, midi=43 + index * 4)
        for index, start in source_starts.items()
    }
    monkeypatch.setattr(reviewed_chords, "_current_fanout", lambda _project: (fanout, object()))
    monkeypatch.setattr(reviewed_chords, "load_score_for_mapping_review", lambda _project: score)
    monkeypatch.setattr(
        reviewed_chords,
        "_source_event",
        lambda _project, arrangement, event_index: (entry, track, notes[event_index]),
    )


def test_accepts_nearby_source_events_as_reviewed_chord(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "song"
    project.mkdir()
    _patch_authority(monkeypatch, project)

    layer = reviewed_chords.set_reviewed_chord_group(
        project,
        arrangement="lead",
        event_indices=[1, 0],
    )

    assert len(layer.decisions) == 1
    assert layer.decisions[0].event_indices == [0, 1]
    assert (project / reviewed_chords.CHORD_REVIEW_PATH).is_file()
    assert reviewed_chords.reviewed_chord_groups(
        project, arrangement="lead", source_track_index=2
    ) == [[0, 1]]


def test_rejects_distant_events_before_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "song"
    project.mkdir()
    _patch_authority(monkeypatch, project)

    with pytest.raises(ValueError, match="span more than"):
        reviewed_chords.set_reviewed_chord_group(
            project,
            arrangement="lead",
            event_indices=[0, 2],
        )
    assert not (project / reviewed_chords.CHORD_REVIEW_PATH).exists()


def test_replacing_overlapping_group_removes_old_membership(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "song"
    project.mkdir()
    _patch_authority(monkeypatch, project, starts={0: 1.0, 1: 1.03, 2: 1.06})

    reviewed_chords.set_reviewed_chord_group(
        project,
        arrangement="lead",
        event_indices=[0, 1],
    )
    layer = reviewed_chords.set_reviewed_chord_group(
        project,
        arrangement="lead",
        event_indices=[1, 2],
    )

    assert [decision.event_indices for decision in layer.decisions] == [[1, 2]]


def test_stale_source_event_identity_is_rejected_on_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "song"
    project.mkdir()
    _patch_authority(monkeypatch, project)
    reviewed_chords.set_reviewed_chord_group(
        project,
        arrangement="lead",
        event_indices=[0, 1],
    )

    _patch_authority(monkeypatch, project, starts={0: 1.0, 1: 1.05, 2: 2.0})
    with pytest.raises(ValueError, match="source event identity"):
        reviewed_chords.load_current_reviewed_chords(project)


def test_new_acceptance_replaces_stale_chord_layer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "song"
    project.mkdir()
    _patch_authority(monkeypatch, project)
    reviewed_chords.set_reviewed_chord_group(
        project,
        arrangement="lead",
        event_indices=[0, 1],
    )

    # A changed source onset makes the persisted decision stale, but the user must be
    # able to accept a new group against the current authority without deleting files.
    _patch_authority(monkeypatch, project, starts={0: 1.0, 1: 1.05, 2: 2.0})
    layer = reviewed_chords.set_reviewed_chord_group(
        project,
        arrangement="lead",
        event_indices=[0, 1],
    )

    assert len(layer.decisions) == 1
    assert layer.decisions[0].event_indices == [0, 1]
    assert layer.decisions[0].members[1].source_start_seconds == pytest.approx(1.05)
    assert reviewed_chords.load_current_reviewed_chords(project) == layer
