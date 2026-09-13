from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from rocksmith_cdlc_generator.unattended_worker import (
    LocalDiagnosis,
    OllamaDiagnosisSettings,
    RecentProjectHealth,
    UnattendedWorkerConfig,
    _acquire_lock,
    _diagnosis_payload,
    _ollama_chat_url,
    _release_lock,
    discover_private_scenarios,
    load_worker_config,
    run_unattended_worker,
)
from rocksmith_cdlc_generator.windows_unattended_worker import (
    ensure_windows_worker_registered,
    registration_command,
)


def _scenario(path: Path, *, scenario_id: str = "timing-one") -> Path:
    project = path.parent / "project"
    project.mkdir(exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "scenario_id": scenario_id,
                "scenario_type": "shared_timing",
                "project_dir": str(project),
                "roles": ["bass"],
                "expected": {"first_playable_seconds": 7.1},
            }
        ),
        encoding="utf-8",
    )
    return path


def test_ollama_diagnosis_refuses_non_loopback_host() -> None:
    with pytest.raises(ValueError, match="local-only"):
        _ollama_chat_url("http://192.168.1.50:11434")
    assert _ollama_chat_url("http://127.0.0.1:11434") == "http://127.0.0.1:11434/api/chat"


def test_worker_default_config_uses_gitignored_private_roots(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    repo = tmp_path / "repo"
    config = load_worker_config(repo_root=repo)
    assert repo / "private" / "product-reality-scenarios" in config.scenario_roots
    assert repo / "private" / "product-reality-inbox" in config.scenario_roots
    assert config.state_dir == tmp_path / "local" / "RocksmithCDLCGenerator" / "unattended-worker"


def test_scenario_discovery_preserves_malformed_candidates_and_deduplicates_valid_ids(tmp_path: Path) -> None:
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    root_a.mkdir()
    root_b.mkdir()
    _scenario(root_a / "one.json", scenario_id="same")
    _scenario(root_b / "two.json", scenario_id="same")
    invalid = root_a / "not-a-scenario.json"
    invalid.write_text('{"hello":"world"}', encoding="utf-8")
    config = UnattendedWorkerConfig(scenario_roots=[root_a, root_b])
    found = discover_private_scenarios(config)
    assert len(found) == 2
    assert root_a / "one.json" in found
    assert invalid in found
    assert root_b / "two.json" not in found


def test_malformed_configured_scenario_fails_closed(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "scenarios"
    root.mkdir()
    malformed = root / "important.json"
    malformed.write_text('{"schema_version": 1, "scenario_id":', encoding="utf-8")
    config = UnattendedWorkerConfig(
        scenario_roots=[root],
        results_dir=tmp_path / "results",
        state_dir=tmp_path / "state",
        include_recent_projects=False,
        ollama=OllamaDiagnosisSettings(enabled=False),
    )
    monkeypatch.setattr("rocksmith_cdlc_generator.unattended_worker.load_worker_config", lambda *a, **k: config)
    result = run_unattended_worker()
    assert result.report.status == "REVIEW_REQUIRED"
    assert len(result.report.scenario_results) == 1
    assert result.report.scenario_results[0].scenario_id == "important"
    assert result.report.scenario_results[0].checks[0]["code"] == "worker_scenario_error"


def test_ollama_payload_contains_derived_metrics_not_private_paths() -> None:
    health = RecentProjectHealth(
        project_name="Private Song",
        recording_sha256="a" * 64,
        status="FAIL",
        qualification_status="review_required",
        best_shift_seconds=-4.65,
        first_projected_note_seconds=11.77,
        first_audio_note_seconds=7.12,
        reason="Repeated onset evidence prefers an earlier translation.",
    )
    payload = _diagnosis_payload(scenario_results=[], recent_health=[health])
    text = json.dumps(payload)
    assert "C:/" not in text
    assert "recording_sha256" not in text
    assert "-4.65" in text


def test_unattended_worker_uses_ollama_as_advisor_not_authority(tmp_path: Path, monkeypatch) -> None:
    config = UnattendedWorkerConfig(
        scenario_roots=[],
        results_dir=tmp_path / "results",
        state_dir=tmp_path / "state",
        include_recent_projects=True,
        ollama=OllamaDiagnosisSettings(enabled=True),
    )
    health = RecentProjectHealth(
        project_name="Song",
        recording_sha256="b" * 64,
        status="FAIL",
        qualification_status="review_required",
        best_shift_seconds=-4.65,
        first_projected_note_seconds=11.77,
        first_audio_note_seconds=7.12,
        reason="Independent qualification failed.",
    )
    diagnosis = LocalDiagnosis(
        category="timing_phase",
        summary="The measured phase is wrong.",
        likely_root_cause="Shared alignment is bound to the wrong repeated phrase.",
        next_automated_action="Reproduce against the phase solver regression and rebuild timing.",
        human_required=False,
        confidence=0.9,
    )
    monkeypatch.setattr("rocksmith_cdlc_generator.unattended_worker.load_worker_config", lambda *a, **k: config)
    monkeypatch.setattr("rocksmith_cdlc_generator.unattended_worker.discover_private_scenarios", lambda _c: [])
    monkeypatch.setattr("rocksmith_cdlc_generator.unattended_worker.collect_recent_project_health", lambda: [health])
    monkeypatch.setattr("rocksmith_cdlc_generator.unattended_worker.diagnose_with_local_ollama", lambda *a, **k: diagnosis)

    result = run_unattended_worker()
    assert result.report.status == "FAIL"
    assert result.report.diagnosis == diagnosis
    assert result.report.diagnosis.human_required is False
    assert result.report_path.is_file()
    assert list((tmp_path / "state" / "history").glob("*.json"))


def test_unattended_worker_idle_requires_no_human_action(tmp_path: Path, monkeypatch) -> None:
    config = UnattendedWorkerConfig(
        scenario_roots=[],
        results_dir=tmp_path / "results",
        state_dir=tmp_path / "state",
        include_recent_projects=True,
        ollama=OllamaDiagnosisSettings(enabled=True),
    )
    monkeypatch.setattr("rocksmith_cdlc_generator.unattended_worker.load_worker_config", lambda *a, **k: config)
    monkeypatch.setattr("rocksmith_cdlc_generator.unattended_worker.discover_private_scenarios", lambda _c: [])
    monkeypatch.setattr("rocksmith_cdlc_generator.unattended_worker.collect_recent_project_health", lambda: [])
    result = run_unattended_worker()
    assert result.report.status == "IDLE"
    assert result.report.diagnosis is None
    assert "No configured" in result.report.notes[0]


def test_worker_reclaims_lock_owned_by_dead_process(tmp_path: Path, monkeypatch) -> None:
    state = tmp_path / "state"
    state.mkdir()
    lock = state / "worker.lock"
    lock.write_text("123456", encoding="ascii")
    monkeypatch.setattr("rocksmith_cdlc_generator.unattended_worker._pid_is_running", lambda _pid: False)
    fd = _acquire_lock(state)
    assert fd is not None
    assert lock.read_text(encoding="ascii") == str(__import__("os").getpid())
    _release_lock(state, fd)
    assert not lock.exists()


def test_worker_does_not_steal_lock_from_live_process(tmp_path: Path, monkeypatch) -> None:
    state = tmp_path / "state"
    state.mkdir()
    lock = state / "worker.lock"
    lock.write_text("123456", encoding="ascii")
    monkeypatch.setattr("rocksmith_cdlc_generator.unattended_worker._pid_is_running", lambda _pid: True)
    assert _acquire_lock(state) is None
    assert lock.exists()


def test_windows_registration_is_noop_off_windows() -> None:
    result = ensure_windows_worker_registered(os_name="posix")
    assert result.supported is False
    assert result.changed is False


def test_windows_registration_refreshes_current_build_path(monkeypatch) -> None:
    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="created", stderr="")

    monkeypatch.setattr(
        "rocksmith_cdlc_generator.windows_unattended_worker.worker_invocation",
        lambda: ["worker.exe", "--unattended-worker"],
    )
    result = ensure_windows_worker_registered(runner=runner, os_name="nt")
    assert result.registered is True
    assert result.changed is True
    assert len(calls) == 1
    assert "/F" in calls[0]
    assert "--unattended-worker" in " ".join(calls[0])


def test_windows_registration_creates_idle_task(monkeypatch) -> None:
    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="created", stderr="")

    monkeypatch.setattr(
        "rocksmith_cdlc_generator.windows_unattended_worker.worker_invocation",
        lambda: ["worker.exe", "--unattended-worker"],
    )
    result = ensure_windows_worker_registered(runner=runner, os_name="nt")
    assert result.registered is True
    assert result.changed is True
    assert len(calls) == 1
    create = calls[0]
    assert "/SC" in create and "ONIDLE" in create
    assert "/I" in create and "10" in create
    assert "--unattended-worker" in " ".join(create)


def test_registration_command_never_invokes_a_remote_service() -> None:
    command = registration_command(["worker.exe", "--unattended-worker"])
    text = " ".join(command).lower()
    assert "schtasks" in text
    assert "http://" not in text
    assert "https://" not in text
