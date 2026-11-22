"""Fail-closed, advisory admission for the single canonical #796 delivery queue.

Do not treat checked boxes, cached status, issue prose, or model guesses as
merge proof. The caller must verify exact-head GitHub checks on each recorded
merged PR. Never executes a slice or grants a local model/network permission.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import re
from typing import Any, Callable

from .slice_queue_integrity import SliceRecord, parse_slice_queue

SHA = re.compile(r"^[0-9a-f]{40}$")
HASH256 = re.compile(r"^[0-9a-f]{64}$")
CODE = re.compile(r"^[A-Z][A-Z0-9_]{3,79}$")
N = 62


class SliceReadinessError(ValueError):
    """No trustworthy next-slice admission can be produced."""


def item_fingerprint(item: SliceRecord) -> str:
    """Bind a merge receipt to the exact reviewed title and criterion."""
    source = f"{item.number:02}\n{item.title}\n{item.acceptance}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def queue_fingerprint(records: tuple[SliceRecord, ...]) -> str:
    """Git blob SHA-1 for reviewed names, criteria and A-F groups, not checkboxes.

    This is the repository's normal Git blob address used as a stale-revision
    sentinel; item receipts separately use SHA-256 for exact content binding.
    """
    text = "\n".join(
        f"{item.number:02}|{item.group}|{item.title}|{item.acceptance}"
        for item in records
    ).encode("utf-8")
    header = f"blob {len(text)}\0".encode("ascii")
    return hashlib.sha1(header + text).hexdigest()


@dataclass(frozen=True)
class SliceEligibility:
    number: int
    status: str
    missing_slices: tuple[int, ...]
    missing_evidence: tuple[str, ...]


def validate_contract(contract: dict[str, Any]) -> None:
    if (not isinstance(contract, dict) or contract.get("schema_version") != 1
            or contract.get("issue_number") != 796):
        raise SliceReadinessError("PREREQUISITE_CONTRACT_VERSION_INVALID")
    if (not isinstance(contract.get("reviewed_queue_git_blob_sha"), str)
            or not SHA.fullmatch(contract["reviewed_queue_git_blob_sha"])):
        raise SliceReadinessError("REVIEWED_QUEUE_REVISION_MISSING")
    rules = contract.get("rules")
    if not isinstance(rules, list) or len(rules) != N:
        raise SliceReadinessError("PREREQUISITE_RULE_COVERAGE_INVALID")
    if [row.get("slice") for row in rules if isinstance(row, dict)] != list(range(1, N + 1)):
        raise SliceReadinessError("PREREQUISITE_RULE_ORDER_INVALID")
    edges: dict[int, list[int]] = {}
    for row in rules:
        node = row["slice"]
        dependencies = row.get("requires_completed")
        external = row.get("requires_external_evidence")
        if (not isinstance(dependencies, list)
                or len(dependencies) != len(set(map(str, dependencies)))
                or any(type(dep) is not int or dep not in range(1, N + 1) or dep == node for dep in dependencies)):
            raise SliceReadinessError("PREREQUISITE_SLICE_LINK_INVALID")
        if (not isinstance(external, list) or any(not isinstance(key, str)
                or not CODE.fullmatch(key) for key in external)
                or len(set(external)) != len(external)):
            raise SliceReadinessError("EXTERNAL_EVIDENCE_KEY_INVALID")
        edges[node] = dependencies

    # A cycle makes every linked item permanently opaque; fail rather than
    # arbitrarily declaring one of the tasks ready.
    seen: set[int] = set()
    visiting: set[int] = set()
    def visit(number: int) -> None:
        if number in visiting:
            raise SliceReadinessError("PREREQUISITE_CYCLE")
        if number in seen:
            return
        visiting.add(number)
        for dependency in edges[number]:
            visit(dependency)
        visiting.remove(number)
        seen.add(number)
    for number in range(1, N + 1):
        visit(number)

    required_checks = contract.get("required_check_jobs")
    if (not isinstance(required_checks, list)
            or not {"Python 3.12 tests", "Windows 3.12 + PSARC bridge",
                    "Windows desktop app"}.issubset(set(required_checks))):
        raise SliceReadinessError("REQUIRED_CHECK_CONTRACT_INVALID")
    receipts = contract.get("receipts")
    if not isinstance(receipts, list):
        raise SliceReadinessError("MERGE_RECEIPTS_MISSING")
    receipt_ids: set[int] = set()
    for row in receipts:
        if not isinstance(row, dict):
            raise SliceReadinessError("MERGE_RECEIPT_INVALID")
        ident, number = row.get("slice"), row.get("pr")
        if (type(ident) is not int or ident not in range(1, N + 1)
                or ident in receipt_ids or type(number) is not int or number <= 0
                or not isinstance(row.get("merge_sha"), str)
                or not SHA.fullmatch(row["merge_sha"])
                or not isinstance(row.get("head_sha"), str)
                or not SHA.fullmatch(row["head_sha"])
                or not isinstance(row.get("reviewed_item_sha256"), str)
                or not HASH256.fullmatch(row["reviewed_item_sha256"])):
            raise SliceReadinessError("MERGE_RECEIPT_INVALID")
        receipt_ids.add(ident)


def verified_completion_ids(
    contract: dict[str, Any],
    records: tuple[SliceRecord, ...],
    github: Callable[[str], Any],
) -> frozenset[int]:
    """Check live PR merges AND required exact-PR-head CI for every receipt.

    Uses GitHub's authenticated repository read API supplied by the director,
    not local issue prose or a stored PASS flag. A changed/missing response
    raises a stable blocker; a checked issue box alone cannot unlock work.
    """
    validate_contract(contract)
    if len(records) != N or [r.number for r in records] != list(range(1, N + 1)):
        raise SliceReadinessError("CANONICAL_QUEUE_INVALID")
    if queue_fingerprint(records) != contract["reviewed_queue_git_blob_sha"]:
        raise SliceReadinessError("QUEUE_CONTENT_REVISION_CHANGED")
    checked = {r.number for r in records if r.completed}
    by_number = {r.number: r for r in records}
    by_pr: dict[int, list[dict]] = defaultdict(list)
    for receipt in contract["receipts"]:
        if (receipt["slice"] in checked
                and receipt["reviewed_item_sha256"] ==
                    item_fingerprint(by_number[receipt["slice"]])):
            by_pr[receipt["pr"]].append(receipt)
    verified: set[int] = set()
    checks_required = set(contract["required_check_jobs"])
    for pr_number, receipts in sorted(by_pr.items()):
        try:
            pr = github(f"/pulls/{pr_number}")
            head = pr["head"]["sha"]
            merged = pr["merge_commit_sha"]
            if (pr.get("merged_at") is None or pr.get("state") != "closed"
                    or pr.get("number") != pr_number):
                continue
            if any(row["head_sha"] != head or row["merge_sha"] != merged
                   for row in receipts):
                continue
            check_payload = github(f"/commits/{head}/check-runs?per_page=100")
            items = check_payload["check_runs"]
            if (not isinstance(items, list) or
                    check_payload.get("total_count") != len(items)):
                continue
            # A past successful check run does not authorize a PR whose
            # latest rerun failed or is pending. Reject duplicate job names
            # altogether rather than picking an arbitrary past success.
            required_rows = [
                item for item in items
                if isinstance(item, dict) and item.get("name") in checks_required
            ]
            if (len(required_rows) != len(checks_required)
                    or {item["name"] for item in required_rows} != checks_required
                    or any(
                        item.get("status") != "completed"
                        or item.get("conclusion") != "success"
                        or item.get("app", {}).get("slug") != "github-actions"
                        or item.get("head_sha") != head
                        for item in required_rows
                    )):
                continue
        except (KeyError, TypeError, ValueError, IndexError, AttributeError):
            continue
        verified.update(row["slice"] for row in receipts)
    return frozenset(verified)


def classify_queue(
    body: str,
    contract: dict[str, Any],
    verified_completed: frozenset[int],
    *,
    externally_verified: frozenset[str] = frozenset(),
) -> dict:
    """Choose earliest proven-unblocked *engineering* candidate; never execute."""
    records = parse_slice_queue(body)
    validate_contract(contract)
    if queue_fingerprint(records) != contract["reviewed_queue_git_blob_sha"]:
        raise SliceReadinessError("QUEUE_CONTENT_REVISION_CHANGED")
    verified_completed = frozenset(verified_completed)
    checked = {record.number for record in records if record.completed}
    if not verified_completed.issubset(checked):
        raise SliceReadinessError("PROOF_FOR_UNCHECKED_SLICE")
    by_number = {record.number: record for record in records}
    by_receipt = {receipt["slice"]: receipt for receipt in contract["receipts"]}
    if any(
        n not in by_receipt
        or by_receipt[n]["reviewed_item_sha256"] != item_fingerprint(by_number[n])
        for n in verified_completed
    ):
        raise SliceReadinessError("STALE_MERGE_PROOF_FOR_REVISED_SLICE")
    rules = {rule["slice"]: rule for rule in contract["rules"]}
    eligibility: list[SliceEligibility] = []
    for item in records:
        if item.completed:
            status = "MERGED_VERIFIED" if item.number in verified_completed else "CHECKED_BUT_MERGE_UNVERIFIED"
            eligibility.append(SliceEligibility(item.number, status, (), ()))
            continue
        rule = rules[item.number]
        missing_slices = tuple(dep for dep in rule["requires_completed"] if dep not in verified_completed)
        missing_evidence = tuple(key for key in rule["requires_external_evidence"]
                                 if key not in externally_verified)
        eligibility.append(SliceEligibility(
            item.number, "BLOCKED" if missing_slices or missing_evidence else "READY_FOR_ENGINEERING",
            missing_slices, missing_evidence,
        ))
    ready = [row.number for row in eligibility if row.status == "READY_FOR_ENGINEERING"]
    blocked = [row.number for row in eligibility if row.status == "BLOCKED"]
    unknown = [row.number for row in eligibility if row.status == "CHECKED_BUT_MERGE_UNVERIFIED"]
    return {
        "schema_version": 1,
        "issue_number": 796,
        "status": "ADVISORY_REQUIREMENTS_ONLY",
        "next_slice_number": ready[0] if ready else None,
        "ready_numbers": ready,
        "blocked_numbers": blocked,
        "checked_but_unverified_numbers": unknown,
        "verified_completed_numbers": sorted(verified_completed),
        "details": [
            {"slice": row.number, "status": row.status,
             "missing_slices": list(row.missing_slices),
             "missing_evidence": list(row.missing_evidence)}
            for row in eligibility if row.status != "MERGED_VERIFIED"
        ],
        "auto_execution_authorized": False,
        "model_execution_authorized": False,
        "musical_pass_proven": False,
        "external_evidence_independently_verified_by_caller": bool(externally_verified),
    }
