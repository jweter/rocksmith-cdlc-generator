from __future__ import annotations

from rocksmith_cdlc_generator.review_queue_summary import summarize_preview_review_queue
from rocksmith_cdlc_generator.song_preview import PreviewReviewItem, PreviewReviewQueue
from rocksmith_cdlc_generator.source_import import SourceTrustClass


def _item(
    review_id: str,
    instrument: str,
    *,
    trust: SourceTrustClass,
    string_index: int | None,
    fret: int | None,
) -> PreviewReviewItem:
    return PreviewReviewItem(
        review_id=review_id,
        instrument=instrument,
        part_name=instrument.title(),
        event_index=int(review_id.split(":")[1]),
        start_seconds=1.0,
        duration_seconds=0.25,
        midi=64,
        note_name="E4",
        string_index=string_index,
        fret=fret,
        techniques=[],
        import_confidence=1.0,
        trust_class=trust,
    )


def test_summary_groups_by_role_and_trust_without_hiding_events() -> None:
    queue = PreviewReviewQueue(
        items=[
            _item(
                "lead:0",
                "lead",
                trust=SourceTrustClass.symbolic_unverified,
                string_index=0,
                fret=0,
            ),
            _item(
                "lead:1",
                "lead",
                trust=SourceTrustClass.symbolic_unverified,
                string_index=None,
                fret=None,
            ),
            _item(
                "rhythm:0",
                "rhythm",
                trust=SourceTrustClass.symbolic_verified,
                string_index=1,
                fret=2,
            ),
        ]
    )

    summary = summarize_preview_review_queue(queue)

    assert summary.total_events == 3
    assert summary.unresolved_position_events == 1
    assert [
        (
            bucket.instrument,
            bucket.trust_class,
            bucket.event_count,
            bucket.unresolved_position_count,
        )
        for bucket in summary.buckets
    ] == [
        ("lead", SourceTrustClass.symbolic_unverified, 2, 1),
        ("rhythm", SourceTrustClass.symbolic_verified, 1, 0),
    ]
    assert len(queue.items) == 3


def test_empty_queue_has_empty_summary() -> None:
    summary = summarize_preview_review_queue(PreviewReviewQueue())

    assert summary.total_events == 0
    assert summary.unresolved_position_events == 0
    assert summary.buckets == []
