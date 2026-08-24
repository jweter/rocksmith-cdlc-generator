from __future__ import annotations

from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = (
    "AGENTS.md",
    "PROJECT_PLAN.md",
    "README.md",
    "docs/agent-development-policy.md",
    "docs/project-status.yaml",
    "docs/engineering/error-resolution-ledger.md",
    ".github/workflows/ci.yml",
    ".github/workflows/windows-desktop.yml",
    ".github/pull_request_template.md",
)

REQUIRED_WORKFLOWS = {
    "CI": ".github/workflows/ci.yml",
    "Windows Desktop": ".github/workflows/windows-desktop.yml",
}


def fail(message: str) -> None:
    raise RuntimeError(message)


def load_status() -> dict:
    status_path = ROOT / "docs/project-status.yaml"
    try:
        data = yaml.safe_load(status_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        fail(f"Could not parse {status_path.relative_to(ROOT)}: {exc}")
    if not isinstance(data, dict):
        fail("docs/project-status.yaml must contain a YAML mapping")
    return data


def check_required_paths() -> None:
    missing = [path for path in REQUIRED_PATHS if not (ROOT / path).exists()]
    if missing:
        fail(f"Missing automation contract paths: {', '.join(missing)}")


def check_status_contract(status: dict) -> None:
    if status.get("project") != "rocksmith-cdlc-generator":
        fail("project-status.yaml has the wrong project identity")

    product = status.get("product") or {}
    arrangements = set(product.get("arrangements") or [])
    if arrangements != {"bass", "lead", "rhythm"}:
        fail("project-status.yaml must declare bass, lead, and rhythm arrangements")
    if product.get("arrangement_priority") != "equal":
        fail("Bass, Lead, and Rhythm must remain equal product priorities")

    milestone = status.get("current_milestone") or {}
    if milestone.get("roadmap_file") != "PROJECT_PLAN.md":
        fail("PROJECT_PLAN.md must remain the canonical roadmap")

    maintenance = status.get("maintenance_contract") or {}
    for key in (
        "verify_every_scheduled_run",
        "update_when_project_reality_changes",
        "update_in_same_pr_as_relevant_change",
        "stale_status_is_a_defect",
    ):
        if maintenance.get(key) is not True:
            fail(f"maintenance_contract.{key} must be true")

    automation = status.get("automation_contract") or {}
    if automation.get("branch_prefix") != "agent/":
        fail("automation_contract.branch_prefix must be 'agent/'")
    if automation.get("new_roadmap_pr_budget_per_hour") != 1:
        fail("Autonomous roadmap PR budget must remain one per hourly run")

    active_change = status.get("active_change")
    continuation = status.get("next_continuation") or {}
    continuation_pr = continuation.get("active_pr_number")
    if active_change is None:
        if continuation_pr is not None:
            fail("next_continuation.active_pr_number must be null when active_change is null")
    else:
        if not isinstance(active_change, dict):
            fail("active_change must be null or a mapping")
        active_pr = active_change.get("pr_number")
        if not isinstance(active_pr, int) or active_pr <= 0:
            fail("active_change.pr_number must be a positive integer")
        if continuation_pr != active_pr:
            fail("active_change.pr_number must match next_continuation.active_pr_number")

    required = automation.get("required_pr_workflows") or []
    observed = {
        item.get("name"): item.get("file")
        for item in required
        if isinstance(item, dict)
    }
    if observed != REQUIRED_WORKFLOWS:
        fail(
            "automation_contract.required_pr_workflows must exactly declare "
            "CI and Windows Desktop"
        )


def check_workflow_names() -> None:
    for expected_name, relative_path in REQUIRED_WORKFLOWS.items():
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        if f"name: {expected_name}\n" not in text:
            fail(f"{relative_path} must keep workflow name '{expected_name}'")
        if "pull_request:" not in text or "- main" not in text:
            fail(f"{relative_path} must run on pull requests targeting main")


def check_policy_markers() -> None:
    policy = (ROOT / "docs/agent-development-policy.md").read_text(encoding="utf-8")
    required_phrases = (
        "Bass, Lead Guitar, and Rhythm Guitar are equal product targets",
        "Leave the PR for fresh CI",
        "Required merge evidence",
        "Advisory automation and review bots",
    )
    missing = [phrase for phrase in required_phrases if phrase not in policy]
    if missing:
        fail(f"Agent policy is missing required merge/readiness language: {missing}")


def main() -> int:
    try:
        check_required_paths()
        status = load_status()
        check_status_contract(status)
        check_workflow_names()
        check_policy_markers()
    except RuntimeError as exc:
        print(f"AUTOMATION READINESS: FAIL - {exc}", file=sys.stderr)
        return 1

    print("AUTOMATION READINESS: PASS")
    print("Required policy files, status contract, and PR workflows are coherent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
