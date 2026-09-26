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


def _debt_section(report: str) -> list[str]:
    lines = report.splitlines()
    heading_index = next(
        i for i, line in enumerate(lines) if line.startswith("Human-only acceptance debt")
    )
    return lines[heading_index:]


def test_report_names_only_explicit_human_acceptance_debt() -> None:
    report = format_private_product_reality_report(
        _evidence(human_only_acceptance=["Judge final Rocksmith gameplay feel."])
    )

    debt_section = _debt_section(report)
    assert debt_section == [
        "Human-only acceptance debt:",
        "- Judge final Rocksmith gameplay feel.",
    ]
    assert "deterministic timing evidence passed" in report
    assert not any("deterministic timing evidence passed" in line for line in debt_section)


def test_report_explicitly_says_when_no_human_acceptance_remains() -> None:
    report = format_private_product_reality_report(_evidence(human_only_acceptance=[]))

    assert _debt_section(report) == ["Human-only acceptance debt: none"]


def test_report_withholds_human_debt_when_automated_evidence_is_not_pass() -> None:
    evidence = _evidence(
        human_only_acceptance=["Judge final Rocksmith gameplay feel."]
    ).model_copy(update={"result": "FAIL", "checks": [
        ProductRealityCheck(code="bass_first_event", status="FAIL", message="bass is late")
    ]})

    assert _debt_section(format_private_product_reality_report(evidence)) == [
        "Human-only acceptance debt: UNKNOWN (fail closed: automated_evidence_not_pass)"
    ]


def test_report_lists_deterministic_items_as_not_human_debt() -> None:
    report = format_private_product_reality_report(
        _evidence(human_only_acceptance=["Confirm all arrangements are in sync."])
    )

    # The synthetic evidence has no shared_timing_transform check, so the fact is
    # automation debt rather than covered, and never human debt.
    assert _debt_section(report) == [
        "Human-only acceptance debt: none",
        "- not human debt (automation_debt): "
        "Confirm all arrangements are in sync.",
    ]
