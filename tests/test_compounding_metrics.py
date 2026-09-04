from __future__ import annotations

from datetime import UTC, datetime

from engineering.compounding_metrics import UNKNOWN, safe_ratio, window_metrics


def test_safe_ratio_rejects_bool_and_zero_denominator() -> None:
    assert safe_ratio(True, 1) == UNKNOWN
    assert safe_ratio(1, False) == UNKNOWN
    assert safe_ratio(1, 0) == UNKNOWN


def test_window_metrics_uses_merge_time_and_cycle_time() -> None:
    pulls = [
        {
            "created_at": "2026-08-01T00:00:00Z",
            "merged_at": "2026-08-02T00:00:00Z",
        },
        {
            "created_at": "2026-08-03T00:00:00Z",
            "merged_at": "2026-08-05T00:00:00Z",
        },
        {
            "created_at": "2026-07-01T00:00:00Z",
            "merged_at": "2026-07-02T00:00:00Z",
        },
    ]
    result = window_metrics(
        pulls,
        datetime(2026, 8, 1, tzinfo=UTC),
        datetime(2026, 9, 1, tzinfo=UTC),
    )
    assert result["merged_prs"] == 2
    assert result["sample_size"] == 2
    assert result["median_pr_cycle_hours"] == 36.0
