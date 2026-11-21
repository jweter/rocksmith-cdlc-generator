"""Prove the upstream readiness doctor is read-only, specific and fail-closed.

No third-party audio model or Wwise executable is imported/launched. Fixture
material is fully original and the mock merely stands in for Git/version
metadata queries, not for evidence of a successful model transcription.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from rocksmith_cdlc_generator import auto_cdlc_readiness as doctor
from rocksmith_cdlc_generator.auto_cdlc_doctor_cli import build_parser
from rocksmith_cdlc_generator.auto_cdlc_truth import generate_known_truth


def _expected_versions() -> dict[str, str]:
    result = {}
    for name, req in doctor._REQUIRED.items():
        result[name] = req[2:] if req.startswith((">=", "==")) else "2.5.0"
    return result


def _test_environment(tmp_path: Path, monkeypatch, *, memory: float = 9.0,
                      disk: float = 15.0, versions: dict | None = None,
                      dirty: bool = False, cache_valid: bool = True):
    fixture = tmp_path / "fixture"
    generate_known_truth(fixture)
    root = tmp_path / "auto-cdlc"
    root.mkdir()
    (root / ".git").mkdir()
    (root / "cdlc_bajo.py").write_text("# reviewed synthetic source fixture", encoding="utf-8")
    models = root / "modelos"
    models.mkdir()
    bass = models / "kuielab_b_bass.onnx"
    bass.write_bytes(b"n" * (1024 * 1024 + 1))
    beat = models / "beat_this-final0.ckpt"
    with beat.open("wb") as handle:
        handle.seek(50_000_000 - 1)
        handle.write(b"\0")
    python = tmp_path / "python313.exe"
    python.write_bytes(b"mock interpreter")
    run_parent = tmp_path / "future-runs"
    run_parent.mkdir()
    subprocess_calls = []
    original_hash = doctor.sha256_file

    def fake_hash(path):
        if Path(path) == beat:
            return doctor.BEAT_THIS_SHA256 if cache_valid else "0" * 64
        return original_hash(path)

    monkeypatch.setattr(doctor, "sha256_file", fake_hash)
    monkeypatch.setattr(doctor, "available_memory_gib", lambda: memory)
    monkeypatch.setattr(doctor.shutil, "disk_usage",
                        lambda _root: SimpleNamespace(free=disk * 1024 ** 3))

    def fake_process(command, **kwargs):
        subprocess_calls.append(command)
        if command[0:3] == ["git", "-C", str(root)]:
            if command[3:] == ["rev-parse", "HEAD"]:
                return SimpleNamespace(stdout=doctor.REVIEWED_UPSTREAM_COMMIT, returncode=0)
            if command[3:] == ["status", "--porcelain", "--untracked-files=no"]:
                return SimpleNamespace(stdout=" M cdlc_bajo.py\n" if dirty else "", returncode=0)
        if command[0] == str(python) and command[1:4] == ["-B", "-I", "-c"]:
            return SimpleNamespace(
                stdout=json.dumps({
                    "versions": _expected_versions() if versions is None else versions,
                    "python": [3, 13], "isolated": True,
                }),
                returncode=0,
            )
        raise AssertionError(f"Unexpected executable in read-only doctor: {command[0]}")

    monkeypatch.setattr(doctor.subprocess, "run", fake_process)
    return fixture, root, python, run_parent, subprocess_calls


def _check(env):
    fixture, root, python, run_parent, _calls = env
    return doctor.inspect_upstream_readiness(
        fixture_dir=fixture, upstream_checkout=root,
        python_313_exe=python, run_parent=run_parent,
    )


def test_complete_cached_fixture_and_dependencies_are_synthetic_ready(tmp_path, monkeypatch):
    env = _test_environment(tmp_path, monkeypatch)
    result = _check(env)
    assert result["synthetic_transcription_ready"] is True
    assert result["synthetic_blocker_codes"] == []
    assert result["wwise_console_located"] is False
    assert result["wwise_packaging_verified"] is False
    assert result["network_isolation_proven"] is False
    assert result["model_producer_provenance_verified"] is False
    assert result["real_song_accuracy_verified"] is False
    assert all(check["passed"] for check in result["checks"] if check["code"] != "WWISE_CONSOLE_LOCATED")
    assert all("install" not in " ".join(map(str, cmd)).lower() for cmd in env[-1])
    assert result["sha256"]["synthetic_audio"]
    assert str(tmp_path) not in json.dumps(result)


def test_low_ram_blocks_even_with_every_model_cached(tmp_path, monkeypatch):
    env = _test_environment(tmp_path, monkeypatch, memory=2.09)
    result = _check(env)
    assert not result["synthetic_transcription_ready"]
    assert result["synthetic_blocker_codes"] == ["PHYSICAL_RAM_AT_LEAST_7_GIB"]
    assert not (env[3] / "new-run").exists()


def test_low_disk_blocks_without_creating_any_output(tmp_path, monkeypatch):
    env = _test_environment(tmp_path, monkeypatch, disk=2.0)
    result = _check(env)
    assert "RUN_VOLUME_FREE_DISK_AT_LEAST_8_GIB" in result["synthetic_blocker_codes"]
    assert list(env[3].iterdir()) == []


def test_unreviewed_source_or_tracked_mutation_is_rejected(tmp_path, monkeypatch):
    env = _test_environment(tmp_path, monkeypatch, dirty=True)
    result = _check(env)
    assert "UPSTREAM_REVIEWED_CHECKOUT" in result["synthetic_blocker_codes"]


def test_missing_and_below_requirement_packages_have_named_errors(tmp_path, monkeypatch):
    versions = _expected_versions()
    versions["madmom"] = None
    versions["numpy"] = "1.21.6"
    env = _test_environment(tmp_path, monkeypatch, versions=versions)
    report = _check(env)
    packages = next(item["detail"] for item in report["checks"] if item["code"] == "PYTHON_313_PACKAGE_SET")
    assert packages["unmet_packages"] == ["numpy", "madmom"]
    assert "PYTHON_313_PACKAGE_SET" in report["synthetic_blocker_codes"]


def test_beat_checkpoint_wrong_sha_refused(tmp_path, monkeypatch):
    env = _test_environment(tmp_path, monkeypatch, cache_valid=False)
    report = _check(env)
    assert "BEAT_THIS_CHECKPOINT_PINNED" in report["synthetic_blocker_codes"]


def test_missing_bass_model_blocks_even_when_beat_model_is_pinned(tmp_path, monkeypatch):
    env = _test_environment(tmp_path, monkeypatch)
    (env[1] / "modelos" / "kuielab_b_bass.onnx").unlink()
    report = _check(env)
    assert "BASS_ONNX_MODEL_CACHED" in report["synthetic_blocker_codes"]


def test_verified_fixture_tampering_blocks_readiness(tmp_path, monkeypatch):
    env = _test_environment(tmp_path, monkeypatch)
    (env[0] / "fixture.json").write_text("{}", encoding="utf-8")
    result = _check(env)
    assert "SYNTHETIC_FIXTURE_VERIFIED" in result["synthetic_blocker_codes"]


def test_wwise_presence_is_never_a_gameplay_or_psarc_success(tmp_path, monkeypatch):
    env = _test_environment(tmp_path, monkeypatch)
    console = tmp_path / "wwise" / "Authoring" / "x64" / "Release" / "bin" / "WwiseConsole.exe"
    console.parent.mkdir(parents=True)
    console.write_bytes(b"test-stub-NOT-real-Wwise")
    report = doctor.inspect_upstream_readiness(
        fixture_dir=env[0], upstream_checkout=env[1],
        python_313_exe=env[2], run_parent=env[3], wwise_console=console,
    )
    assert report["wwise_console_located"]
    assert report["wwise_packaging_verified"] is False
    assert report["real_rocksmith_gameplay_verified"] is False


def test_not_configured_paths_have_explainable_codes_without_child_launch(tmp_path, monkeypatch):
    monkeypatch.setattr(doctor, "available_memory_gib", lambda: 7.5)
    monkeypatch.setattr(doctor.shutil, "disk_usage",
                        lambda _root: SimpleNamespace(free=12 * 1024 ** 3))
    child_calls = []
    monkeypatch.setattr(doctor.subprocess, "run", lambda *_a, **_kw: child_calls.append(True))
    report = doctor.inspect_upstream_readiness(run_parent=tmp_path)
    assert "SYNTHETIC_FIXTURE_VERIFIED" in report["synthetic_blocker_codes"]
    assert "UPSTREAM_REVIEWED_CHECKOUT" in report["synthetic_blocker_codes"]
    assert "PYTHON_313_PACKAGE_SET" in report["synthetic_blocker_codes"]
    assert child_calls == []


@pytest.mark.parametrize("actual,req,expected", [
    ("1.14.1", ">=1.13", True),
    ("1.12", ">=1.13", False),
    ("2.0", ">=2", True),
    ("1.9", ">=2", False),
    ("0.17.dev0+puro", "==0.17.dev0+puro", True),
    ("0.17.dev0", "==0.17.dev0+puro", False),
    ("0.2.0rc1", ">=0.2", False),
    ("1.3.0+cpu", ">=1.2.6", True),
])
def test_version_floor_is_conservative(actual, req, expected):
    assert doctor._minimum_satisfied(actual, req) is expected


def test_doctor_cli_imports_without_mido_or_external_model_runtime(tmp_path):
    """Run a real subprocess with MIDI imports intentionally denied."""
    code = (
        "import builtins, sys\n"
        "old = builtins.__import__\n"
        "def guard(name, *a, **kw):\n"
        "    if name == 'mido' or name.startswith('mido.'):\n"
        "        raise ImportError('MIDI engine intentionally not available')\n"
        "    return old(name, *a, **kw)\n"
        "builtins.__import__ = guard\n"
        "sys.argv = ['cdlc-auto-cdlc-doctor', '--run-parent', sys.argv[1]]\n"
        "from rocksmith_cdlc_generator.auto_cdlc_doctor_cli import main\n"
        "main()\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)],
        capture_output=True, text=True, check=False, timeout=20,
    )
    assert proc.returncode == 2, proc.stderr
    report = json.loads(proc.stdout)
    assert report["synthetic_transcription_ready"] is False
    assert "PYTHON_313_PACKAGE_SET" in report["synthetic_blocker_codes"]


def test_cli_accepts_known_local_paths_and_does_not_create_them(tmp_path):
    args = build_parser().parse_args(["--run-parent", str(tmp_path), "--python-313", "C:/Tools/py313.exe"])
    assert args.python_313.name == "py313.exe"
    assert args.run_parent == tmp_path
