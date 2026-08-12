from __future__ import annotations

from pydantic import BaseModel, Field

from .song_preview import PreviewReviewItem, PreviewReviewQueue


class PreviewReviewNavigationState(BaseModel):
    """Read-only navigation result for the Song Preview review queue."""

    schema_version: int = 1
    current_index: int = Field(ge=0)
    current: PreviewReviewItem
    previous: PreviewReviewItem | None = None
    next: PreviewReviewItem | None = None


def _copy_item(item: PreviewReviewItem | None) -> PreviewReviewItem | None:
    return item.model_copy(deep=True) if item is not None else None


def build_review_navigation_from_id(
    queue: PreviewReviewQueue,
    review_id: str,
) -> PreviewReviewNavigationState:
    """Return previous/current/next review items around one stable review identifier."""

    if not queue.items:
        raise ValueError("Preview review queue is empty")

    matches = [index for index, item in enumerate(queue.items) if item.review_id == review_id]
    if not matches:
        raise ValueError(f"Review item not found: {review_id}")
    if len(matches) != 1:
        raise ValueError(f"Review queue contains duplicate review id: {review_id}")

    index = matches[0]
    return PreviewReviewNavigationState(
        current_index=index,
        current=queue.items[index].model_copy(deep=True),
        previous=_copy_item(queue.items[index - 1] if index > 0 else None),
        next=_copy_item(queue.items[index + 1] if index + 1 < len(queue.items) else None),
    )


def build_review_navigation_from_position(
    queue: PreviewReviewQueue,
    position_seconds: float,
) -> PreviewReviewNavigationState:
    """Select the first review item at or after a playhead position.

    If the playhead is beyond the final item, the final review item is selected so the
    caller can still navigate backward. Queue order is treated as authoritative and is
    validated as nondecreasing by onset before navigation.
    """

    if position_seconds < 0:
        raise ValueError("Review navigation position must be non-negative")
    if not queue.items:
        raise ValueError("Preview review queue is empty")

    for previous, current in zip(queue.items, queue.items[1:]):
        if current.start_seconds < previous.start_seconds:
            raise ValueError("Preview review queue is not ordered by song position")

    index = next(
        (
            item_index
            for item_index, item in enumerate(queue.items)
            if item.start_seconds >= position_seconds
        ),
        len(queue.items) - 1,
    )
    return PreviewReviewNavigationState(
        current_index=index,
        current=queue.items[index].model_copy(deep=True),
        previous=_copy_item(queue.items[index - 1] if index > 0 else None),
        next=_copy_item(queue.items[index + 1] if index + 1 < len(queue.items) else None),
    )
