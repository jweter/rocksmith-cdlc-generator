from __future__ import annotations

import json
from pathlib import Path

from rocksmith_cdlc_generator.validation import (
    ReviewItem,
    ValidationReport,
    summarize_review_queue,
    write_review_artifacts,
)


def _item(
    *,
    code: str,
    severity: str,
    stage: str,
    message: str,
    time_seconds: float | None,
    priority: int,
) -> ReviewItem:
    return ReviewItem(
        code=code,
        severity=severity,
        stage=stage,
        message=message,
        time_seconds=time_seconds,
        priority=priority,
    )


def test_summarize_review_queue_groups_repeated_root_causes_deterministically() -> None:
    items = [
        _item(
            code="unmapped_bass_note",
            severity="FAIL",
            stage="mapping",
            message="Bass note 4 has no playable string/fret position.",
            time_seconds=4.0,
            priority=100,
        ),
        _item(
            code="low_beat_confidence",
            severity="WARNING",
            stage="tempo",
            message="Beat 2 has low confidence (0.20).",
            time_seconds=2.0,
            priority=70,
        ),
        _item(
            code="unmapped_bass_note",
            severity="FAIL",
            stage="mapping",
            message="Bass note 1 has no playable string/fret position.",
            time_seconds=1.0,
            priority=100,
        ),
        _item(
            code="unmapped_bass_note",
            severity="FAIL",
            stage="mapping",
            message="Bass note 3 has no playable string/fret position.",
            time_seconds=3.0,
            priority=100,
        ),
    ]

    groups = summarize_review_queue(items)

    assert [(group.severity, group.stage, group.code, group.count) for group in groups] == [
        ("FAIL", "mapping", "unmapped_bass_note", 3),
        ("WARNING", "tempo", "low_beat_confidence", 1),
    ]
    assert groups[0].first_time_seconds == 1.0
    assert groups[0].example_message.startswith("Bass note 1")


def test_summary_markdown_groups_repeated_items_but_machine_artifacts_keep_all_details(
    tmp_path: Path,
) -> None:
    items = [
        _item(
            code="mapping_pitch_mismatch",
            severity="FAIL",
            stage="mapping",
            message=f"Mapped note {index} string/fret does not reproduce MIDI 64.",
            time_seconds=float(index),
            priority=100,
        )
        for index in range(3)
    ]
    report = ValidationReport(
        status="FAIL",
        can_package=False,
        fail_count=3,
        warning_count=0,
        review_queue=items,
    )

    paths = write_review_artifacts(report, tmp_path)
    summary = paths["summary"].read_text(encoding="utf-8")
    flags = json.loads(paths["flags"].read_text(encoding="utf-8"))
    persisted = json.loads(paths["validation"].read_text(encoding="utf-8"))

    assert "## Review Queue by Root Cause" in summary
    assert "**FAIL × 3** [mapping/mapping_pitch_mismatch]" in summary
    assert "3 occurrences." in summary
    assert summary.count("mapping_pitch_mismatch") == 1
    assert len(flags) == 3
    assert len(persisted["review_queue"]) == 3


def test_empty_review_queue_summary_remains_explicit(tmp_path: Path) -> None:
    report = ValidationReport(
        status="PASS",
        can_package=True,
        fail_count=0,
        warning_count=0,
        review_queue=[],
    )

    summary = write_review_artifacts(report, tmp_path)["summary"].read_text(encoding="utf-8")

    assert "No unresolved review items." in summary
