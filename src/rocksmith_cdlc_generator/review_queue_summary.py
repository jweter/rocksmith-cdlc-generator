from __future__ import annotations

from pydantic import BaseModel, Field

from .musicxml_multi_import import ArrangementKind
from .song_preview import PreviewReviewQueue
from .source_import import SourceTrustClass


class ReviewQueueBucket(BaseModel):
    instrument: ArrangementKind
    trust_class: SourceTrustClass
    event_count: int = Field(ge=1)
    unresolved_position_count: int = Field(ge=0)


class ReviewQueueSummary(BaseModel):
    """Read-only aggregate of review pressure without changing review authority."""

    schema_version: int = 1
    total_events: int = Field(ge=0)
    unresolved_position_events: int = Field(ge=0)
    buckets: list[ReviewQueueBucket] = Field(default_factory=list)


def summarize_preview_review_queue(queue: PreviewReviewQueue) -> ReviewQueueSummary:
    """Group review-required events by arrangement and source trust class.

    This summary is informational only. It does not accept source trust, resolve
    positions, suppress queue items, or mutate imported/source artifacts. Its purpose
    is to make systemic review pressure visible before a user is asked to inspect
    individual events.
    """

    grouped: dict[tuple[ArrangementKind, SourceTrustClass], tuple[int, int]] = {}
    unresolved_total = 0

    for item in queue.items:
        unresolved = item.string_index is None or item.fret is None
        if unresolved:
            unresolved_total += 1
        key = (item.instrument, item.trust_class)
        count, unresolved_count = grouped.get(key, (0, 0))
        grouped[key] = (count + 1, unresolved_count + int(unresolved))

    role_order: dict[ArrangementKind, int] = {"lead": 0, "rhythm": 1, "bass": 2}
    buckets = [
        ReviewQueueBucket(
            instrument=instrument,
            trust_class=trust_class,
            event_count=count,
            unresolved_position_count=unresolved_count,
        )
        for (instrument, trust_class), (count, unresolved_count) in sorted(
            grouped.items(),
            key=lambda entry: (
                role_order[entry[0][0]],
                entry[0][1].value,
            ),
        )
    ]

    return ReviewQueueSummary(
        total_events=len(queue.items),
        unresolved_position_events=unresolved_total,
        buckets=buckets,
    )
