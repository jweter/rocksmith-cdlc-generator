"""Strict public GitHub issue #796 slice queue parser and integrity diagnostics.

The queue is a planning contract, NOT authority to run local models, make
unreviewed merges or claim Product Reality PASS. Input is explicitly
provided Markdown; this module does not access GitHub or execute work.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import re

LINE = re.compile(r"^- \[([ x])\] \*\*(\d{2})\. ([^*\n]+)\*\* — (.+)\.$")
GROUP = re.compile(r"^### ([A-F])\. ")
GROUP_COUNTS = {"A": 12, "B": 10, "C": 12, "D": 10, "E": 10, "F": 8}
EXPECTED_SLICES = 62


class SliceQueueIntegrityError(ValueError):
    """Public queue is stale, incomplete, reordered or ambiguous."""


@dataclass(frozen=True)
class SliceRecord:
    number: int
    title: str
    acceptance: str
    group: str
    completed: bool


@dataclass(frozen=True)
class SliceQueueReport:
    schema_version: int
    total_slices: int
    completed_slices: int
    pending_slices: int
    status: str
    pending_numbers: tuple[int, ...]
    completed_numbers: tuple[int, ...]
    external_evidence_required: bool = True
    auto_execution_authorized: bool = False
    musical_pass_proven: bool = False

    def public_dict(self) -> dict:
        return asdict(self)


def parse_slice_queue(body: str, *, expected_count: int = EXPECTED_SLICES) -> tuple[SliceRecord, ...]:
    """Fail closed on duplicate, missing, malformed and ambiguous task IDs.

    A Markdown checkbox is an owner's declared status, not independently
    verified proof of a merge. Caller must inspect exact-head PR evidence.
    """
    if not isinstance(body, str) or not body.strip():
        raise SliceQueueIntegrityError("QUEUE_INPUT_MISSING")
    if expected_count != EXPECTED_SLICES:
        raise SliceQueueIntegrityError("UNAUTHORIZED_QUEUE_LENGTH")
    group = None
    collected: list[SliceRecord] = []
    seen: set[int] = set()
    group_counts: dict[str, int] = {key: 0 for key in GROUP_COUNTS}
    for line in body.splitlines():
        heading = GROUP.fullmatch(line.strip())
        if heading:
            group = heading.group(1)
            continue
        if not line.startswith("- ["):
            continue
        # Treat any unchecked/malformed task-like line as a bad queue, never
        # skip it and silently report 62 verified entries from elsewhere.
        if line.startswith("- [ ] **") or line.startswith("- [x] **"):
            matched = LINE.fullmatch(line)
            if not matched:
                raise SliceQueueIntegrityError("MALFORMED_SLICE_ENTRY")
            checked, raw_id, title, criterion = matched.groups()
            number = int(raw_id)
            if number in seen:
                raise SliceQueueIntegrityError("DUPLICATE_SLICE_ID")
            if group not in GROUP_COUNTS:
                raise SliceQueueIntegrityError("SLICE_WITHOUT_VALID_GROUP")
            if (not title.strip() or len(title.strip()) < 5
                    or not criterion.strip() or len(criterion.strip()) < 12):
                raise SliceQueueIntegrityError("SLICE_ACCEPTANCE_TOO_WEAK")
            group_counts[group] += 1
            collected.append(
                SliceRecord(number, title.strip(), criterion.strip(), group, checked == "x")
            )
            seen.add(number)
    if len(collected) != expected_count:
        raise SliceQueueIntegrityError("SLICE_COUNT_MISMATCH")
    if [item.number for item in collected] != list(range(1, expected_count + 1)):
        raise SliceQueueIntegrityError("SLICE_ID_SEQUENCE_MISMATCH")
    if group_counts != GROUP_COUNTS:
        raise SliceQueueIntegrityError("SLICE_GROUP_QUOTA_MISMATCH")
    expected_groups = (
        ["A"] * GROUP_COUNTS["A"] + ["B"] * GROUP_COUNTS["B"]
        + ["C"] * GROUP_COUNTS["C"] + ["D"] * GROUP_COUNTS["D"]
        + ["E"] * GROUP_COUNTS["E"] + ["F"] * GROUP_COUNTS["F"]
    )
    if [item.group for item in collected] != expected_groups:
        raise SliceQueueIntegrityError("SLICE_GROUP_ORDER_MISMATCH")
    return tuple(collected)


def inspect_slice_queue(body: str) -> SliceQueueReport:
    records = parse_slice_queue(body)
    completed = tuple(item.number for item in records if item.completed)
    remaining = tuple(item.number for item in records if not item.completed)
    return SliceQueueReport(
        schema_version=1, total_slices=EXPECTED_SLICES,
        completed_slices=len(completed), pending_slices=len(remaining),
        status="QUEUE_STRUCTURALLY_VALID_NOT_PROOF_OF_MERGE",
        pending_numbers=remaining, completed_numbers=completed,
    )
