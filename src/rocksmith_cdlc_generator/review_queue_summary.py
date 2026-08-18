from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .musicxml_multi_import import ArrangementKind
from .song_preview import PreviewReviewQueue
from .source_import import SourceTrustClass

ReviewReason = Literal[
    "event_review_required",
    "symbolic_unverified",
    "missing_position",
    "tie",
]


class ReviewQueueBucket(BaseModel):
    instrument: ArrangementKind
    trust_class: SourceTrustClass
    event_count: int = Field(ge=1)
    unresolved_position_count: int = Field(ge=0)


class ReviewReasonCount(BaseModel):
    reason: ReviewReason
    event_count: int = Field(ge=1)


class ReviewQueueSummary(BaseModel):
    """Read-only aggregate of review pressure without changing review authority."""

    schema_version: int = 2
    total_events: int = Field(ge=0)
    unresolved_position_events: int = Field(ge=0)
    buckets: list[ReviewQueueBucket] = Field(default_factory=list)
    reason_counts: list[ReviewReasonCount] = Field(default_factory=list)


def summarize_preview_review_queue(queue: PreviewReviewQueue) -> ReviewQueueSummary:
    """Group review-required events and expose overlapping review reasons.

    Every queue item already carries an explicit source-level ``review_required`` flag,
    so ``event_review_required`` is always counted. Additional reason counters describe
    facts that coexist with that flag; they are not treated as the cause of queue
    membership. In particular, ``symbolic_unverified`` may be incidental to a tie or
    other independent event-review condition and must not be suppressed merely because
    a whole source track later receives provenance acceptance.

    This summary is informational only. It does not accept source trust, resolve
    positions, suppress queue items, or mutate imported/source artifacts.
    """

    grouped: dict[tuple[ArrangementKind, SourceTrustClass], tuple[int, int]] = {}
    reason_totals: dict[ReviewReason, int] = {
        "event_review_required": 0,
        "symbolic_unverified": 0,
        "missing_position": 0,
        "tie": 0,
    }
    unresolved_total = 0

    for item in queue.items:
        reason_totals["event_review_required"] += 1
        if item.trust_class is SourceTrustClass.symbolic_unverified:
            reason_totals["symbolic_unverified"] += 1
        unresolved = item.string_index is None or item.fret is None
        if unresolved:
            unresolved_total += 1
            reason_totals["missing_position"] += 1
        if "tie" in item.techniques:
            reason_totals["tie"] += 1

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
    reason_order: list[ReviewReason] = [
        "event_review_required",
        "symbolic_unverified",
        "missing_position",
        "tie",
    ]
    reason_counts = [
        ReviewReasonCount(reason=reason, event_count=reason_totals[reason])
        for reason in reason_order
        if reason_totals[reason] > 0
    ]

    return ReviewQueueSummary(
        total_events=len(queue.items),
        unresolved_position_events=unresolved_total,
        buckets=buckets,
        reason_counts=reason_counts,
    )
