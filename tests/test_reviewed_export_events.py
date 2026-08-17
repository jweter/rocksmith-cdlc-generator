from __future__ import annotations

from contextlib import contextmanager

import pytest

from rocksmith_cdlc_generator.accepted_score_timing import AcceptedScoreTimingPoint
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.reviewed_arrangement_timing import ReviewedArrangementTiming
from rocksmith_cdlc_generator import reviewed_export_events as export_module
from rocksmith_cdlc_generator.reviewed_export_events import reviewed_export_arrangement
from rocksmith_cdlc_generator.score_source import ArrangementRole
from rocksmith_cdlc_generator.source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTrack,
    SourceTrustClass,
)


_SHA_A = "a" * 64
_SHA_B = "b" * 64


def _points() -> list[AcceptedScoreTimingPoint]:
    return [
        AcceptedScoreTimingPoint(
            source_beat_index=0,
            source_time_seconds=0.0,
            candidate_time_seconds=1.0,
            reviewed_time_seconds=1.0,
            review_origin="human_anchor",
        ),
        AcceptedScoreTimingPoint(
            source_beat_index=1,
            source_time_seconds=1.0,
            candidate_time_seconds=2.0,
            reviewed_time_seconds=2.2,
            review_origin="bounded_refit",
        ),
        AcceptedScoreTimingPoint(
            source_beat_index=2,
            source_time_seconds=2.0,
            candidate_time_seconds=3.0,
            reviewed_time_seconds=3.0,
            review_origin="human_anchor",
        ),
    ]


def _write_source(tmp_path, role: ArrangementRole, track_index: int) -> tuple[str, str]:
    relative = f"sources/imported/{role.value}.json"
    path = tmp_path / relative
    source = ImportedSource(
        provenance=SourceProvenance(
            source_type="musicxml",
            source_filename="score.musicxml",
            source_sha256=_SHA_B,
            importer="test",
            importer_version="1",
        ),
        tracks=[
            SourceTrack(
                source_track_index=track_index,
                instrument=role.value,
                notes=[
                    SourceNoteEvent(
                        start_seconds=0.5,
                        duration_seconds=0.5,
                        midi=64,
                        note_name="E4",
                        string_index=1,
                        fret=2,
                        techniques=["hammer_on"],
                        import_confidence=0.95,
                        trust_class=SourceTrustClass.symbolic_verified,
                    ),
                    SourceNoteEvent(
                        start_seconds=1.0,
                        duration_seconds=0.5,
                        midi=67,
                        import_confidence=0.70,
                        trust_class=SourceTrustClass.symbolic_unverified,
                        review_required=True,
                    ),
                ],
            )
        ],
    )
    source.write_json(path)
    return relative, sha256_file(path)


def _timing(role: ArrangementRole, track_index: int, relative: str, output_sha: str) -> ReviewedArrangementTiming:
    return ReviewedArrangementTiming(
        role=role,
        source_track_index=track_index,
        source_output_json=relative,
        source_output_sha256=output_sha,
        recording_sha256=_SHA_A,
        score_sha256=_SHA_B,
        points=_points(),
        human_confirmed=True,
    )


def _locked_transaction(state: dict[str, bool]):
    @contextmanager
    def transaction(_project):
        assert not state["held"]
        state["held"] = True
        try:
            yield
        finally:
            state["held"] = False

    return transaction


@pytest.mark.parametrize(
    ("role", "track_index"),
    [
        (ArrangementRole.bass, 2),
        (ArrangementRole.lead, 5),
        (ArrangementRole.rhythm, 7),
    ],
)
def test_reviewed_export_projects_source_notes_for_each_arrangement(tmp_path, monkeypatch, role, track_index) -> None:
    relative, output_sha = _write_source(tmp_path, role, track_index)
    timing = _timing(role, track_index, relative, output_sha)
    state = {"held": False}
    monkeypatch.setattr(export_module, "score_mapping_transaction", _locked_transaction(state))

    def load_timing(_project, requested_role):
        assert state["held"]
        assert requested_role is role
        return timing

    original_read = export_module.ImportedSource.read_json

    def read_source(path):
        assert state["held"]
        return original_read(path)

    monkeypatch.setattr(export_module, "_reviewed_arrangement_timing_locked", load_timing)
    monkeypatch.setattr(export_module.ImportedSource, "read_json", read_source)

    projected = reviewed_export_arrangement(tmp_path, role)

    assert projected.role is role
    assert projected.source_track_index == track_index
    assert projected.human_confirmed_timing is True
    assert len(projected.notes) == 2
    first, second = projected.notes
    assert first.reviewed_start_seconds == pytest.approx(1.6)
    assert first.reviewed_duration_seconds == pytest.approx(0.6)
    assert first.string_index == 1
    assert first.fret == 2
    assert first.techniques == ["hammer_on"]
    assert first.position_ready is True
    assert second.reviewed_start_seconds == pytest.approx(2.2)
    assert second.reviewed_duration_seconds == pytest.approx(0.4)
    assert second.review_required is True
    assert second.position_ready is False
    assert state["held"] is False


def test_reviewed_export_rejects_changed_fanout_content(tmp_path, monkeypatch) -> None:
    role = ArrangementRole.lead
    relative, output_sha = _write_source(tmp_path, role, 5)
    timing = _timing(role, 5, relative, output_sha)
    (tmp_path / relative).write_text("changed", encoding="utf-8")
    monkeypatch.setattr(export_module, "_reviewed_arrangement_timing_locked", lambda _project, _role: timing)

    with pytest.raises(ValueError, match="fan-out output content changed"):
        reviewed_export_arrangement(tmp_path, role)


def test_reviewed_export_rejects_track_identity_mismatch(tmp_path, monkeypatch) -> None:
    role = ArrangementRole.rhythm
    relative, output_sha = _write_source(tmp_path, role, 7)
    timing = _timing(role, 8, relative, output_sha)
    monkeypatch.setattr(export_module, "_reviewed_arrangement_timing_locked", lambda _project, _role: timing)

    with pytest.raises(ValueError, match="fan-out track does not match"):
        reviewed_export_arrangement(tmp_path, role)
