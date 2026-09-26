import json

import pytest

from rocksmith_cdlc_generator.human_only_debt import (
    CATEGORY_EXTERNAL_RUNTIME,
    CATEGORY_SUBJECTIVE,
    STATUS_FAIL_CLOSED,
    human_only_debt_payload,
)
from rocksmith_cdlc_generator.private_product_reality import (
    BuildObservation,
    PrivateProductRealityEvidence,
    ProductRealityCheck,
)

_CODES = ["audio_beat_grid", "bass_first_event", "lead_first_event", "rhythm_first_event",
          "arrangement_first_event_spread", "shared_timing_transform", "checkpoint_chorus_drift"]


def _check(code: str, status: str = "PASS", message: str = "synthetic") -> ProductRealityCheck:
    return ProductRealityCheck(code=code, status=status, message=message)


def _evidence(
    items: list[str],
    *,
    checks: list[ProductRealityCheck] | None = None,
    result: str = "PASS",
    commit_sha: str | None = "b" * 40,
) -> PrivateProductRealityEvidence:
    return PrivateProductRealityEvidence(
        scenario_id="synthetic-shared-timing",
        observed_at_utc="2026-09-14T02:30:00Z",
        scenario_sha256="a" * 64,
        result=result,
        build=BuildObservation(
            version="test", commit_sha=commit_sha,
            built_at_utc="2026-09-14T02:29:00Z", packaged=False,
        ),
        checks=[_check(code) for code in _CODES] if checks is None else checks,
        human_only_acceptance=items,
    )


def test_payload_contains_only_explicit_human_debt() -> None:
    payload = human_only_debt_payload(_evidence(["Judge final Rocksmith gameplay feel."]))
    assert payload["human_attention_required"] is True
    assert payload["item_count"] == 1
    assert payload["items"] == ["Judge final Rocksmith gameplay feel."]
    assert payload["categories"] == [CATEGORY_SUBJECTIVE]


def test_payload_marks_empty_debt_without_inventing_work() -> None:
    payload = human_only_debt_payload(_evidence([]))
    assert payload["human_attention_required"] is False
    assert payload["item_count"] == 0
    assert payload["items"] == []


def test_external_runtime_acceptance_is_human_debt_until_automated() -> None:
    payload = human_only_debt_payload(_evidence(["Confirm the package loads in Rocksmith 2014."]))
    assert payload["categories"] == [CATEGORY_EXTERNAL_RUNTIME]


@pytest.mark.parametrize(
    ("item", "reason"),
    [
        ("Check the bass first playable note.", "covered_by_automated_evidence"),
        ("Check chorus checkpoint drift.", "covered_by_automated_evidence"),
        ("Confirm all arrangements are in sync.", "covered_by_automated_evidence"),
        ("Validate the exported XML.", "automation_debt"),
    ],
)
def test_deterministic_items_are_never_human_debt(item: str, reason: str) -> None:
    payload = human_only_debt_payload(_evidence([item]))
    assert payload["human_attention_required"] is False
    assert payload["items"] == []
    assert payload["excluded_items"][0]["reason"] == reason


def test_named_role_fact_requires_that_role_measured_and_roles_stay_independent() -> None:
    checks = [_check(code) for code in _CODES if code != "rhythm_first_event"]
    payload = human_only_debt_payload(_evidence(["Check the rhythm first event."], checks=checks))
    assert payload["excluded_items"][0]["reason"] == "automation_debt"
    assert payload["arrangement_coverage"] == {
        "bass": "PASS", "lead": "PASS", "rhythm": "NOT_OBSERVED",
    }


@pytest.mark.parametrize(
    "item", ["Judge whether timing feels right in game.", "Look at it."]
)
def test_mixed_or_unrecognized_items_fail_closed(item: str) -> None:
    payload = human_only_debt_payload(_evidence([item]))
    assert payload["status"] == STATUS_FAIL_CLOSED
    assert payload["human_attention_required"] is None
    assert payload["items"] == []


@pytest.mark.parametrize(
    ("evidence_kwargs", "expected_commit_sha", "blocker"),
    [
        ({"commit_sha": None}, None, "build_identity_unknown"),
        ({}, "c" * 40, "evidence_stale_build"),
        ({"checks": []}, None, "automated_checks_missing"),
        ({"result": "FAIL", "checks": [_check("bass_first_event", "FAIL")]}, None,
         "automated_evidence_not_pass"),
    ],
)
def test_stale_or_non_pass_evidence_is_never_human_only(
    evidence_kwargs: dict, expected_commit_sha: str | None, blocker: str
) -> None:
    evidence = _evidence(["Judge final Rocksmith gameplay feel."], **evidence_kwargs)
    payload = human_only_debt_payload(evidence, expected_commit_sha=expected_commit_sha)
    assert blocker in payload["evidence_blockers"]
    assert payload["status"] == STATUS_FAIL_CLOSED
    assert payload["human_attention_required"] is None
    assert payload["items"] == []


def test_missing_evidence_fails_closed_without_leaking_private_messages() -> None:
    assert human_only_debt_payload(None)["evidence_blockers"] == ["evidence_missing"]
    message = r"C:\private\song\stems\guitar.wav unavailable"
    evidence = _evidence([], result="REVIEW_REQUIRED",
                         checks=[_check("collection_1", "REVIEW_REQUIRED", message)])
    payload = human_only_debt_payload(evidence)
    assert "private" not in json.dumps(payload)
    assert payload["blocking_check_codes"] == ["collection_1"]
