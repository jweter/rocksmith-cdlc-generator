from __future__ import annotations

import json

from rocksmith_cdlc_generator.validation import (
    ReviewItem,
    ValidationReport,
    _workspace_review_queue,
    write_review_artifacts,
)


def _warning(time_seconds: float) -> ReviewItem:
    return ReviewItem(
        code="source_pitch_conflict",
        severity="WARNING",
        stage="reconciliation",
        message="Symbolic and audio-derived notes occur together but disagree on MIDI pitch.",
        time_seconds=time_seconds,
        priority=90,
    )


def test_workspace_queue_groups_repeated_warnings_but_keeps_failures_individual() -> None:
    fail_a = ReviewItem(
        code="unmapped_bass_note",
        severity="FAIL",
        stage="mapping",
        message="Bass note 10 has no playable string/fret position.",
        time_seconds=4.0,
        note_index=10,
        priority=100,
    )
    fail_b = fail_a.model_copy(update={"message": "Bass note 11 has no playable string/fret position.", "time_seconds": 5.0, "note_index": 11})
    queue = [fail_a, fail_b, _warning(17.845), _warning(18.849), _warning(21.902)]

    grouped = _workspace_review_queue(queue)

    assert len(grouped) == 3
    assert sum(item.severity == "FAIL" for item in grouped) == 2
    warning = next(item for item in grouped if item.severity == "WARNING")
    assert warning.code == "source_pitch_conflict"
    assert warning.time_seconds == 17.845
    assert "3 occurrences" in warning.message
    assert "disagree on MIDI pitch" in warning.message


def test_persisted_workspace_report_is_grouped_while_flags_preserve_all_events(tmp_path) -> None:
    detailed = [_warning(17.845), _warning(18.849), _warning(21.902)]
    report = ValidationReport(
        status="WARNING",
        can_package=True,
        fail_count=0,
        warning_count=3,
        review_queue=detailed,
    )

    paths = write_review_artifacts(report, tmp_path)
    persisted = ValidationReport.model_validate_json(paths["validation"].read_text(encoding="utf-8"))
    flags = json.loads(paths["flags"].read_text(encoding="utf-8"))

    assert persisted.warning_count == 3
    assert persisted.fail_count == 0
    assert len(persisted.review_queue) == 1
    assert "3 occurrences" in persisted.review_queue[0].message
    assert len(flags) == 3
    assert [item["time_seconds"] for item in flags] == [17.845, 18.849, 21.902]
