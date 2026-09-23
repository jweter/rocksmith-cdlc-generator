from rocksmith_cdlc_generator.human_only_debt import human_only_debt_payload
from rocksmith_cdlc_generator.private_product_reality import (
    BuildObservation,
    PrivateProductRealityEvidence,
)


def _evidence(items: list[str]) -> PrivateProductRealityEvidence:
    return PrivateProductRealityEvidence(
        scenario_id="synthetic-shared-timing",
        observed_at_utc="2026-09-14T02:30:00Z",
        scenario_sha256="a" * 64,
        result="PASS",
        build=BuildObservation(
            version="test", commit_sha="b" * 40,
            built_at_utc="2026-09-14T02:29:00Z", packaged=False,
        ),
        checks=[], human_only_acceptance=items,
    )


def test_payload_contains_only_explicit_human_debt() -> None:
    payload = human_only_debt_payload(_evidence(["Judge final Rocksmith gameplay feel."]))
    assert payload["human_attention_required"] is True
    assert payload["item_count"] == 1
    assert payload["items"] == ["Judge final Rocksmith gameplay feel."]


def test_payload_marks_empty_debt_without_inventing_work() -> None:
    payload = human_only_debt_payload(_evidence([]))
    assert payload["human_attention_required"] is False
    assert payload["item_count"] == 0
    assert payload["items"] == []
