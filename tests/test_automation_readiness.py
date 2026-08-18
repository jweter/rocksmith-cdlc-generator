from __future__ import annotations

import importlib.util
from pathlib import Path


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
