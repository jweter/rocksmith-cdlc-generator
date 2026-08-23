"""Regression coverage for the local quality-preflight whitespace-diff base.

Reproduces the Codex P2 finding on PR #385: the bare ``git diff --check``
form only compares the working tree with the index, so it silently ignores
every staged file and every already-committed branch change -- exactly the
changes that make up a proposed patch by the time someone is about to open
or update a pull request. ``resolve_diff_base()``/``diff_check_command()``
fix this by diffing against the merge-base with the target branch instead.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/quality_preflight.py"


def _load_preflight():
    spec = importlib.util.spec_from_file_location("quality_preflight", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )


def _init_repo_with_main_and_feature_branch(repo: Path) -> str:
    """Build a tiny repo: a `main` tip, then a `feature` branch with a new
    commit. Returns the sha of the `main` tip (the expected merge-base).
    """
    _run_git(["init", "-q"], repo)
    _run_git(["config", "user.email", "test@example.com"], repo)
    _run_git(["config", "user.name", "Test"], repo)
    _run_git(["checkout", "-q", "-b", "main"], repo)

    (repo / "committed.txt").write_text("hello\n", encoding="utf-8")
    _run_git(["add", "committed.txt"], repo)
    _run_git(["commit", "-q", "-m", "initial"], repo)
    main_tip = _run_git(["rev-parse", "HEAD"], repo).stdout.strip()

    _run_git(["checkout", "-q", "-b", "feature"], repo)
    return main_tip


def test_resolve_diff_base_uses_local_main_merge_base(tmp_path: Path) -> None:
    preflight = _load_preflight()
    repo = tmp_path / "repo"
    repo.mkdir()
    main_tip = _init_repo_with_main_and_feature_branch(repo)

    # A committed change on the feature branch -- the bare `git diff --check`
    # form would never see this because it is neither staged nor unstaged
    # relative to the index.
    (repo / "committed.txt").write_text("hello\nbad \n", encoding="utf-8")
    _run_git(["add", "committed.txt"], repo)
    _run_git(["commit", "-q", "-m", "introduce trailing whitespace"], repo)

    base = _run_in_repo(preflight.resolve_diff_base, repo)

    assert base == main_tip


def test_diff_check_command_catches_already_committed_whitespace(
    tmp_path: Path,
) -> None:
    """The exact defect scenario: a whitespace error was already committed
    on this branch (not staged, not unstaged), so it must still be caught.
    """
    preflight = _load_preflight()
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo_with_main_and_feature_branch(repo)

    (repo / "committed.txt").write_text("hello\nbad \n", encoding="utf-8")
    _run_git(["add", "committed.txt"], repo)
    _run_git(["commit", "-q", "-m", "introduce trailing whitespace"], repo)

    command = _run_in_repo(preflight.diff_check_command, repo)
    result = subprocess.run(command, cwd=repo, capture_output=True, text=True, check=False)
    assert result.returncode != 0
    assert "trailing whitespace" in result.stdout

    # The bare pre-fix form only compares the working tree with the index,
    # so it reports nothing wrong even though the same commit is present.
    bare_result = subprocess.run(
        ["git", "diff", "--check"], cwd=repo, capture_output=True, text=True, check=False
    )
    assert bare_result.returncode == 0
    assert bare_result.stdout == ""


def test_resolve_diff_base_falls_back_to_head_without_a_base_branch(
    tmp_path: Path,
) -> None:
    preflight = _load_preflight()
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(["init", "-q"], repo)
    _run_git(["config", "user.email", "test@example.com"], repo)
    _run_git(["config", "user.name", "Test"], repo)
    _run_git(["checkout", "-q", "-b", "solo-branch"], repo)
    (repo / "file.txt").write_text("hello\n", encoding="utf-8")
    _run_git(["add", "file.txt"], repo)
    _run_git(["commit", "-q", "-m", "initial"], repo)

    # Neither "origin/main" nor "main" exists in this repo.
    base = _run_in_repo(preflight.resolve_diff_base, repo)

    assert base == "HEAD"


def _run_in_repo(func, repo: Path):
    """Run ``func`` (a preflight module function that shells out to git)
    with the process cwd temporarily set to ``repo``, since it relies on
    being invoked from within the target git working tree, matching how
    quality_preflight.py itself is always run.
    """
    import os

    previous = Path.cwd()
    os.chdir(repo)
    try:
        return func()
    finally:
        os.chdir(previous)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
