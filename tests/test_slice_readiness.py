"""Canonical next-62 admission: merged PR+exact-head CI, not checkbox optimism."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from rocksmith_cdlc_generator.slice_queue_integrity import GROUP_COUNTS, parse_slice_queue
from rocksmith_cdlc_generator.slice_readiness import (
    SliceReadinessError, classify_queue, validate_contract, verified_completion_ids,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "engineering" / "rocksmith-slice-dependencies.json"


def _contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _issue_body(completed: set[int] | None = None) -> str:
    completed = set(completed or ())
    lines = ["# Verified public next-62 tracker"]
    number = 0
    for letter, count in GROUP_COUNTS.items():
        lines.append(f"### {letter}. Category")
        for _ in range(count):
            number += 1
            check = "x" if number in completed else " "
            lines.append(
                f"- [{check}] **{number:02}. Concrete engineering slice {number}**"
                f" — Exact-head reviewed acceptance test for item {number}."
            )
    return "\n".join(lines)


def _fake_github(contract: dict, *, broken: str = ""):
    receipts: dict[int, list[dict]] = {}
    for receipt in contract["receipts"]:
        receipts.setdefault(receipt["pr"], []).append(receipt)
    def fetch(path: str):
        if path.startswith("/pulls/"):
            pr_num = int(path.split("/")[-1])
            receipt = receipts[pr_num][0]
            return {
                "number": pr_num,
                "state": "closed",
                "merged_at": "2026-11-21T23:00:00Z",
                "merge_commit_sha": ("0" * 40 if broken == "merge_sha" else receipt["merge_sha"]),
                "head": {"sha": ("1" * 40 if broken == "head" else receipt["head_sha"])},
            }
        if path.startswith("/commits/"):
            head = path.split("/")[2]
            jobs = [
                {"name": name, "status": "completed", "conclusion": "success",
                 "head_sha": head, "app": {"slug": "github-actions"}}
                for name in contract["required_check_jobs"]
                if not (broken == "missing_windows" and name == "Windows desktop app")
            ]
            if broken == "failed_python":
                jobs[0]["conclusion"] = "failure"
            if broken == "partial_checks":
                return {"total_count": len(jobs) + 1, "check_runs": jobs}
            return {"total_count": len(jobs), "check_runs": jobs}
        raise AssertionError(f"Unexpected live proof API call: {path}")
    return fetch


def test_contract_covers_every_id_and_has_no_cycles():
    contract = _contract()
    validate_contract(contract)
    assert [r["slice"] for r in contract["rules"]] == list(range(1, 63))
    assert len(contract["receipts"]) == 16
    assert len({r["slice"] for r in contract["receipts"]}) == 16


def test_verified_merge_proof_unlocks_one_specific_next_slice():
    contract = _contract()
    done = {r["slice"] for r in contract["receipts"]}
    body = _issue_body(done)
    records = parse_slice_queue(body)
    proof = verified_completion_ids(contract, records, _fake_github(contract))
    assert proof == frozenset(done)
    report = classify_queue(body, contract, proof)
    assert report["next_slice_number"] == 10  # Job-tree/GPU accounting after merged #801
    assert 10 in report["ready_numbers"]
    assert 11 in report["blocked_numbers"]  # No independently authorized Windows network sandbox
    assert 12 in report["blocked_numbers"]  # Depends on #11
    assert 31 in report["ready_numbers"]  # Negative-control Bass octave test after #798
    assert report["auto_execution_authorized"] is False
    assert report["model_execution_authorized"] is False
    assert report["musical_pass_proven"] is False


@pytest.mark.parametrize("broken", [
    "merge_sha", "head", "missing_windows", "failed_python", "partial_checks",
])
def test_missing_or_stale_exact_head_proof_never_unlocks_dependency(broken: str):
    contract = _contract()
    done = {r["slice"] for r in contract["receipts"]}
    body = _issue_body(done)
    confirmed = verified_completion_ids(
        contract, parse_slice_queue(body), _fake_github(contract, broken=broken)
    )
    assert 9 not in confirmed
    report = classify_queue(body, contract, confirmed)
    row10 = next(r for r in report["details"] if r["slice"] == 10)
    assert row10["status"] == "BLOCKED"
    assert 9 in row10["missing_slices"]
    assert 9 in report["checked_but_unverified_numbers"]


def test_checked_box_without_pr_receipt_does_not_unlock_dependency():
    contract = _contract()
    contract["receipts"] = [r for r in contract["receipts"] if r["slice"] != 9]
    done = {r["slice"] for r in _contract()["receipts"]}
    body = _issue_body(done)
    verified = verified_completion_ids(contract, parse_slice_queue(body), _fake_github(contract))
    report = classify_queue(body, contract, verified)
    assert 9 in report["checked_but_unverified_numbers"]
    assert 10 not in report["ready_numbers"]


def test_external_evidence_cannot_be_inferred_from_checked_prs():
    contract = _contract()
    body = _issue_body({9})
    report = classify_queue(body, contract, frozenset({9}))
    row11 = next(r for r in report["details"] if r["slice"] == 11)
    assert row11["status"] == "BLOCKED"
    assert "WINDOWS_HOME_NETWORK_SANDBOX_AUTHORIZED" in row11["missing_evidence"]
    row18 = next(r for r in report["details"] if r["slice"] == 18)
    assert "OWNER_APPROVED_OFFLINE_MODEL_PILOT" in row18["missing_evidence"]
    assert "AVAILABLE_RAM_7_GIB" in row18["missing_evidence"]


def test_permissive_checkbox_payload_is_refused():
    contract = _contract()
    with pytest.raises(SliceReadinessError, match="PROOF_FOR_UNCHECKED_SLICE"):
        classify_queue(_issue_body(set()), contract, frozenset({9}))


def test_missing_graph_entry_wrong_id_cycle_and_unsafe_evidence_fail_closed():
    contract = _contract()
    for mutate, code in [
        (lambda c: c["rules"].pop(), "PREREQUISITE_RULE_COVERAGE_INVALID"),
        (lambda c: c["rules"][0].update(slice=2), "PREREQUISITE_RULE_ORDER_INVALID"),
        (lambda c: c["rules"][8].update(requires_completed=[10]), "PREREQUISITE_CYCLE"),
        (lambda c: c["rules"][10].update(requires_external_evidence=["owner says yes"]),
         "EXTERNAL_EVIDENCE_KEY_INVALID"),
        (lambda c: c["receipts"][0].update(head_sha="wrong"), "MERGE_RECEIPT_INVALID"),
    ]:
        damaged = deepcopy(contract)
        mutate(damaged)
        with pytest.raises(SliceReadinessError, match=code):
            validate_contract(damaged)


def test_duplicate_and_unreferenced_source_evidence_not_accepted():
    contract = _contract()
    damaged = deepcopy(contract)
    damaged["receipts"].append(damaged["receipts"][0])
    with pytest.raises(SliceReadinessError, match="MERGE_RECEIPT_INVALID"):
        validate_contract(damaged)


def test_no_private_media_or_path_in_public_decision():
    contract = _contract()
    body = _issue_body({9})
    decision = classify_queue(body, contract, frozenset({9}))
    serialized = json.dumps(decision)
    for forbidden in ("C:\\", ".wav", ".psarc", "audio/", "private/"):
        assert forbidden not in serialized


def test_director_does_not_grant_unverified_new_slice(monkeypatch):
    # The policy bridge must not consult external evidence or Github if a PR
    # already needs servicing, and it must fail closed on an invalid queue.
    from engineering import execution_director as director

    pending = {"state": "SERVICE_EXISTING_WORK", "allow_new_slice": False}
    monkeypatch.setattr(director, "github", lambda _path: (_ for _ in ()).throw(
        AssertionError("No GitHub action permitted while servicing open PR")
    ))
    actual, evidence = director._admit_next_canonical_slice(pending)
    assert actual == pending
    assert actual["allow_new_slice"] is False
    assert evidence["auto_execution_authorized"] is False

    clean = {"state": "EXECUTE_NEXT_SLICE", "allow_new_slice": True}
    policy, evidence = director._admit_next_canonical_slice(clean)
    assert policy["state"] == "HOLD"
    assert policy["allow_new_slice"] is False
    assert evidence["status"] == "BLOCKED_EVIDENCE_INVALID_OR_UNAVAILABLE"


def test_director_takes_only_current_issue_with_independent_git_proof(monkeypatch):
    from engineering import execution_director as director

    contract = _contract()
    done = {r["slice"] for r in contract["receipts"]}
    mock = _fake_github(contract)
    def github(path: str):
        if path == "/issues/796":
            return {"body": _issue_body(done)}
        return mock(path)
    monkeypatch.setattr(director, "github", github)
    clean = {"state": "EXECUTE_NEXT_SLICE", "allow_new_slice": True}
    policy, evidence = director._admit_next_canonical_slice(clean)
    assert policy["state"] == "EXECUTE_NEXT_SLICE"
    assert policy["allow_new_slice"] is True
    assert policy["next_slice_number"] == 10
    assert policy["advisory_only"] is True
    assert evidence["model_execution_authorized"] is False


def test_director_blocks_issue_edited_during_live_merge_verification(monkeypatch):
    from engineering import execution_director as director

    contract = _contract()
    completed = {r["slice"] for r in contract["receipts"]}
    valid_body = _issue_body(completed)
    mock = _fake_github(contract)
    issue_reads = [valid_body, valid_body + "\\n# Changed while checks were in flight"]
    def github(path: str):
        if path == "/issues/796":
            return {"body": issue_reads.pop(0)}
        return mock(path)
    monkeypatch.setattr(director, "github", github)
    policy, report = director._admit_next_canonical_slice({
        "state": "EXECUTE_NEXT_SLICE", "allow_new_slice": True,
    })
    assert policy["state"] == "HOLD"
    assert policy["allow_new_slice"] is False
    assert "next_slice_number" not in policy
    assert report["auto_execution_authorized"] is False
