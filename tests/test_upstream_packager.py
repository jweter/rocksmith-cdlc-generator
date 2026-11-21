"""Contract tests for opt-in local auto-cdlc packager (no Wwise or executable needed)."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from rocksmith_cdlc_generator import build_staging, upstream_packager
from rocksmith_cdlc_generator.cli import build_parser
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.psarc_inspection import PsarcContentError
from tests.test_build_staging import (
    _passing_content_validation,
    _write_dlcbuilder_fixture,
    _write_valid_psarc,
)


def _ready(tmp_path, monkeypatch, *, multi=True):
    project, _ = _write_dlcbuilder_fixture(tmp_path, multi=multi)
    binary = tmp_path / "cdlc-pack.exe"
    binary.write_bytes(b"pinned-local-test-stub")
    monkeypatch.setattr(
        build_staging, "require_configured_arrangements_ready",
        lambda _: SimpleNamespace(status="PASS"),
    )
    monkeypatch.setattr(build_staging, "bridge_available", lambda: True)
    monkeypatch.setattr(upstream_packager, "bridge_available", lambda: True)
    monkeypatch.setattr(
        build_staging, "validate_project_psarc_content",
        lambda *_: _passing_content_validation(),
    )
    return project, binary, sha256_file(binary)


def _simulate_packaging(monkeypatch, *, exit_code=0, stdout="VERIF files=12", count=1, mutate=None):
    captured = []

    def fake_run(command, **kwargs):
        captured.append((command, kwargs))
        if mutate is not None:
            mutate()
        out = Path(command[command.index("--salida") + 1])
        for i in range(count):
            _write_valid_psarc(out / f"TestSong{i}_p.psarc")
        return SimpleNamespace(returncode=exit_code, stdout=stdout, stderr="")

    monkeypatch.setattr(upstream_packager.subprocess, "run", fake_run)
    return captured


def _build(project, binary, digest, **kwargs):
    return upstream_packager.build_psarc_with_cdlc_pack(
        project, packager=binary, expected_packager_sha256=digest, **kwargs
    )


def test_cli_exposes_explicit_pinned_packager_path():
    args = build_parser().parse_args(
        ["build-psarc", "project", "--packager", "cdlc-pack.exe", "--packager-sha256", "a" * 64]
    )
    assert args.project == Path("project")
    assert args.packager == Path("cdlc-pack.exe")
    assert args.packager_sha256 == "a" * 64
    assert args.timeout == 3600


def test_generated_psarc_passes_existing_deep_registration_for_all_roles(tmp_path, monkeypatch):
    project, binary, digest = _ready(tmp_path, monkeypatch)
    calls = _simulate_packaging(monkeypatch)
    receipt_path = _build(project, binary, digest)

    receipt = build_staging.PsarcReceipt.model_validate_json(receipt_path.read_text())
    report = json.loads((project / "build/staging/cdlc_pack_run.json").read_text())
    assert receipt.safe_for_manual_installation is True
    assert receipt.content_inspection_status == "PASS"
    assert receipt.installed_to_rocksmith is False
    assert receipt.staged_path.startswith(str(project / "build" / "staging"))
    assert report["status"] == "PASS"
    assert report["packager_sha256"] == digest
    assert build_staging.verify_psarc_registration(project).status == "PASS"
    assert "--salida" in calls[0][0]
    assert calls[0][1]["check"] is False
    assert calls[0][1]["timeout"] == 3600
    assert (project / "build/staging/psarc_receipt.json").exists()


@pytest.mark.parametrize(
    ("exit_code", "stdout", "count", "match"),
    [
        (1, "", 0, "exited with code 1"),
        (0, "VERIF files=0\\nVERIF error=bad SNG", 1, "read-back verification error"),
        (0, "built but none returned", 0, "Expected exactly one"),
        (0, "built multiple outputs", 2, "Expected exactly one"),
    ],
)
def test_bad_upstream_outputs_never_register(tmp_path, monkeypatch, exit_code, stdout, count, match):
    project, binary, digest = _ready(tmp_path, monkeypatch)
    _simulate_packaging(monkeypatch, exit_code=exit_code, stdout=stdout, count=count)
    with pytest.raises((ValueError, RuntimeError), match=match):
        _build(project, binary, digest)
    assert not (project / "build/staging/psarc_receipt.json").exists()
    assert json.loads((project / "build/staging/cdlc_pack_run.json").read_text())["status"] == "FAIL"


def test_stale_inputs_while_packager_runs_fail_closed(tmp_path, monkeypatch):
    project, binary, digest = _ready(tmp_path, monkeypatch)
    input_path = project / "build/dlcbuilder/arr_bass_RS2.xml"
    _simulate_packaging(monkeypatch, mutate=lambda: input_path.write_bytes(b"changed"))
    with pytest.raises(ValueError, match="Staged input"):
        _build(project, binary, digest)
    assert not (project / "build/staging/psarc_receipt.json").exists()


def test_independent_bridge_failure_is_not_masked_by_upstream_success(tmp_path, monkeypatch):
    project, binary, digest = _ready(tmp_path, monkeypatch)
    _simulate_packaging(monkeypatch)
    def reject(*_):
        raise PsarcContentError("missing reference SNG")
    monkeypatch.setattr(build_staging, "validate_project_psarc_content", reject)
    with pytest.raises(PsarcContentError, match="missing reference"):
        _build(project, binary, digest)
    assert not (project / "build/staging/psarc_receipt.json").exists()


def test_packager_hash_mismatch_blocks_before_staging(tmp_path, monkeypatch):
    project, binary, _ = _ready(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="differs"):
        _build(project, binary, "0" * 64)
    assert not (project / "build/staging").exists()


def test_missing_inspection_bridge_blocks_before_staging(tmp_path, monkeypatch):
    project, binary, digest = _ready(tmp_path, monkeypatch)
    monkeypatch.setattr(upstream_packager, "bridge_available", lambda: False)
    with pytest.raises(RuntimeError, match="Deep PSARC inspection bridge"):
        _build(project, binary, digest)
    assert not (project / "build/staging").exists()


def test_packager_timeout_reports_failure(tmp_path, monkeypatch):
    project, binary, digest = _ready(tmp_path, monkeypatch)
    def hang(command, **kwargs):
        raise upstream_packager.subprocess.TimeoutExpired(command, kwargs["timeout"])
    monkeypatch.setattr(upstream_packager.subprocess, "run", hang)
    with pytest.raises(RuntimeError, match="timed out"):
        _build(project, binary, digest, timeout_seconds=10)
    report = json.loads((project / "build/staging/cdlc_pack_run.json").read_text())
    assert report["status"] == "FAIL"
    assert "timed out" in report["error"]
