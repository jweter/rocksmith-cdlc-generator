from rocksmith_cdlc_generator.human_only_debt import human_only_debt_payload
from rocksmith_cdlc_generator.private_product_reality import (
    BuildObservation,
    PrivateProductRealityEvidence,
    ProductRealityCheck,
)
from rocksmith_cdlc_generator.product_reality_printed_score import (
    PrintedScoreProductRealityEvidence,
)


def _evidence(
    items: list[str],
    *,
    checks: list[ProductRealityCheck] | None = None,
    printed_score_recognition: PrintedScoreProductRealityEvidence | None = None,
) -> PrivateProductRealityEvidence:
    return PrivateProductRealityEvidence(
        scenario_id="synthetic-shared-timing",
        observed_at_utc="2026-09-14T02:30:00Z",
        scenario_sha256="a" * 64,
        result="PASS",
        build=BuildObservation(
            version="test", commit_sha="b" * 40,
            built_at_utc="2026-09-14T02:29:00Z", packaged=False,
        ),
        checks=checks or [],
        human_only_acceptance=items,
        printed_score_recognition=printed_score_recognition,
    )


def test_payload_contains_only_explicit_human_debt() -> None:
    payload = human_only_debt_payload(_evidence(["Judge final Rocksmith gameplay feel."]))
    assert payload["human_attention_required"] is True
    assert payload["item_count"] == 1
    assert payload["items"] == ["Judge final Rocksmith gameplay feel."]
    assert payload["automation_evidence_gaps"] == []


def test_payload_marks_empty_debt_without_inventing_work() -> None:
    payload = human_only_debt_payload(_evidence([]))
    assert payload["human_attention_required"] is False
    assert payload["item_count"] == 0
    assert payload["items"] == []


def test_deterministic_review_required_checks_are_not_human_debt() -> None:
    """A missing/stale automated check is an automation gap, never human-only debt."""
    checks = [
        ProductRealityCheck(
            code="bass_first_event",
            status="REVIEW_REQUIRED",
            message="Current reviewed bass arrangement could not be observed.",
        ),
        ProductRealityCheck(
            code="lead_first_event",
            status="REVIEW_REQUIRED",
            message="Current reviewed lead arrangement could not be observed.",
        ),
        ProductRealityCheck(
            code="rhythm_first_event",
            status="REVIEW_REQUIRED",
            message="Current reviewed rhythm arrangement could not be observed.",
        ),
    ]
    payload = human_only_debt_payload(_evidence([], checks=checks))

    assert payload["items"] == []
    assert payload["human_attention_required"] is False
    assert payload["automation_evidence_gaps"] == [
        "Current reviewed bass arrangement could not be observed.",
        "Current reviewed lead arrangement could not be observed.",
        "Current reviewed rhythm arrangement could not be observed.",
    ]


def test_printed_score_pending_review_is_human_debt() -> None:
    """Every candidate is readable but still awaits human review: a genuine human task."""
    recognition = PrintedScoreProductRealityEvidence(
        status="REVIEW_REQUIRED",
        candidate_page_count=3,
        reviewed_page_count=1,
        unreadable_candidate_count=0,
        message="2 of 3 printed-score recognition candidate page(s) still require human review before promotion.",
    )
    checks = [
        ProductRealityCheck(
            code="printed_score_recognition",
            status="REVIEW_REQUIRED",
            message=recognition.message,
        )
    ]
    payload = human_only_debt_payload(
        _evidence([], checks=checks, printed_score_recognition=recognition)
    )

    assert payload["items"] == [recognition.message]
    assert payload["human_attention_required"] is True
    assert payload["automation_evidence_gaps"] == []


def test_printed_score_unreadable_candidate_is_automation_gap_not_human_debt() -> None:
    """An unreadable candidate file is an automation/evidence defect, not a human task."""
    recognition = PrintedScoreProductRealityEvidence(
        status="REVIEW_REQUIRED",
        candidate_page_count=3,
        reviewed_page_count=0,
        unreadable_candidate_count=1,
        message="1 of 3 printed-score recognition candidate file(s) could not be read or validated.",
    )
    checks = [
        ProductRealityCheck(
            code="printed_score_recognition",
            status="REVIEW_REQUIRED",
            message=recognition.message,
        )
    ]
    payload = human_only_debt_payload(
        _evidence([], checks=checks, printed_score_recognition=recognition)
    )

    assert payload["items"] == []
    assert payload["human_attention_required"] is False
    assert payload["automation_evidence_gaps"] == [recognition.message]
