from __future__ import annotations

from rocksmith_cdlc_generator.private_product_reality import (
    BuildObservation,
    PrivateProductRealityEvidence,
    ProductRealityCheck,
    format_private_product_reality_report,
)


def _evidence(*, human_only_acceptance: list[str]) -> PrivateProductRealityEvidence:
    return PrivateProductRealityEvidence(
        scenario_id="synthetic-shared-timing",
        observed_at_utc="2026-09-14T02:30:00Z",
        scenario_sha256="a" * 64,
        result="PASS",
        build=BuildObservation(
            version="test",
            commit_sha="b" * 40,
            built_at_utc="2026-09-14T02:29:00Z",
            packaged=False,
        ),
        checks=[
            ProductRealityCheck(
                code="shared_transform",
                status="PASS",
                message="deterministic timing evidence passed",
            )
        ],
        human_only_acceptance=human_only_acceptance,
    )


def test_report_names_only_explicit_human_acceptance_debt() -> None:
    report = format_private_product_reality_report(
        _evidence(human_only_acceptance=["Judge final Rocksmith gameplay feel."])
    )

    assert "Human-only acceptance debt:" in report
    assert "- Judge final Rocksmith gameplay feel." in report
    assert "deterministic timing evidence passed" in report


def test_report_explicitly_says_when_no_human_acceptance_remains() -> None:
    report = format_private_product_reality_report(_evidence(human_only_acceptance=[]))

    assert "Human-only acceptance debt: none" in report
