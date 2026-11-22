"""Canonical next-62 admission: merged PR+exact-head CI, not checkbox optimism."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from rocksmith_cdlc_generator.slice_queue_integrity import GROUP_COUNTS, parse_slice_queue
from rocksmith_cdlc_generator.slice_readiness import (
    SliceReadinessError, classify_queue, item_fingerprint, queue_fingerprint,
    validate_contract, verified_completion_ids,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "engineering" / "rocksmith-slice-dependencies.json"


def _contract() -> dict:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    # Keep the test issue synthetic. The receipt fingerprints must bind to
    # its synthetic title/criteria, not the separately reviewed live issue.
    completed = {receipt["slice"] for receipt in contract["receipts"]}
    records = parse_slice_queue(_issue_body(completed))
    by_number = {r.number: r for r in records}
    contract["reviewed_queue_git_blob_sha"] = queue_fingerprint(records)
    for receipt in contract["receipts"]:
        receipt["reviewed_item_sha256"] = item_fingerprint(by_number[receipt["slice"]])
    return contract


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


def _fake_github(contract: dict, *, broken: str = "", broken_pr: int | None = None):
    receipts: dict[int, list[dict]] = {}
    for receipt in contract["receipts"]:
        receipts.setdefault(receipt["pr"], []).append(receipt)
    def mode_for(pr: int | None) -> str:
        return broken if broken_pr is None or broken_pr == pr else ""

    def fetch(path: str):
        if path.startswith("/pulls/"):
            pr_num = int(path.split("/")[-1])
            receipt = receipts[pr_num][0]
            scenario = mode_for(pr_num)
            return {
                "number": pr_num,
                "state": "closed",
                "merged_at": "2026-11-21T23:00:00Z",
                "merge_commit_sha": ("0" * 40 if scenario == "merge_sha" else receipt["merge_sha"]),
                "head": {"sha": ("1" * 40 if scenario == "head" else receipt["head_sha"])},
            }
        if path.startswith("/commits/"):
            head = path.split("/")[2]
            related_pr = next((p for p, rows in receipts.items() if rows[0]["head_sha"] == head), None)
            scenario = mode_for(related_pr)
            jobs = [
                {"id": 100 + i, "name": name, "status": "completed",
                 "conclusion": "success", "head_sha": head,
                 "app": {"slug": "github-actions"}}
                for i, name in enumerate(contract["required_check_jobs"])
                if not (scenario == "missing_windows" and name == "Windows desktop app")
            ]
            if scenario == "failed_python":
                jobs[0]["conclusion"] = "failure"
            if scenario in {"duplicate_checks", "old_success_new_failure",
                          "old_failure_new_success", "newer_pending"}:
                extra = deepcopy(jobs[0])
                extra["id"] = 1000
                if scenario == "old_success_new_failure":
                    extra["conclusion"] = "failure"
                if scenario == "old_failure_new_success":
                    jobs[0]["conclusion"] = "failure"
                if scenario == "newer_pending":
                    extra["status"] = "in_progress"
                    extra["conclusion"] = None
                # API response order is deliberately adversarial.
                jobs.insert(0, extra)
            if scenario == "partial_checks":
                return {"total_count": len(jobs) + 1, "check_runs": jobs}
            return {"total_count": len(jobs), "check_runs": jobs}
        raise AssertionError(f"Unexpected live proof API call: {path}")
    return fetch


def test_contract_covers_every_id_and_has_no_cycles():
    contract = _contract()
    validate_contract(contract)
    assert [r["slice"] for r in contract["rules"]] == list(range(1, 63))
    assert len(contract["receipts"]) == 21
    assert len({r["slice"] for r in contract["receipts"]}) == 21


def test_verified_merge_proof_unlocks_one_specific_next_slice():
    contract = _contract()
    done = {r["slice"] for r in contract["receipts"]}
    body = _issue_body(done)
    records = parse_slice_queue(body)
    proof = verified_completion_ids(contract, records, _fake_github(contract))
    assert proof == frozenset(done)
    report = classify_queue(body, contract, proof)
    assert report["next_slice_number"] == 31  # Long-window octave leakage negatives; prerequisite slices 29 and 30 verified
    assert 10 in report["verified_completed_numbers"]
    assert 21 in report["verified_completed_numbers"]
    assert 28 in report["verified_completed_numbers"]
    assert 11 in report["blocked_numbers"]  # No independently authorized Windows network sandbox
    assert 12 in report["blocked_numbers"]  # Depends on #11
    assert 31 in report["ready_numbers"]  # Negative-control Bass octave test after #798
    assert report["auto_execution_authorized"] is False
    assert report["model_execution_authorized"] is False
    assert report["musical_pass_proven"] is False


@pytest.mark.parametrize("broken", [
    "merge_sha", "head", "missing_windows", "failed_python",
    "partial_checks", "old_success_new_failure", "newer_pending",
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
    row18 = next(r for r in report["details"] if r["slice"] == 18)
    assert row18["status"] == "BLOCKED"
    assert {9, 10}.issubset(set(row18["missing_slices"]))
    assert 9 in report["checked_but_unverified_numbers"]


def test_checked_box_without_pr_receipt_does_not_unlock_dependency():
    contract = _contract()
    contract["receipts"] = [r for r in contract["receipts"] if r["slice"] != 10]
    done = {r["slice"] for r in _contract()["receipts"]}
    body = _issue_body(done)
    verified = verified_completion_ids(contract, parse_slice_queue(body), _fake_github(contract))
    report = classify_queue(body, contract, verified)
    assert 10 in report["checked_but_unverified_numbers"]
    assert 10 in next(r for r in report["details"] if r["slice"] == 18)["missing_slices"]


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
        (lambda c: c["receipts"][0].update(reviewed_item_sha256="wrong"),
         "MERGE_RECEIPT_INVALID"),
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
    # The real director loads reviewed live-issue hashes from disk. Inject
    # the same independently reviewed contract, re-bound to THIS synthetic
    # test issue, rather than silently weakening production hash checks.
    original_load = director.load
    monkeypatch.setattr(
        director, "load",
        lambda path, default: contract if path == director.SLICE_DEPENDENCIES
        else original_load(path, default),
    )
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
    assert policy["next_slice_number"] == 31
    assert policy["advisory_only"] is True
    assert evidence["model_execution_authorized"] is False


def test_director_blocks_issue_edited_during_live_merge_verification(monkeypatch):
    from engineering import execution_director as director

    contract = _contract()
    original_load = director.load
    monkeypatch.setattr(
        director, "load",
        lambda path, default: contract if path == director.SLICE_DEPENDENCIES
        else original_load(path, default),
    )
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


def test_completed_task_rewrite_invalidates_old_verified_merge_proof():
    contract = _contract()
    done = {receipt["slice"] for receipt in contract["receipts"]}
    original = _issue_body(done)
    verified_before = verified_completion_ids(
        contract, parse_slice_queue(original), _fake_github(contract)
    )
    assert 9 in verified_before
    # Checkbox, PR merge and CI all still match, but the criterion changed.
    mutated = original.replace(
        "Exact-head reviewed acceptance test for item 9.",
        "New acceptance criterion requires different evidence for item 9.",
    )
    # A changed acceptance rule requires graph review even before checking
    # individual completed-item receipts; previous CI cannot authorize it.
    with pytest.raises(SliceReadinessError, match="QUEUE_CONTENT_REVISION_CHANGED"):
        verified_completion_ids(
            contract, parse_slice_queue(mutated), _fake_github(contract)
        )
    with pytest.raises(SliceReadinessError, match="QUEUE_CONTENT_REVISION_CHANGED"):
        classify_queue(mutated, contract, verified_before)


def test_repository_receipt_bound_to_actual_reviewed_item_text():
    from rocksmith_cdlc_generator.slice_queue_integrity import SliceRecord
    raw = json.loads(CONTRACT.read_text(encoding="utf-8"))
    nine = next(r for r in raw["receipts"] if r["slice"] == 9)
    canonical = SliceRecord(
        number=9, group="A", completed=True,
        title="Windows Job Object containment",
        acceptance="OS-enforced child-tree memory/process cap with termination proof",
    )
    assert nine["reviewed_item_sha256"] == item_fingerprint(canonical)


def test_checkbox_progress_does_not_stale_reviewed_task_semantics():
    contract = _contract()
    before = parse_slice_queue(_issue_body({9}))
    after = parse_slice_queue(_issue_body({9, 10}))
    assert queue_fingerprint(before) == queue_fingerprint(after)
    assert contract["reviewed_queue_git_blob_sha"] == queue_fingerprint(before)


def test_reviewed_queue_revision_missing_or_mismatched_blocks_instead_of_guessing():
    contract = _contract()
    body = _issue_body({9})
    del contract["reviewed_queue_git_blob_sha"]
    with pytest.raises(SliceReadinessError, match="REVIEWED_QUEUE_REVISION_MISSING"):
        classify_queue(body, contract, frozenset())
    contract = _contract()
    contract["reviewed_queue_git_blob_sha"] = "0" * 40
    with pytest.raises(SliceReadinessError, match="QUEUE_CONTENT_REVISION_CHANGED"):
        classify_queue(body, contract, frozenset())


def test_live_repository_receipt_graph_has_sha_format():
    raw = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert len(raw["reviewed_queue_git_blob_sha"]) == 40
    assert len(raw["receipts"]) == 21
    assert all(len(x["reviewed_item_sha256"]) == 64 for x in raw["receipts"])


@pytest.mark.parametrize("scenario", ["duplicate_checks", "old_failure_new_success"])
def test_latest_successful_ci_run_wins_even_if_older_attempt_was_repeated(scenario):
    contract = _contract()
    done = {receipt["slice"] for receipt in contract["receipts"]}
    body = _issue_body(done)
    confirmed = verified_completion_ids(
        contract, parse_slice_queue(body),
        _fake_github(contract, broken=scenario),
    )
    assert confirmed == frozenset(done)
    report = classify_queue(body, contract, confirmed)
    assert report["next_slice_number"] == 31


@pytest.mark.parametrize(("slice_id", "pr", "head", "merge", "title", "criterion"), [
    (10, 807, "826274daa9348921ef190e45833b9746bb81e9eb",
     "0d3be0f716847f34f7f83b662a90c08f906df260",
     "Child-tree/GPU memory evidence", "Peak total and GPU usage measured or reported unavailable"),
    (20, 808, "67730eb63c41fe1f330c693fb3c35b4bde548b06",
     "abfb5a9f2b147133a8f93dad85ec4e3756eefed5",
     "Minimal model model-card comparison", "Candidate size, family, rights and constraints are documented"),
    (21, 810, "80805fcb6f414c2d796b0be04f877c169adcb9ec",
     "2fd6bd3c1451d28bbadf61d2231f84457dde5ad1",
     "Host concurrency admission", "Model run deferred while unrelated workloads reduce RAM"),
    (28, 812, "dc3c7392db0c99850890d77b2b51f03e7ce1f076",
     "42b9d2842eb46f80ab6d6ecd79e6348fb0db7395",
     "Unrelated/percussion-only negatives",
     "No Bass note trust is promoted from silence/drums alone"),
    (56, 806, "184f8b35f38618b1d7b91ac618a310016afe5ae0",
     "ac478dce644cbd85db4a8083b97691253e56c2b7",
     "Blocked/ready dependency state", "Dispatcher chooses only work with proven prerequisite evidence"),
])
def test_reconciled_receipt_binds_independent_pr_and_reviewed_acceptance(
    slice_id: int, pr: int, head: str, merge: str, title: str, criterion: str,
):
    from rocksmith_cdlc_generator.slice_queue_integrity import SliceRecord
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    receipt = next(x for x in contract["receipts"] if x["slice"] == slice_id)
    assert receipt["pr"] == pr
    assert receipt["head_sha"] == head
    assert receipt["merge_sha"] == merge
    reviewed = SliceRecord(
        number=slice_id, title=title, acceptance=criterion,
        group="A" if slice_id == 10 else "B" if slice_id == 20 else "C" if slice_id == 28 else "F",
        completed=True,
    )
    assert receipt["reviewed_item_sha256"] == item_fingerprint(reviewed)


@pytest.mark.parametrize(("slice_id", "pr", "downstream"), [
    (10, 807, 18), (20, 808, 22), (56, 806, 62),
])
@pytest.mark.parametrize("failure", ["missing_windows", "newer_pending", "head", "merge_sha"])
def test_reconciled_pr_failure_blocks_only_its_own_receipt_dependencies(
    slice_id: int, pr: int, downstream: int, failure: str,
):
    contract = _contract()
    completed = {x["slice"] for x in contract["receipts"]}
    body = _issue_body(completed)
    proven = verified_completion_ids(
        contract, parse_slice_queue(body),
        _fake_github(contract, broken=failure, broken_pr=pr),
    )
    assert slice_id not in proven
    assert {10, 20, 56}.difference({slice_id}).issubset(proven)
    report = classify_queue(body, contract, proven)
    assert slice_id in report["checked_but_unverified_numbers"]
    affected = next(x for x in report["details"] if x["slice"] == downstream)
    assert affected["status"] == "BLOCKED"
    assert slice_id in affected["missing_slices"]
    assert report["model_execution_authorized"] is False


@pytest.mark.parametrize("slice_id", [10, 20, 21, 28, 56])
def test_rewritten_recently_checked_acceptance_refuses_old_proof(slice_id: int):
    contract = _contract()
    done = {receipt["slice"] for receipt in contract["receipts"]}
    original = _issue_body(done)
    needle = f"Exact-head reviewed acceptance test for item {slice_id}."
    mutated = original.replace(needle, f"Different acceptance requires independent evidence for item {slice_id}.")
    assert mutated != original
    with pytest.raises(SliceReadinessError, match="QUEUE_CONTENT_REVISION_CHANGED"):
        verified_completion_ids(contract, parse_slice_queue(mutated), _fake_github(contract))



@pytest.mark.parametrize("failure", ["missing_windows", "newer_pending", "head", "merge_sha"])
def test_slice21_new_receipt_never_borrows_other_workflows(failure: str):
    contract = _contract()
    done = {x["slice"] for x in contract["receipts"]}
    body = _issue_body(done)
    proof = verified_completion_ids(
        contract, parse_slice_queue(body),
        _fake_github(contract, broken=failure, broken_pr=810),
    )
    assert 21 not in proof
    assert {10, 20, 56}.issubset(proof)
    report = classify_queue(body, contract, proof)
    assert 21 in report["checked_but_unverified_numbers"]
    assert report["auto_execution_authorized"] is False
    assert report["model_execution_authorized"] is False



@pytest.mark.parametrize("failure", ["missing_windows", "newer_pending", "head", "merge_sha"])
def test_slice28_real_merge_receipt_fails_closed_per_pr_on_bad_ci(failure: str):
    contract = _contract()
    completed = {receipt["slice"] for receipt in contract["receipts"]}
    body = _issue_body(completed)
    proven = verified_completion_ids(
        contract, parse_slice_queue(body),
        _fake_github(contract, broken=failure, broken_pr=812),
    )
    assert 28 not in proven
    assert {10, 20, 21, 29, 30, 56}.issubset(proven)
    report = classify_queue(body, contract, proven)
    assert 28 in report["checked_but_unverified_numbers"]
    assert report["model_execution_authorized"] is False
    assert report["auto_execution_authorized"] is False
    assert report["next_slice_number"] == 31
