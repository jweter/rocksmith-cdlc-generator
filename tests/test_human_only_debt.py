import json
from datetime import datetime, timedelta, timezone

from rocksmith_cdlc_generator.human_only_debt import classify_human_only_item, human_only_debt_payload
from rocksmith_cdlc_generator.private_product_reality import (
    BuildObservation,
    PrivateProductRealityEvidence,
    ProductRealityCheck,
)

COMMIT = "b" * 40
CODES = [
    "build_identity", "audio_beat_grid", "bass_first_event", "lead_first_event", "rhythm_first_event",
    "arrangement_first_event_spread", "shared_timing_transform", "checkpoint_chorus", "psarc_registration",
]


def _evidence(
    items: list[str], *, drop: str = "", status: dict[str, str] | None = None,
    commit_sha: str | None = COMMIT, observed_at_utc: str = "2026-09-14T02:30:00Z",
) -> PrivateProductRealityEvidence:
    checks = [
        ProductRealityCheck(code=code, status=(status or {}).get(code, "PASS"), message=f"private detail {code}")
        for code in CODES if not (drop and code.startswith(drop))
    ]
    statuses = {check.status for check in checks}
    return PrivateProductRealityEvidence(
        scenario_id="synthetic-shared-timing",
        observed_at_utc=observed_at_utc,
        scenario_sha256="a" * 64,
        result="FAIL" if "FAIL" in statuses else "REVIEW_REQUIRED" if "REVIEW_REQUIRED" in statuses else "PASS",
        build=BuildObservation(
            version="test", commit_sha=commit_sha,
            built_at_utc="2026-09-14T02:29:00Z", packaged=False,
        ),
        checks=checks if drop != "*" else [], human_only_acceptance=items,
    )


def _reasons(evidence: PrivateProductRealityEvidence | None, **kwargs: object) -> list[str]:
    kwargs.setdefault("current_commit_sha", COMMIT)
    return human_only_debt_payload(evidence, **kwargs)["blocking_reasons"]  # type: ignore[arg-type,return-value]


def test_current_passing_evidence_surfaces_only_subjective_and_runtime_items() -> None:
    items = [
        "Judge final Rocksmith gameplay feel.",
        "Confirm the package appears in the in-game song list.",
        "Confirm Bass first note lines up with the recording.",
        "Check chorus checkpoint drift stays small.",
    ]
    payload = human_only_debt_payload(_evidence(items), current_commit_sha=COMMIT)
    assert payload["status"] == "HUMAN_ATTENTION_REQUIRED"
    assert payload["items"] == items[:2]
    assert [item["description"] for item in payload["excluded_automated_items"]] == items[2:]
    assert human_only_debt_payload(_evidence([]), current_commit_sha=COMMIT)["status"] == "CLEAR"
    text = json.dumps(payload)
    assert "private detail" not in text and "a" * 64 not in text


def test_missing_stale_or_unverified_evidence_fails_closed_and_withholds_human_debt() -> None:
    stale = human_only_debt_payload(_evidence(["Judge feel."]), current_commit_sha="e" * 40)
    assert (stale["status"], stale["items"], stale["deferred_human_item_count"]) == ("BLOCKED", [], 1)
    assert stale["blocking_reasons"] == ["EVIDENCE_STALE_BUILD"]
    assert _reasons(None) == ["EVIDENCE_MISSING"]
    assert _reasons(_evidence([], commit_sha=None)) == ["EVIDENCE_BUILD_UNKNOWN"]
    assert _reasons(_evidence([]), current_commit_sha=None) == ["CURRENT_BUILD_UNKNOWN"]
    now, day = datetime(2026, 9, 20, tzinfo=timezone.utc), timedelta(days=1)
    assert _reasons(_evidence([]), now=now, max_age=day) == ["EVIDENCE_STALE_AGE"]
    assert _reasons(_evidence([], observed_at_utc="yesterday"), now=now, max_age=day) == ["EVIDENCE_TIME_UNKNOWN"]
    review = _evidence(["Judge feel."], status={"lead_first_event": "REVIEW_REQUIRED"})
    assert _reasons(review) == ["AUTOMATED_EVIDENCE_REVIEW_REQUIRED"]
    assert _reasons(_evidence([], status={"psarc_registration": "FAIL"})) == ["AUTOMATED_EVIDENCE_FAIL"]
    assert _reasons(_evidence(["Judge feel."], drop="*")) == ["AUTOMATED_EVIDENCE_EMPTY"]


def test_uncovered_deterministic_or_unclassified_items_block_instead_of_reaching_humans() -> None:
    payload = human_only_debt_payload(
        _evidence(["Check chorus checkpoint drift."], drop="checkpoint_"), current_commit_sha=COMMIT
    )
    assert payload["blocking_reasons"] == ["DETERMINISTIC_ITEM_NOT_COVERED"]
    assert payload["automation_debt_items"][0]["covering_checks"] == {"checkpoint_*": "MISSING"}
    assert _reasons(_evidence(["Look over the project."])) == ["UNCLASSIFIED_ITEM"]


def test_each_arrangement_role_is_judged_by_its_own_evidence() -> None:
    evidence = _evidence([], drop="rhythm_first_event")
    offset = classify_human_only_item("Verify the first playable event offset.", evidence)
    assert offset["covering_checks"] == {"bass_first_event": "PASS", "lead_first_event": "PASS"}
    for role in ("bass", "lead"):
        item = classify_human_only_item(f"Confirm {role.title()} first note timing.", evidence)
        assert (item["roles"], item["covered_by_automation"]) == ([role], True)
    rhythm = classify_human_only_item("Confirm Rhythm first note timing.", evidence)
    assert rhythm["covering_checks"] == {"rhythm_first_event": "MISSING"}
    subjective = classify_human_only_item("Judge Rhythm arrangement playability.", evidence)
    assert (subjective["category"], subjective["roles"]) == ("SUBJECTIVE_MUSICAL_JUDGMENT", ["rhythm"])
    assert classify_human_only_item("Judge rhythmic phrasing feel.", evidence)["roles"] == []
