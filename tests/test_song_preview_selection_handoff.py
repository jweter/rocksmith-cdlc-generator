from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.song_preview import (
    PreviewArrangement,
    PreviewNoteEvent,
    SongPreviewSnapshot,
)
from rocksmith_cdlc_generator.song_preview_event_locator import (
    PreviewEventLocatorCandidate,
    PreviewEventLocatorState,
    build_preview_event_locator,
)
from rocksmith_cdlc_generator.song_preview_selection_handoff import (
    build_preview_selection_handoff,
)
from rocksmith_cdlc_generator.source_import import SourceTrustClass


def _note(event_index: int, start: float, duration: float = 0.4) -> PreviewNoteEvent:
    return PreviewNoteEvent(
        event_index=event_index,
        start_seconds=start,
        duration_seconds=duration,
        midi=64 + event_index,
        note_name="E4",
        string_index=event_index % 6,
        fret=event_index,
        techniques=[],
        import_confidence=0.8,
        trust_class=SourceTrustClass.symbolic_unverified,
        review_required=event_index == 1,
    )


def _snapshot() -> SongPreviewSnapshot:
    notes = [_note(0, 1.0, 0.6), _note(1, 1.2, 0.6), _note(2, 2.0)]
    return SongPreviewSnapshot(
        source_filename="song.musicxml",
        source_sha256="a" * 64,
        arrangements=[
            PreviewArrangement(
                instrument="lead",
                part_index=0,
                part_id="P1",
                part_name="Lead Guitar",
                tuning_midi=[40, 45, 50, 55, 59, 64],
                output_json="sources/imported/lead.json",
                note_count=len(notes),
                notes=notes,
            )
        ],
    )


def test_single_locator_candidate_resolves_to_trusted_inspector_state() -> None:
    snapshot = _snapshot()
    locator = build_preview_event_locator(
        snapshot, "lead", 2.1, tolerance_seconds=0.0
    )

    handoff = build_preview_selection_handoff(snapshot, locator)

    assert handoff.requires_choice is False
    assert handoff.candidate_selection_ids == ["lead:2"]
    assert handoff.selected is not None
    assert handoff.selected.selection_id == "lead:2"
    assert handoff.selected.source_sha256 == "a" * 64


def test_overlapping_candidates_require_explicit_choice() -> None:
    snapshot = _snapshot()
    locator = build_preview_event_locator(
        snapshot, "lead", 1.3, tolerance_seconds=0.0
    )

    handoff = build_preview_selection_handoff(snapshot, locator)

    assert handoff.requires_choice is True
    assert handoff.selected is None
    assert handoff.candidate_selection_ids == ["lead:0", "lead:1"]


def test_explicit_choice_resolves_only_a_returned_candidate() -> None:
    snapshot = _snapshot()
    locator = build_preview_event_locator(
        snapshot, "lead", 1.3, tolerance_seconds=0.0
    )

    handoff = build_preview_selection_handoff(
        snapshot, locator, selection_id="lead:1"
    )

    assert handoff.requires_choice is False
    assert handoff.selected is not None
    assert handoff.selected.selection_id == "lead:1"
    assert handoff.selected.review_id == "lead:1"

    with pytest.raises(ValueError, match="not a locator candidate"):
        build_preview_selection_handoff(
            snapshot, locator, selection_id="lead:2"
        )


def test_empty_locator_stays_unselected() -> None:
    snapshot = _snapshot()
    locator = build_preview_event_locator(
        snapshot, "lead", 9.0, tolerance_seconds=0.01
    )

    handoff = build_preview_selection_handoff(snapshot, locator)

    assert handoff.candidate_selection_ids == []
    assert handoff.requires_choice is False
    assert handoff.selected is None

    with pytest.raises(ValueError, match="empty locator"):
        build_preview_selection_handoff(
            snapshot, locator, selection_id="lead:0"
        )


def test_handoff_rebuilds_from_snapshot_not_locator_event_payload() -> None:
    snapshot = _snapshot()
    locator = build_preview_event_locator(
        snapshot, "lead", 2.1, tolerance_seconds=0.0
    )
    locator.candidates[0].event.midi = 99

    handoff = build_preview_selection_handoff(snapshot, locator)

    assert handoff.selected is not None
    assert handoff.selected.selected.midi == 66


def test_rejects_inconsistent_or_duplicate_locator_contracts() -> None:
    snapshot = _snapshot()
    locator = build_preview_event_locator(
        snapshot, "lead", 2.1, tolerance_seconds=0.0
    )
    locator.candidates[0].selection_id = "bass:2"
    with pytest.raises(ValueError, match="identity"):
        build_preview_selection_handoff(snapshot, locator)

    note = _note(0, 1.0)
    duplicate = PreviewEventLocatorState(
        instrument="lead",
        position_seconds=1.0,
        tolerance_seconds=0.0,
        match_kind="overlap",
        candidates=[
            PreviewEventLocatorCandidate(
                selection_id="lead:0",
                event_index=0,
                distance_seconds=0.0,
                event=note,
            ),
            PreviewEventLocatorCandidate(
                selection_id="lead:0",
                event_index=0,
                distance_seconds=0.0,
                event=note.model_copy(deep=True),
            ),
        ],
    )
    with pytest.raises(ValueError, match="duplicate"):
        build_preview_selection_handoff(snapshot, duplicate)

    inconsistent = PreviewEventLocatorState(
        instrument="lead",
        position_seconds=9.0,
        tolerance_seconds=0.0,
        match_kind="none",
        candidates=[
            PreviewEventLocatorCandidate(
                selection_id="lead:0",
                event_index=0,
                distance_seconds=8.0,
                event=note,
            )
        ],
    )
    with pytest.raises(ValueError, match="marked none"):
        build_preview_selection_handoff(snapshot, inconsistent)
