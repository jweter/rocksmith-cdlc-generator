from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.song_preview import PreviewReviewItem, PreviewReviewQueue
from rocksmith_cdlc_generator.song_preview_review_nav import (
    build_review_navigation_from_id,
    build_review_navigation_from_position,
)
from rocksmith_cdlc_generator.source_import import SourceTrustClass


def _item(review_id: str, start_seconds: float) -> PreviewReviewItem:
    instrument, event_index = review_id.split(":")
    return PreviewReviewItem(
        review_id=review_id,
        instrument=instrument,
        part_name=instrument.title(),
        event_index=int(event_index),
        start_seconds=start_seconds,
        duration_seconds=0.25,
        midi=64,
        note_name="E4",
        string_index=0,
        fret=0,
        techniques=["accent"],
        import_confidence=0.5,
        trust_class=SourceTrustClass.symbolic_unverified,
    )


def _queue() -> PreviewReviewQueue:
    return PreviewReviewQueue(
        items=[
            _item("lead:0", 1.0),
            _item("rhythm:0", 2.0),
            _item("bass:0", 3.0),
        ]
    )


def test_navigates_previous_and_next_from_review_id() -> None:
    state = build_review_navigation_from_id(_queue(), "rhythm:0")

    assert state.current_index == 1
    assert state.previous is not None and state.previous.review_id == "lead:0"
    assert state.current.review_id == "rhythm:0"
    assert state.next is not None and state.next.review_id == "bass:0"


def test_navigation_boundaries_do_not_wrap() -> None:
    first = build_review_navigation_from_id(_queue(), "lead:0")
    last = build_review_navigation_from_id(_queue(), "bass:0")

    assert first.previous is None
    assert first.next is not None
    assert last.previous is not None
    assert last.next is None


def test_position_selects_first_item_at_or_after_playhead() -> None:
    state = build_review_navigation_from_position(_queue(), 1.5)

    assert state.current.review_id == "rhythm:0"
    assert state.current_index == 1


def test_position_after_queue_selects_last_item_for_backward_navigation() -> None:
    state = build_review_navigation_from_position(_queue(), 99.0)

    assert state.current.review_id == "bass:0"
    assert state.next is None


def test_navigation_returns_copies_not_queue_objects() -> None:
    queue = _queue()
    state = build_review_navigation_from_id(queue, "rhythm:0")

    state.current.techniques.append("preview-only")
    assert queue.items[1].techniques == ["accent"]


def test_rejects_empty_missing_duplicate_and_unordered_queues() -> None:
    with pytest.raises(ValueError, match="empty"):
        build_review_navigation_from_position(PreviewReviewQueue(), 0.0)

    queue = _queue()
    with pytest.raises(ValueError, match="not found"):
        build_review_navigation_from_id(queue, "lead:99")

    duplicate = PreviewReviewQueue(items=[_item("lead:0", 1.0), _item("lead:0", 2.0)])
    with pytest.raises(ValueError, match="duplicate"):
        build_review_navigation_from_id(duplicate, "lead:0")

    unordered = PreviewReviewQueue(items=[_item("lead:0", 2.0), _item("bass:0", 1.0)])
    with pytest.raises(ValueError, match="not ordered"):
        build_review_navigation_from_position(unordered, 0.0)

    with pytest.raises(ValueError, match="non-negative"):
        build_review_navigation_from_position(queue, -0.1)
