from __future__ import annotations

from rocksmith_cdlc_generator.review_queue_summary import (
    ReviewQueueBucket,
    ReviewQueueSummary,
    ReviewReasonCount,
)
from rocksmith_cdlc_generator.review_queue_workspace_ui import (
    format_review_queue_summary,
    format_review_queue_summary_unavailable,
)
from rocksmith_cdlc_generator.source_import import SourceTrustClass


def test_formats_overlapping_review_pressure_deterministically() -> None:
    summary = ReviewQueueSummary(
        total_events=12,
        unresolved_position_events=2,
        reason_counts=[
            ReviewReasonCount(reason="event_review_required", event_count=12),
            ReviewReasonCount(reason="symbolic_unverified", event_count=8),
            ReviewReasonCount(reason="missing_position", event_count=2),
            ReviewReasonCount(reason="tie", event_count=5),
        ],
        buckets=[
            ReviewQueueBucket(
                instrument="lead",
                trust_class=SourceTrustClass.symbolic_unverified,
                event_count=8,
                unresolved_position_count=2,
            ),
            ReviewQueueBucket(
                instrument="rhythm",
                trust_class=SourceTrustClass.user_confirmed,
                event_count=4,
                unresolved_position_count=0,
            ),
        ],
    )

    text = format_review_queue_summary(summary)

    assert text.startswith("12 review-required events · 2 unresolved positions")
    assert "event review required: 12" in text
    assert "symbolic unverified: 8" in text
    assert "tie: 5" in text
    assert "Lead symbolic_unverified: 8" in text
    assert "Rhythm user_confirmed: 4" in text


def test_formats_empty_review_queue() -> None:
    assert format_review_queue_summary(
        ReviewQueueSummary(total_events=0, unresolved_position_events=0)
    ) == "No arrangement events currently require human review."


def test_final_workspace_includes_review_summary_mixin() -> None:
    from rocksmith_cdlc_generator.audio_output_ui import AudioOutputSongWorkspaceWindow
    from rocksmith_cdlc_generator.review_queue_workspace_ui import ReviewQueueWorkspaceMixin

    assert issubclass(AudioOutputSongWorkspaceWindow, ReviewQueueWorkspaceMixin)


def test_summary_failure_is_sanitized_and_actionable() -> None:
    error = RuntimeError(r"C:\\Users\\tester\\private-project\\score.gp5 could not be read")

    text = format_review_queue_summary_unavailable(error)

    assert text.startswith("⚠ REVIEW SUMMARY UNAVAILABLE")
    assert "Review-required events remain unchanged" in text
    assert "Refresh the workspace to retry" in text
    assert "RuntimeError" in text
    assert "private-project" not in text
    assert "score.gp5" not in text
