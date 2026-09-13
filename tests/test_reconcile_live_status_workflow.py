from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(".github/workflows/reconcile-live-status.yml")


def test_reconciliation_workflow_does_not_create_github_token_pr() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "gh pr create" not in text
    assert "pull-requests: write" not in text
    assert "pull-requests: read" in text
    assert 'gh pr list --head "$BRANCH" --state open' in text
    assert 'if [ -n "$PR_NUMBER" ]; then' in text
    assert "refusing a GITHUB_TOKEN-authenticated push" in text
    assert "Push reconciliation branch for orchestrator promotion" in text
    assert "automation/status-reconcile" in text
    assert "does not create its own PR with GITHUB_TOKEN" in text
