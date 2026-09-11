"""Regression test for the preflight-promotion gate's gh CLI repo context.

See docs/engineering/error-resolution-ledger.md ERR-2026-010: the
``verify-promotion-gate`` job in promote-preflight-green.yml runs ``gh``
commands with no checkout step, so the CLI cannot infer the target
repository from a local git clone and every invocation fails with
"fatal: not a git repository". Fail this test if that repo context is
ever dropped again.
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW_PATH = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "promote-preflight-green.yml"
)


def _load_promotion_job() -> dict:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    return workflow["jobs"]["verify-promotion-gate"]


def test_promotion_gate_job_has_no_checkout_step() -> None:
    job = _load_promotion_job()
    steps = job.get("steps", [])
    assert not any(
        isinstance(step, dict) and str(step.get("uses", "")).startswith("actions/checkout")
        for step in steps
    ), (
        "This job has no repository checkout. If a checkout step was added, "
        "the gh CLI repo-context assertion below is no longer required and "
        "this test should be revisited instead of loosened silently."
    )


def test_promotion_gate_job_gives_gh_cli_explicit_repo_context() -> None:
    job = _load_promotion_job()

    job_env = job.get("env", {})
    assert job_env.get("GH_REPO") == "${{ github.repository }}", (
        "verify-promotion-gate has no checkout step, so every `gh` invocation "
        "needs an explicit repository (GH_REPO env or --repo) or it fails "
        "with 'fatal: not a git repository'. See ERR-2026-010."
    )

    for step in job.get("steps", []):
        run = step.get("run", "") if isinstance(step, dict) else ""
        if isinstance(run, str) and run.strip().startswith("gh ") or " gh " in run:
            step_env = step.get("env", {}) if isinstance(step, dict) else {}
            assert "--repo" in run or "GH_REPO" in step_env or "GH_REPO" in job_env, (
                f"step {step.get('name')!r} calls gh without repo context"
            )
