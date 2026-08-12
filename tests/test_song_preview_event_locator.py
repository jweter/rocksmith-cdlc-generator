from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.song_preview import (
    PreviewArrangement,
    PreviewNoteEvent,
    SongPreviewSnapshot,
)
from rocksmith_cdlc_generator.song_preview_event_locator import (
    build_preview_event_locator,
)
from rocksmith_cdlc_generator.source_import import SourceTrustClass


def _note(event_index: int, start_seconds: float, duration_seconds: float = 0.25) -> PreviewNoteEvent:
    return PreviewNoteEvent(
        event_index=event_index,
        start_seconds=start_seconds,
        duration_seconds=duration_seconds,
        midi=64 + event_index,
        note_name="E4",
        string_index=event_index % 6,
        fret=event_index,
        techniques=["accent"],
        import_confidence=0.8,
        trust_class=SourceTrustClass.symbolic_unverified,
        review_required=False,
    )


def _arrangement(instrument: str, notes: list[PreviewNoteEvent]) -> PreviewArrangement:
    return PreviewArrangement(
        instrument=instrument,
        part_index={"lead": 0, "rhythm": 1, "bass": 2}[instrument],
        part_id={"lead": "P1", "rhythm": "P2", "bass": "P3"}[instrument],
        part_name=instrument.title(),
        tuning_midi=[40, 45, 50, 55, 59, 64] if instrument != "bass" else [28, 33, 38, 43],
        output_json=f"sources/imported/{instrument}.json",
        note_count=len(notes),
        notes=notes,
    )


def _snapshot() -> SongPreviewSnapshot:
    return SongPreviewSnapshot(
        source_filename="song.musicxml",
        source_sha256="a" * 64,
        arrangements=[
            _arrangement(
                "lead",
                [
                    _note(2, 2.0),
                    _note(0, 1.0, 0.5),
                    _note(1, 1.0, 0.25),
                ],
            )
        ],
    )


def test_returns_all_overlapping_candidates_without_guessing() -> None:
    state = build_preview_event_locator(_snapshot(), "lead", 1.1)

    assert state.match_kind == "overlap"
    assert [item.selection_id for item in state.candidates] == ["lead:0", "lead:1"]
    assert [item.distance_seconds for item in state.candidates] == [0.0, 0.0]


def test_half_open_intervals_do_not_match_exact_end() -> None:
    state = build_preview_event_locator(
        _snapshot(),
        "lead",
        1.5,
        tolerance_seconds=0.0,
    )

    assert state.match_kind == "nearby"
    assert [item.selection_id for item in state.candidates] == ["lead:0"]
    assert state.candidates[0].distance_seconds == 0.0


def test_returns_nearby_candidates_in_deterministic_distance_order() -> None:
    state = build_preview_event_locator(
        _snapshot(),
        "lead",
        1.8,
        tolerance_seconds=0.35,
    )

    assert state.match_kind == "nearby"
    assert [item.selection_id for item in state.candidates] == ["lead:2", "lead:0"]
    assert state.candidates[0].distance_seconds == pytest.approx(0.2)
    assert state.candidates[1].distance_seconds == pytest.approx(0.3)


def test_returns_none_when_no_event_is_within_tolerance() -> None:
    state = build_preview_event_locator(
        _snapshot(),
        "lead",
        10.0,
        tolerance_seconds=0.05,
    )

    assert state.match_kind == "none"
    assert state.candidates == []


def test_candidates_are_deep_copies() -> None:
    snapshot = _snapshot()
    state = build_preview_event_locator(snapshot, "lead", 1.1)

    state.candidates[0].event.techniques.append("preview-only")
    assert snapshot.arrangements[0].notes[1].techniques == ["accent"]


def test_rejects_invalid_or_ambiguous_locator_contracts() -> None:
    snapshot = _snapshot()

    with pytest.raises(ValueError, match="position must be non-negative"):
        build_preview_event_locator(snapshot, "lead", -0.1)
    with pytest.raises(ValueError, match="tolerance must be non-negative"):
        build_preview_event_locator(snapshot, "lead", 1.0, tolerance_seconds=-0.1)
    with pytest.raises(ValueError, match="arrangement not found"):
        build_preview_event_locator(snapshot, "bass", 1.0)

    duplicate_role = _snapshot()
    duplicate_role.arrangements.append(_arrangement("lead", [_note(9, 9.0)]))
    with pytest.raises(ValueError, match="duplicate arrangement role"):
        build_preview_event_locator(duplicate_role, "lead", 1.0)

    duplicate_event = _snapshot()
    duplicate_event.arrangements[0].notes.append(_note(0, 9.0))
    with pytest.raises(ValueError, match="duplicate event indices"):
        build_preview_event_locator(duplicate_event, "lead", 1.0)
