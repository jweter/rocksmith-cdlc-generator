"""Queue structure cannot drift silently or grant execution authorization."""
from __future__ import annotations

import json

import pytest

from rocksmith_cdlc_generator.slice_queue_integrity import (
    EXPECTED_SLICES, GROUP_COUNTS, SliceQueueIntegrityError,
    inspect_slice_queue, parse_slice_queue,
)


def _issue_body(checked: int = 11) -> str:
    lines = ["# Public next-62 delivery tracker"]
    index = 0
    for letter, total in GROUP_COUNTS.items():
        lines.extend(["", f"### {letter}. Technical category"])
        for _ in range(total):
            index += 1
            marker = "x" if index <= checked else " "
            lines.append(
                f"- [{marker}] **{index:02}. Verified development slice {index}**"
                f" — Independent test and exact-head checked merge for item {index}."
            )
    assert index == 62
    lines += ["", "### Evidence and status", "Completed items must be independently verified."]
    return "\n".join(lines)


def test_valid_exact_62_queue_has_no_authority_to_execute():
    text = _issue_body()
    report = inspect_slice_queue(text)
    assert report.total_slices == EXPECTED_SLICES == 62
    assert report.completed_slices == 11
    assert report.pending_slices == 51
    assert report.completed_numbers == tuple(range(1, 12))
    assert report.pending_numbers == tuple(range(12, 63))
    assert report.status == "QUEUE_STRUCTURALLY_VALID_NOT_PROOF_OF_MERGE"
    assert report.external_evidence_required is True
    assert report.auto_execution_authorized is False
    assert report.musical_pass_proven is False


def test_realistic_completed_toggles_preserve_fixed_order():
    records = parse_slice_queue(_issue_body(checked=0))
    assert len(records) == 62
    assert all(not x.completed for x in records)
    assert records[0].group == "A"
    assert records[12].group == "B"
    assert records[22].group == "C"
    assert records[34].group == "D"
    assert records[44].group == "E"
    assert records[54].group == "F"
    assert inspect_slice_queue(_issue_body(checked=62)).completed_slices == 62


@pytest.mark.parametrize("old,new,code", [
    ("**09.", "**08.", "DUPLICATE_SLICE_ID"),
    ("**09.", "**80.", "SLICE_ID_SEQUENCE_MISMATCH"),
    (" — Independent test and exact-head checked merge for item 9.",
     " - none.", "MALFORMED_SLICE_ENTRY"),
    ("### B. Technical category", "### G. Technical category",
     "SLICE_GROUP_QUOTA_MISMATCH"),
])
def test_invalid_structure_cannot_be_accepted(old: str, new: str, code: str):
    damaged = _issue_body().replace(old, new, 1)
    with pytest.raises(SliceQueueIntegrityError, match=code):
        parse_slice_queue(damaged)


def test_missing_or_duplicate_checkbox_is_blocked():
    original = _issue_body()
    line = "- [ ] **62. Verified development slice 62** — Independent test and exact-head checked merge for item 62."
    assert line in original
    with pytest.raises(SliceQueueIntegrityError, match="SLICE_COUNT_MISMATCH"):
        parse_slice_queue(original.replace(line, ""))
    with pytest.raises(SliceQueueIntegrityError, match="DUPLICATE_SLICE_ID"):
        parse_slice_queue(original + "\n" + line)


def test_short_or_ambiguous_acceptance_text_fails_closed():
    original = _issue_body()
    edited = original.replace(
        "Independent test and exact-head checked merge for item 1.",
        "done.",
    )
    with pytest.raises(SliceQueueIntegrityError, match="SLICE_ACCEPTANCE_TOO_WEAK"):
        parse_slice_queue(edited)


def test_no_content_or_wrong_expected_count_fails_closed():
    with pytest.raises(SliceQueueIntegrityError, match="QUEUE_INPUT_MISSING"):
        parse_slice_queue("")
    with pytest.raises(SliceQueueIntegrityError, match="UNAUTHORIZED_QUEUE_LENGTH"):
        parse_slice_queue(_issue_body(), expected_count=60)


def test_report_never_contains_artifact_or_personal_paths():
    report = inspect_slice_queue(_issue_body())
    encoded = json.dumps(report.public_dict())
    assert "C:\\" not in encoded
    assert "audio/" not in encoded
    assert ".psarc" not in encoded
    assert "owner" not in encoded


def test_cli_reads_explicit_local_copy_without_network_or_work_execution(
    monkeypatch, capsys, tmp_path
):
    import sys
    from rocksmith_cdlc_generator.slice_queue_integrity_cli import main

    path = tmp_path / "queue.md"
    path.write_text(_issue_body(), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "cdlc-slice-queue-validate", "--issue-markdown", str(path),
    ])
    main()
    report = json.loads(capsys.readouterr().out)
    assert report["total_slices"] == 62
    assert report["completed_slices"] == 11
    assert report["auto_execution_authorized"] is False


def test_cli_bad_queue_fails_with_nonzero_safe_diagnostics(monkeypatch, capsys, tmp_path):
    import sys
    from rocksmith_cdlc_generator.slice_queue_integrity_cli import main

    path = tmp_path / "invalid.md"
    path.write_text("not a valid 62-slice issue", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "cdlc-slice-queue-validate", "--issue-markdown", str(path),
    ])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    err = json.loads(capsys.readouterr().err)
    assert err["reason"] == "SLICE_COUNT_MISMATCH"
    assert str(path) not in json.dumps(err)


def test_unrecognized_uppercase_checkbox_is_a_blocking_unexpected_task():
    text = _issue_body()
    extra = (
        "- [X] **62. Duplicate development slice**"
        " — Independent verification required."
    )
    with pytest.raises(SliceQueueIntegrityError, match="MALFORMED_SLICE_ENTRY"):
        parse_slice_queue(text + "\n" + extra)


def test_duplicate_task_title_under_distinct_id_is_not_accepted():
    original = _issue_body()
    a = (
        "- [x] **02. Verified development slice 2**"
        " — Independent test and exact-head checked merge for item 2."
    )
    b = (
        "- [x] **02. Verified development slice 1**"
        " — Independent test and exact-head checked merge for item 1."
    )
    assert a in original
    with pytest.raises(SliceQueueIntegrityError, match="DUPLICATE_SLICE_CONTENT"):
        parse_slice_queue(original.replace(a, b, 1))
