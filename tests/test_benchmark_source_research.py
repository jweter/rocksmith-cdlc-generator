from __future__ import annotations

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from rocksmith_cdlc_generator.benchmark_source_research import BenchmarkSourceResearchRecord


def _record(**overrides: object) -> BenchmarkSourceResearchRecord:
    payload: dict[str, object] = {
        "benchmark_id": "BMARK-001",
        "finding": "official_commercial_guitar_pro",
        "checked_on": date.today(),
        "evidence_note": "Publisher listing confirms a structured score.",
        "source_page_url": "https://example.com/reference/1",
        "source_title": "Example structured score",
    }
    payload.update(overrides)
    return BenchmarkSourceResearchRecord.model_validate(payload)


def test_found_reference_requires_public_source_metadata() -> None:
    for field in ("source_page_url", "source_title"):
        payload = {
            "benchmark_id": "BMARK-001",
            "finding": "community_guitar_pro",
            "checked_on": date.today(),
            "evidence_note": "Search result identifies a candidate source.",
            "source_page_url": "https://example.com/reference/1",
            "source_title": "Example source",
        }
        payload.pop(field)
        with pytest.raises(ValidationError, match="require source_page_url and source_title"):
            BenchmarkSourceResearchRecord.model_validate(payload)


def test_no_source_state_cannot_carry_source_metadata() -> None:
    with pytest.raises(ValidationError, match="must remain unset"):
        _record(
            finding="no_adequate_source_found",
            source_page_url="https://example.com/reference/1",
            source_title="Example source",
        )


def test_rejects_local_or_non_http_source_locations() -> None:
    for value in ("file:///private/reference.gp", "C:/private/reference.gp"):
        with pytest.raises(ValidationError, match="source_page_url"):
            _record(source_page_url=value)


def test_rejects_non_public_or_embedded_user_source_urls() -> None:
    for value in (
        "http://localhost/reference",
        "http://127.0.0.1/reference",
        "http://10.0.0.8/reference",
        "https://account:secret@example.com/reference",
        "https://intranet/reference",
    ):
        with pytest.raises(ValidationError, match="source_page_url"):
            _record(source_page_url=value)


def test_rejects_unicode_digit_benchmark_ids() -> None:
    for benchmark_id in ("BMARK-٠٠١", "BMARK-１２３"):
        with pytest.raises(ValidationError, match="benchmark_id"):
            _record(benchmark_id=benchmark_id)


def test_rejects_future_check_date() -> None:
    with pytest.raises(ValidationError, match="cannot be in the future"):
        _record(checked_on=date.today() + timedelta(days=1))


def test_rejects_unknown_fields_and_blank_text() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _record(local_path="private/reference.gp")

    with pytest.raises(ValidationError, match="non-whitespace"):
        _record(evidence_note="   ")


def test_record_is_frozen_and_normalizes_text() -> None:
    record = _record(
        evidence_note="  Publisher listing confirms a structured score.  ",
        source_title="  Example structured score  ",
    )

    assert record.evidence_note == "Publisher listing confirms a structured score."
    assert record.source_title == "Example structured score"

    with pytest.raises(ValidationError):
        record.finding = "not_checked"  # type: ignore[misc]
