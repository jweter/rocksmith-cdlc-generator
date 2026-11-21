"""Idle-worker integration for the safe auto-cdlc admission doctor.

Music Product Reality and source authority remain unchanged. The worker is
only an observer here, never an upstream model launcher or package installer.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rocksmith_cdlc_generator import unattended_auto_cdlc_probe as probe
from rocksmith_cdlc_generator.unattended_worker import (
    OllamaDiagnosisSettings,
    UnattendedWorkerConfig,
    format_worker_report,
    load_worker_config,
    run_unattended_worker,
)
from rocksmith_cdlc_generator.unattended_worker_github import _public_payload


_CODES = (
    "PHYSICAL_RAM_AT_LEAST_7_GIB",
    "RUN_VOLUME_FREE_DISK_AT_LEAST_8_GIB",
    "SYNTHETIC_FIXTURE_VERIFIED",
    "UPSTREAM_REVIEWED_CHECKOUT",
    "BASS_ONNX_MODEL_CACHED",
    "BEAT_THIS_CHECKPOINT_PINNED",
    "PYTHON_313_PACKAGE_SET",
)


def _doctor_report(
    *, missing: tuple[str, ...] = (
        "PHYSICAL_RAM_AT_LEAST_7_GIB", "BASS_ONNX_MODEL_CACHED",
        "BEAT_THIS_CHECKPOINT_PINNED", "PYTHON_313_PACKAGE_SET"
    ),
) -> dict:
    checks = [
        {
            "code": code, "passed": code not in missing,
        }
        for code in _CODES
    ]
    checks[0]["detail"] = {"available_gib": 6.298}
    checks[1]["detail"] = {"available_gib": 31.278}
    checks[-1]["detail"] = {"installed_count": 0 if missing else 18, "required_count": 18,
                            "unmet_packages": ["librosa", "madmom", "C:/private/test"] if missing else []}
    if not missing:
        checks[0]["detail"] = {"available_gib": 9.25}
    return {
        "schema_version": 1,
        "synthetic_transcription_ready": not missing,
        "synthetic_blocker_codes": list(missing),
        "wwise_console_located": False,
        "checks": checks,
        "private_path_to_never_copy": "C:/private/song.wav",
        "sha256": {"synthetic_audio": "f" * 64},
    }


def test_probe_is_opt_in_and_does_not_invoke_doctor(monkeypatch):
    monkeypatch.setattr(
        probe, "inspect_upstream_readiness",
        lambda **kwargs: pytest.fail("Disabled optional probe invoked the doctor"),
    )
    assert probe.collect_auto_cdlc_worker_probe(probe.AutoCdlcWorkerSettings()) is None


def test_opted_in_blockers_are_machine_readable_but_keep_private_paths_out(monkeypatch):
    observed = []
    def fake(**kwargs):
        observed.append(kwargs)
        return _doctor_report()
    monkeypatch.setattr(probe, "inspect_upstream_readiness", fake)
    settings = probe.AutoCdlcWorkerSettings(
        enabled=True,
        fixture_dir=Path("C:/private/song-benchmark"),
        upstream_checkout=Path("C:/private/auto-cdlc"),
        python_313_exe=Path("C:/private/venv/python.exe"),
        run_parent=Path("C:/private/runs"),
    )
    snapshot = probe.collect_auto_cdlc_worker_probe(settings)
    assert snapshot is not None
    assert snapshot.status == "BLOCKED"
    assert snapshot.available_ram_gib == 6.298
    assert snapshot.available_disk_gib == 31.278
    assert snapshot.missing_package_count == 18
    assert snapshot.wwise_console_located is False
    assert set(snapshot.blocked_codes) == set(_doctor_report()["synthetic_blocker_codes"])
    assert observed[0]["fixture_dir"] == settings.fixture_dir
    assert "C:/private" not in snapshot.model_dump_json()
    assert "librosa" not in snapshot.model_dump_json()
    assert "f" * 64 not in snapshot.model_dump_json()
    assert snapshot.real_model_transcription_proven is False
    assert snapshot.rocksmith_gameplay_proven is False


def test_valid_full_preflight_is_only_ready_to_attempt_synthetic(monkeypatch):
    monkeypatch.setattr(
        probe, "inspect_upstream_readiness",
        lambda **_kwargs: _doctor_report(missing=()),
    )
    snapshot = probe.collect_auto_cdlc_worker_probe(
        probe.AutoCdlcWorkerSettings(enabled=True)
    )
    assert snapshot is not None
    assert snapshot.status == "READY_TO_ATTEMPT_SYNTHETIC"
    assert snapshot.blocked_codes == []
    assert snapshot.wwise_packaging_proven is False
    assert snapshot.real_model_transcription_proven is False


@pytest.mark.parametrize("mutate", [
    lambda x: x.update(synthetic_transcription_ready=True),
    lambda x: x.update(synthetic_blocker_codes=["UNTRUSTED", "PHYSICAL_RAM_AT_LEAST_7_GIB"]),
    lambda x: x["checks"].append({"code": "BASS_ONNX_MODEL_CACHED", "passed": False}),
    lambda x: x["checks"].pop(),
    lambda x: x.update(schema_version=999),
    lambda x: x["checks"][0].update(passed=None),
])
def test_malformed_or_contradictory_doctor_cannot_report_ready(
    monkeypatch, mutate,
):
    report = _doctor_report()
    mutate(report)
    monkeypatch.setattr(probe, "inspect_upstream_readiness", lambda **_kw: report)
    result = probe.collect_auto_cdlc_worker_probe(
        probe.AutoCdlcWorkerSettings(enabled=True)
    )
    assert result is not None
    assert result.status == "UNAVAILABLE"
    assert not result.rocksmith_gameplay_proven


def test_doctor_exception_never_leaks_private_path(monkeypatch):
    def bad(**_kwargs):
        raise OSError("Cannot read C:/PRIVATE-SONG-WORKSPACE/song.wav")
    monkeypatch.setattr(probe, "inspect_upstream_readiness", bad)
    snapshot = probe.collect_auto_cdlc_worker_probe(
        probe.AutoCdlcWorkerSettings(enabled=True)
    )
    assert snapshot is not None
    assert snapshot.status == "UNAVAILABLE"
    assert snapshot.error_code == "OSError"
    assert "PRIVATE-SONG" not in snapshot.model_dump_json()


def test_worker_config_round_trip_preserves_optional_probe_without_running_it(tmp_path):
    config = tmp_path / "worker.json"
    config.write_text(
        json.dumps({
            "schema_version": 1,
            "include_recent_projects": False,
            "ollama": {"enabled": False},
            "auto_cdlc": {
                "enabled": True,
                "fixture_dir": "C:/MusicBench/fixture",
                "upstream_checkout": "C:/MusicBench/auto-cdlc",
                "python_313_exe": "C:/MusicBench/venv/python.exe",
                "run_parent": "C:/MusicBench",
            },
        }), encoding="utf-8",
    )
    resolved = load_worker_config(config, repo_root=tmp_path)
    assert resolved.auto_cdlc.enabled
    assert resolved.auto_cdlc.run_parent == Path("C:/MusicBench")
    assert not resolved.ollama.enabled


def test_worker_idles_with_readiness_blocked_without_ollama_or_human_rerun(
    tmp_path, monkeypatch,
):
    config = UnattendedWorkerConfig(
        scenario_roots=[], state_dir=tmp_path / "state",
        results_dir=tmp_path / "results",
        include_recent_projects=False,
        ollama=OllamaDiagnosisSettings(enabled=True),
        auto_cdlc=probe.AutoCdlcWorkerSettings(enabled=True),
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.unattended_worker.load_worker_config",
        lambda *a, **k: config,
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.unattended_worker.discover_private_scenarios",
        lambda _config: [],
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.unattended_worker.diagnose_with_local_ollama",
        lambda *a, **k: pytest.fail("Missing optional models must not trigger Ollama"),
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.unattended_worker.collect_auto_cdlc_worker_probe",
        lambda _settings: probe._summarize(_doctor_report()),
    )
    result = run_unattended_worker()
    assert result.report.status == "IDLE"
    assert result.report.diagnosis is None
    assert result.report.auto_cdlc_readiness is not None
    assert result.report.auto_cdlc_readiness.status == "BLOCKED"
    assert result.report.auto_cdlc_readiness.missing_package_count == 18
    saved = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert saved["auto_cdlc_readiness"]["status"] == "BLOCKED"
    assert not saved["auto_cdlc_readiness"]["rocksmith_gameplay_proven"]
    assert "Auto-cdlc" in format_worker_report(result.report) or "auto-cdlc" in format_worker_report(result.report)
    published = _public_payload(result.report)
    assert "auto_cdlc_readiness" not in published
    assert "C:/private" not in json.dumps(published)


def test_purported_ready_with_missing_packages_cannot_be_promoted(monkeypatch):
    report = _doctor_report(missing=())
    packages = next(c for c in report["checks"] if c["code"] == "PYTHON_313_PACKAGE_SET")
    packages["detail"]["installed_count"] = 0
    monkeypatch.setattr(probe, "inspect_upstream_readiness", lambda **_kw: report)
    observed = probe.collect_auto_cdlc_worker_probe(
        probe.AutoCdlcWorkerSettings(enabled=True)
    )
    assert observed is not None and observed.status == "UNAVAILABLE"


def test_purported_ready_below_ram_floor_cannot_be_promoted(monkeypatch):
    report = _doctor_report(missing=())
    report["checks"][0]["detail"]["available_gib"] = 5.0
    monkeypatch.setattr(probe, "inspect_upstream_readiness", lambda **_kw: report)
    observed = probe.collect_auto_cdlc_worker_probe(
        probe.AutoCdlcWorkerSettings(enabled=True)
    )
    assert observed is not None and observed.status == "UNAVAILABLE"
