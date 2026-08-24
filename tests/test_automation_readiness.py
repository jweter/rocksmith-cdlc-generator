from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_automation_readiness.py"


def _load_checker():
    spec = importlib.util.spec_from_file_location("automation_readiness", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_automation_readiness_contract_passes() -> None:
    checker = _load_checker()
    checker.check_required_paths()
    status = checker.load_status()
    checker.check_status_contract(status)
    checker.check_workflow_names()
    checker.check_policy_markers()



def test_status_accepts_one_structured_active_pr_source() -> None:
    checker = _load_checker()
    status = deepcopy(checker.load_status())
    status["active_change"] = {"pr_number": 406}

    checker.check_status_contract(status)


def test_status_rejects_legacy_continuation_active_pr_pointer() -> None:
    checker = _load_checker()
    status = deepcopy(checker.load_status())
    status["next_continuation"]["active_pr_number"] = 405

    with pytest.raises(
        RuntimeError,
        match="next_continuation.active_pr_number is forbidden",
    ):
        checker.check_status_contract(status)


def test_status_rejects_legacy_verified_state_active_pr_pointer() -> None:
    checker = _load_checker()
    status = deepcopy(checker.load_status())
    status["verified_repository_state"]["active_pr"] = {"pr_number": 405}

    with pytest.raises(
        RuntimeError,
        match="verified_repository_state.active_pr is forbidden",
    ):
        checker.check_status_contract(status)



@pytest.mark.parametrize(
    "stale_text",
    [
        "PR #999 is open and awaiting merge.",
        "Pull request 999 completed the prior slice.",
    ],
)
def test_status_rejects_pr_references_in_roadmap_queue(stale_text: str) -> None:
    checker = _load_checker()
    status = deepcopy(checker.load_status())
    status["roadmap_issue_queue"]["ordered_items"][0]["action"] = stale_text

    with pytest.raises(
        RuntimeError,
        match="roadmap_issue_queue must not contain pull-request references",
    ):
        checker.check_status_contract(status)


@pytest.mark.parametrize(
    "stale_text",
    [
        "No implementation PR is currently open.",
        "The implementation is pending CI.",
        "The change is awaiting merge.",
    ],
)
def test_status_rejects_current_operational_state_in_roadmap_queue(stale_text: str) -> None:
    checker = _load_checker()
    status = deepcopy(checker.load_status())
    status["roadmap_issue_queue"]["ordered_items"][0]["action"] = stale_text

    with pytest.raises(
        RuntimeError,
        match="roadmap_issue_queue must not contain current operational state",
    ):
        checker.check_status_contract(status)
