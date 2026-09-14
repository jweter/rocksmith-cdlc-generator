from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from rocksmith_cdlc_generator.mobile_review_result import (
    append_mobile_review_result,
    build_mobile_review_result,
    read_mobile_review_results,
)
from rocksmith_cdlc_generator.score_source import ArrangementRole


def _report() -> dict[str, str]:
    return {
        "commit": "1" * 40,
        "scenario": "private-timing-review",
        "scenario_sha256": "2" * 64,
        "project_recording_sha256": "3" * 64,
        "tempo_map_sha256": "4" * 64,
    }


def test_review_result_binds_explicit_verdict_to_exact_evidence_identity(tmp_path: Path) -> None:
    history = tmp_path / "mobile-review-history.jsonl"
    record = build_mobile_review_result(
        _report(),
        arrangement=ArrangementRole.bass,
        result="pass",
        notes="human-reviewed derived evidence only",
        reviewed_at_utc="2026-09-14T22:00:00Z",
    )

    assert record.result == "PASS"
    assert record.arrangement == "bass"
    assert record.desktop_product_reality_cleared is False
    assert len(record.identity_sha256) == 64

    append_mobile_review_result(history, record)
    assert read_mobile_review_results(history) == [record]


def test_review_history_is_append_only_and_preserves_fail_before_pass(tmp_path: Path) -> None:
    history = tmp_path / "mobile-review-history.jsonl"
    failed = build_mobile_review_result(
        _report(),
        arrangement=ArrangementRole.lead,
        result="FAIL",
        reviewed_at_utc="2026-09-14T22:00:00Z",
    )
    passed = build_mobile_review_result(
        _report(),
        arrangement=ArrangementRole.lead,
        result="PASS",
        reviewed_at_utc="2026-09-14T22:05:00Z",
    )

    append_mobile_review_result(history, failed)
    append_mobile_review_result(history, passed)

    assert [item.result for item in read_mobile_review_results(history)] == ["FAIL", "PASS"]


def test_review_result_rejects_unknown_or_unbound_authority() -> None:
    report = _report()
    report["tempo_map_sha256"] = "UNKNOWN"

    with pytest.raises(ValueError, match="tempo_map_sha256"):
        build_mobile_review_result(report, arrangement=ArrangementRole.rhythm, result="FLAG")


def test_review_result_rejects_tampered_identity_and_desktop_clearance(tmp_path: Path) -> None:
    history = tmp_path / "mobile-review-history.jsonl"
    record = build_mobile_review_result(
        _report(),
        arrangement=ArrangementRole.rhythm,
        result="FLAG",
        reviewed_at_utc="2026-09-14T22:00:00Z",
    )

    with pytest.raises(ValueError, match="identity digest mismatch"):
        append_mobile_review_result(history, replace(record, identity_sha256="0" * 64))

    with pytest.raises(ValueError, match="cannot clear desktop Product Reality"):
        append_mobile_review_result(history, replace(record, desktop_product_reality_cleared=True))


def test_review_history_fails_closed_on_malformed_existing_history(tmp_path: Path) -> None:
    history = tmp_path / "mobile-review-history.jsonl"
    history.write_text("not-json\n", encoding="utf-8")
    record = build_mobile_review_result(
        _report(),
        arrangement=ArrangementRole.bass,
        result="PASS",
        reviewed_at_utc="2026-09-14T22:00:00Z",
    )

    with pytest.raises(ValueError, match="invalid mobile review history JSON"):
        append_mobile_review_result(history, record)
