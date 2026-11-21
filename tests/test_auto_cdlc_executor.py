"""Bounded external model-execution contract tests, with no model installed.

The subprocess is simulated; all asserted accuracy is known-truth *test*
infrastructure, not a claim of real upstream audio transcription.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import pytest

from rocksmith_cdlc_generator import auto_cdlc_executor as runner
from rocksmith_cdlc_generator.auto_cdlc_run_cli import build_parser
from rocksmith_cdlc_generator.auto_cdlc_truth import generate_known_truth
from tests.test_auto_cdlc_truth_benchmark import _make_fixture, _upstream_fixture


def _mock_exec(tmp_path, monkeypatch, *, free_ram: float = 12.0, dirty: bool = False,
               version: str = "Python 3.13.9", exit_code: int = 0,
               emit_files: bool = True, virtualenv_symlink: bool = False):
    fixture, _wav, truth = _make_fixture(tmp_path)
    checkout = tmp_path / "external"
    checkout.mkdir()
    (checkout / ".git").mkdir()
    (checkout / "cdlc_bajo.py").write_text("# stable source placeholder", encoding="utf-8")
    python = tmp_path / "python313.exe"
    python.write_bytes(b"test-python-313-stub")
    if virtualenv_symlink:
        if sys.platform == "win32":
            pytest.skip("Windows CI cannot create unprivileged interpreter symlinks")
        alias_dir = tmp_path / "venv" / "bin"
        alias_dir.mkdir(parents=True)
        alias = alias_dir / "python"
        alias.symlink_to(python)
        python = alias
    run_dir = tmp_path / "run"
    arguments = []

    monkeypatch.setattr(runner, "_available_memory_gib", lambda: free_ram)
    monkeypatch.setattr(
        runner.shutil, "disk_usage",
        lambda *_: SimpleNamespace(free=16 * 1024 ** 3)
    )

    original_subprocess_run = runner.subprocess.run

    def fake_run(cmd, **kwargs):
        if cmd[:3] == ["git", "-C", str(checkout)]:
            if cmd[3:] == ["rev-parse", "HEAD"]:
                return SimpleNamespace(stdout=runner._REVIEWED_COMMIT + "\n", stderr="", returncode=0)
            if cmd[3:] == ["status", "--porcelain", "--untracked-files=no"]:
                return SimpleNamespace(stdout=" M cdlc_bajo.py\n" if dirty else "", stderr="", returncode=0)
            raise AssertionError("unexpected git command")
        if cmd == [str(python), "--version"]:
            return SimpleNamespace(stdout=version, stderr="", returncode=0)
        if cmd[0] == str(python) and cmd[1] == str(checkout / "cdlc_bajo.py"):
            arguments.append((cmd, kwargs))
            if exit_code == 0 and emit_files:
                fake_output = _upstream_fixture(tmp_path, truth)
                actual_output = Path(cmd[cmd.index("--salida") + 1]) / "generated"
                shutil.copytree(fake_output, actual_output)
            return SimpleNamespace(stdout="offline synthetic run", stderr="", returncode=exit_code)
        # Our monkeypatch touches the shared subprocess module. Allow the
        # benchmark's unrelated build-identity Git query to run normally.
        return original_subprocess_run(cmd, **kwargs)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    return fixture, checkout, python, run_dir, arguments


def _run(fixture, checkout, python, run_dir, **kwargs):
    return runner.run_pinned_upstream_synthetic(
        fixture, upstream_checkout=checkout,
        python_313_exe=python, run_dir=run_dir,
        confirm_noncommercial=True, **kwargs,
    )


def test_pinned_offline_synthetic_process_generates_hashed_truth_evidence(tmp_path, monkeypatch):
    fixture, checkout, python, run_dir, invocations = _mock_exec(tmp_path, monkeypatch)
    report = _run(fixture, checkout, python, run_dir)
    assert report["status"] == "PASS"
    assert report["synthetic_verdict"] == "PASS"
    assert report["upstream_commit"] == runner._REVIEWED_COMMIT
    assert report["noncommercial_use_confirmed"] is True
    assert report["os_level_network_isolation"] == "NOT_PROVEN"
    assert report["game_installation_changed"] is False
    assert set(["generated_midi_sha256", "generated_svl_sha256", "generated_diagnostic_sha256"]).issubset(report)
    assert len(invocations) == 1
    cmd, kwargs = invocations[0]
    assert "--sin-internet" in cmd and "--sin-actualizar" in cmd
    assert "--sin-psarc" in cmd and "--sin-preguntas" in cmd
    assert kwargs["check"] is False
    assert kwargs["timeout"] == 3600
    assert kwargs["env"]["HF_HUB_OFFLINE"] == "1"
    assert kwargs["env"]["TRANSFORMERS_OFFLINE"] == "1"
    assert json.loads((run_dir / "upstream_run_evidence.json").read_text()) == report
    benchmark = json.loads((run_dir / "benchmark.json").read_text())
    assert benchmark["producer_input_output_binding"] == "UNPROVEN"
    assert benchmark["scope"] == "SYNTHETIC_FIXTURE_ONLY"


def test_available_ram_below_floor_prevents_model_invocation_and_workspace_creation(tmp_path, monkeypatch):
    fixture, checkout, python, run_dir, calls = _mock_exec(tmp_path, monkeypatch, free_ram=4.7)
    with pytest.raises(runner.UpstreamRunError, match="available RAM"):
        _run(fixture, checkout, python, run_dir)
    assert not run_dir.exists()
    assert calls == []


def test_external_source_must_have_exact_reviewed_commit_and_be_clean(tmp_path, monkeypatch):
    fixture, checkout, python, run_dir, calls = _mock_exec(tmp_path, monkeypatch, dirty=True)
    with pytest.raises(runner.UpstreamRunError, match="modified tracked"):
        _run(fixture, checkout, python, run_dir)
    assert not run_dir.exists() and not calls


def test_python_requires_exact_313_version(tmp_path, monkeypatch):
    fixture, checkout, python, run_dir, calls = _mock_exec(tmp_path, monkeypatch, version="Python 3.14.0")
    with pytest.raises(runner.UpstreamRunError, match="3.13"):
        _run(fixture, checkout, python, run_dir)
    assert not run_dir.exists() and not calls


def test_noncommercial_confirmation_required_without_running_preflight(tmp_path, monkeypatch):
    fixture, checkout, python, run_dir, calls = _mock_exec(tmp_path, monkeypatch)
    with pytest.raises(runner.UpstreamRunError, match="noncommercial"):
        runner.run_pinned_upstream_synthetic(
            fixture, upstream_checkout=checkout, python_313_exe=python,
            run_dir=run_dir,
        )
    assert not run_dir.exists() and not calls


def test_runner_is_unable_to_rerun_into_existing_directory(tmp_path, monkeypatch):
    fixture, checkout, python, run_dir, calls = _mock_exec(tmp_path, monkeypatch)
    run_dir.mkdir()
    (run_dir / "something-private.txt").write_text("protect me")
    with pytest.raises(runner.UpstreamRunError, match="must not already exist"):
        _run(fixture, checkout, python, run_dir)
    assert (run_dir / "something-private.txt").read_text() == "protect me"
    assert calls == []


def test_real_model_exit_failure_leaves_local_failed_receipt(tmp_path, monkeypatch):
    fixture, checkout, python, run_dir, calls = _mock_exec(tmp_path, monkeypatch, exit_code=23)
    with pytest.raises(runner.UpstreamRunError, match="exit code 23"):
        _run(fixture, checkout, python, run_dir)
    report = json.loads((run_dir / "upstream_run_evidence.json").read_text())
    assert report["status"] == "FAIL"
    assert report["return_code"] == 23
    assert not (run_dir / "benchmark.json").exists()


def test_missing_expected_upstream_artifacts_cannot_be_called_a_pass(tmp_path, monkeypatch):
    fixture, checkout, python, run_dir, calls = _mock_exec(tmp_path, monkeypatch, emit_files=False)
    with pytest.raises(runner.UpstreamRunError, match="Expected exactly one"):
        _run(fixture, checkout, python, run_dir)
    assert json.loads((run_dir / "upstream_run_evidence.json").read_text())["status"] == "FAIL"


def test_timeout_bounds_reject_outside_range(tmp_path, monkeypatch):
    fixture, checkout, python, run_dir, calls = _mock_exec(tmp_path, monkeypatch)
    with pytest.raises(runner.UpstreamRunError, match="Timeout"):
        _run(fixture, checkout, python, run_dir, timeout_seconds=8000)
    assert calls == [] and not run_dir.exists()


def test_run_directory_cannot_nest_under_fixture_or_untrusted_source(tmp_path, monkeypatch):
    fixture, checkout, python, _run_dir, calls = _mock_exec(tmp_path, monkeypatch)
    with pytest.raises(runner.UpstreamRunError, match="overlap"):
        _run(fixture, checkout, python, checkout / "generated")
    with pytest.raises(runner.UpstreamRunError, match="overlap"):
        _run(fixture, checkout, python, fixture / "generated")
    assert calls == []


def test_cli_exposes_all_toolchain_pinning_and_explicit_model_rights(tmp_path):
    args = build_parser().parse_args([
        "--fixture-dir", str(tmp_path / "fixture"),
        "--upstream-checkout", str(tmp_path / "external"),
        "--python-313", str(tmp_path / "python313.exe"),
        "--run-dir", str(tmp_path / "run"),
        "--confirm-noncommercial",
    ])
    assert args.confirm_noncommercial is True
    assert args.python_313_exe.name == "python313.exe"
    assert args.timeout == 3600


def test_generate_cli_runs_without_any_midi_analysis_library(tmp_path):
    """Actual external process: block mido imports, proving stdlib-only generate."""
    import subprocess
    import sys

    code = (
        "import builtins, sys\n"
        "before = builtins.__import__\n"
        "def guard(name, *args, **kwargs):\n"
        "    if name == 'mido' or name.startswith('mido.'):\n"
        "        raise ImportError('MIDI runtime intentionally unavailable')\n"
        "    return before(name, *args, **kwargs)\n"
        "builtins.__import__ = guard\n"
        "sys.argv = ['cdlc-auto-cdlc-truth', 'generate', '--out-dir', sys.argv[1]]\n"
        "from rocksmith_cdlc_generator.auto_cdlc_truth_cli import main\n"
        "main()\n"
    )
    target = tmp_path / "generated-original-audio"
    run = subprocess.run(
        [sys.executable, "-c", code, str(target)],
        check=False, capture_output=True, text=True, timeout=30,
    )
    assert run.returncode == 0, run.stderr
    assert (target / "original_synthetic.wav").is_file()
    assert (target / "fixture.json").is_file()


def test_virtualenv_python_symlink_is_executed_unresolved(tmp_path, monkeypatch):
    fixture, checkout, python, run_dir, calls = _mock_exec(
        tmp_path, monkeypatch, virtualenv_symlink=True,
    )
    result = _run(fixture, checkout, python, run_dir)
    assert result["status"] == "PASS"
    assert python.is_symlink()
    assert calls[0][0][0] == str(python.absolute())
    assert calls[0][0][0] != str(python.resolve())
