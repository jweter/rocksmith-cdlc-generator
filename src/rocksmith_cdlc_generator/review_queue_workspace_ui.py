from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .review_queue_summary import ReviewQueueSummary, summarize_preview_review_queue


def format_review_queue_summary(summary: ReviewQueueSummary) -> str:
    """Render deterministic review pressure without changing review authority."""

    if summary.total_events == 0:
        return "No arrangement events currently require human review."

    reason_counts = ", ".join(
        f"{reason.reason.replace('_', ' ')}: {reason.event_count}"
        for reason in summary.reason_counts
    ) or "no classified reasons"
    bucket_counts = ", ".join(
        f"{bucket.instrument.title()} {bucket.trust_class.value}: {bucket.event_count}"
        for bucket in summary.buckets
    ) or "no arrangement/trust buckets"
    return (
        f"{summary.total_events} review-required events · "
        f"{summary.unresolved_position_events} unresolved positions · "
        f"Reasons: {reason_counts} · By track/trust: {bucket_counts}"
    )


def format_review_queue_summary_unavailable(exc: Exception) -> str:
    """Render a sanitized, fail-closed recovery state for summary failures."""

    return (
        "⚠ REVIEW SUMMARY UNAVAILABLE · Review-required events remain unchanged. "
        "Refresh the workspace to retry. "
        f"Diagnostics: {type(exc).__name__}."
    )


class ReviewQueueWorkspaceMixin:
    """Surface aggregate review pressure before individual event navigation."""

    def _build_arrangement_preview(self) -> None:
        super()._build_arrangement_preview()
        box = ttk.LabelFrame(
            self.arrangement_preview_tab,
            text="Review queue summary",
            padding=8,
        )
        box.pack(fill="x", pady=(8, 0))
        self.review_queue_summary_var = tk.StringVar(
            value="Review summary becomes available after authoritative score fan-out."
        )
        ttk.Label(
            box,
            textvariable=self.review_queue_summary_var,
            wraplength=1050,
            justify="left",
        ).pack(anchor="w")
        ttk.Label(
            box,
            text=(
                "Counts may overlap because one event can require review for more than one reason. "
                "This panel is informational only and does not suppress or accept review items."
            ),
            wraplength=1050,
            justify="left",
        ).pack(anchor="w", pady=(5, 0))

    def refresh(self) -> None:
        super().refresh()
        if getattr(self, "_refresh_failed", False):
            return
        if not hasattr(self, "review_queue_summary_var"):
            return
        try:
            summary = summarize_preview_review_queue(self.preview_review_queue)
        except Exception as exc:
            self.review_queue_summary_var.set(format_review_queue_summary_unavailable(exc))
            return
        self.review_queue_summary_var.set(format_review_queue_summary(summary))
