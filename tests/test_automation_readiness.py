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


def test_status_rejects_active_change_continuation_mismatch() -> None:
    checker = _load_checker()
    status = deepcopy(checker.load_status())
    status["active_change"] = {"pr_number": 404}
    status["next_continuation"]["active_pr_number"] = 403

    with pytest.raises(
        RuntimeError,
        match="active_change.pr_number must match next_continuation.active_pr_number",
    ):
        checker.check_status_contract(status)


def test_status_rejects_continuation_pr_without_active_change() -> None:
    checker = _load_checker()
    status = deepcopy(checker.load_status())
    status["active_change"] = None
    status["next_continuation"]["active_pr_number"] = 404

    with pytest.raises(
        RuntimeError,
        match="next_continuation.active_pr_number must be null",
    ):
        checker.check_status_contract(status)
