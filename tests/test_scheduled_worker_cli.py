"""Conservative task-time worker admission without real music/model execution."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from rocksmith_cdlc_generator import scheduled_worker_cli as scheduler


def _probe(**overrides) -> scheduler.SchedulerAdmission:
    defaults = dict(
        on_ac=True,
        active_console=True,
        idle_seconds=900,
        cpu_busy_percent=3,
        music_game_running=False,
    )
    defaults.update(overrides)
    return scheduler.SchedulerAdmission(**defaults)


@pytest.mark.parametrize(("overrides", "reason"), [
    ({"on_ac": False}, "NOT_ON_AC"),
    ({"active_console": False}, "NO_ACTIVE_CONSOLE"),
    ({"idle_seconds": 0}, "USER_RECENTLY_ACTIVE"),
    ({"idle_seconds": 599.99}, "USER_RECENTLY_ACTIVE"),
    ({"idle_seconds": float("nan")}, "USER_RECENTLY_ACTIVE"),
    ({"cpu_busy_percent": 20.001}, "CPU_BUSY_OR_UNKNOWN"),
    ({"cpu_busy_percent": float("inf")}, "CPU_BUSY_OR_UNKNOWN"),
    ({"cpu_busy_percent": -1}, "CPU_BUSY_OR_UNKNOWN"),
    ({"music_game_running": True}, "ROCKSMITH_RUNNING"),
])
def test_admission_fails_closed_when_any_owner_protection_is_unsatisfied(
    overrides, reason,
):
    assert scheduler.decide_admission(_probe(**overrides)) == reason


def test_admission_succeeds_at_exact_safety_thresholds():
    assert scheduler.decide_admission(
        _probe(idle_seconds=600.0, cpu_busy_percent=20.0)
    ) == "ADMITTED"


def test_scheduled_invocation_never_runs_engine_when_user_recently_active(monkeypatch):
    states = []
    monkeypatch.delenv("ROCKSMITH_CDLC_DISABLE_UNATTENDED_WORKER", raising=False)
    monkeypatch.setattr(scheduler, "read_admission", lambda: _probe(idle_seconds=5))
    monkeypatch.setattr(scheduler, "_write_local_gate_report",
                        lambda status, reason: states.append((status, reason)))
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.unattended_worker_cli.main",
        lambda *_args: pytest.fail("The user is active; the engine must not execute"),
    )
    assert scheduler.main() == 0
    assert states == [("SKIPPED", "USER_RECENTLY_ACTIVE")]


def test_explicit_owner_disable_short_circuits_all_probes(monkeypatch):
    monkeypatch.setenv("ROCKSMITH_CDLC_DISABLE_UNATTENDED_WORKER", "1")
    states = []
    monkeypatch.setattr(scheduler, "read_admission",
                        lambda: pytest.fail("Owner disabled; probe must not run"))
    monkeypatch.setattr(scheduler, "_write_local_gate_report",
                        lambda status, reason: states.append((status, reason)))
    assert scheduler.main() == 0
    assert states == [("SKIPPED", "OWNER_DISABLED")]


def test_metric_exceptions_skip_without_leaking_paths(monkeypatch):
    monkeypatch.delenv("ROCKSMITH_CDLC_DISABLE_UNATTENDED_WORKER", raising=False)
    def broken():
        raise OSError("C:/private/Music/recording.wav could not be inspected")
    monkeypatch.setattr(scheduler, "read_admission", broken)
    events = []
    monkeypatch.setattr(scheduler, "_write_local_gate_report",
                        lambda *arguments: events.append(arguments))
    assert scheduler.main() == 0
    assert events == [("SKIPPED", "METRICS_UNAVAILABLE")]
    assert "private" not in str(events)


def test_admitted_check_runs_existing_worker_once(monkeypatch):
    monkeypatch.delenv("ROCKSMITH_CDLC_DISABLE_UNATTENDED_WORKER", raising=False)
    monkeypatch.setattr(scheduler, "read_admission", lambda: _probe())
    events = []
    calls = []
    monkeypatch.setattr(scheduler, "_write_local_gate_report",
                        lambda *args: events.append(args))
    monkeypatch.setattr("rocksmith_cdlc_generator.unattended_worker_cli.main",
                        lambda args: calls.append(args) or 0)
    assert scheduler.main(["--config", "test.json"]) == 0
    assert calls == [["--config", "test.json"]]
    assert events == [
        ("STARTED", "ADMITTED"), ("COMPLETED", "WORKER_EXIT_ZERO")
    ]


def test_worker_error_reports_class_only_not_private_exception_message(monkeypatch):
    monkeypatch.delenv("ROCKSMITH_CDLC_DISABLE_UNATTENDED_WORKER", raising=False)
    monkeypatch.setattr(scheduler, "read_admission", lambda: _probe())
    events = []
    monkeypatch.setattr(scheduler, "_write_local_gate_report",
                        lambda *args: events.append(args))
    def fail(_):
        raise ValueError("Private audio C:/Users/example/my_song.wav")
    monkeypatch.setattr("rocksmith_cdlc_generator.unattended_worker_cli.main", fail)
    assert scheduler.main() == 1
    assert events[-1] == ("FAILED", "ValueError")
    assert "my_song" not in str(events)


def test_exit_code_nonzero_is_an_execution_failure_not_a_music_pass(monkeypatch):
    monkeypatch.delenv("ROCKSMITH_CDLC_DISABLE_UNATTENDED_WORKER", raising=False)
    monkeypatch.setattr(scheduler, "read_admission", lambda: _probe())
    events = []
    monkeypatch.setattr(scheduler, "_write_local_gate_report",
                        lambda *args: events.append(args))
    monkeypatch.setattr("rocksmith_cdlc_generator.unattended_worker_cli.main",
                        lambda args: 3)
    assert scheduler.main() == 3
    assert events[-1] == ("FAILED", "WORKER_EXIT_NONZERO")


def test_gate_heartbeat_is_atomic_local_sanitized_and_build_bound(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.scheduled_worker_cli.uuid.uuid4",
        lambda: type("Token", (), {"hex": "testtoken"})(),
    )
    from rocksmith_cdlc_generator.build_identity import BuildIdentity
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.build_identity.current_build_identity",
        lambda: BuildIdentity(
            version="test", commit_sha="b" * 40, built_at_utc=None, packaged=True
        ),
    )
    scheduler._write_local_gate_report("SKIPPED", "USER_RECENTLY_ACTIVE")
    root = tmp_path / "RocksmithCDLCGenerator" / "unattended-worker"
    payload = json.loads((root / "scheduler_gate.json").read_text())
    assert payload["build_sha"] == "b" * 40
    assert payload["status"] == "SKIPPED"
    assert payload["reason_code"] == "USER_RECENTLY_ACTIVE"
    assert "observed_utc" in payload
    assert "path" not in payload
    assert len(list(root.glob("*.tmp"))) == 0
    assert str(tmp_path) not in json.dumps(payload)


def test_cpu_filetime_combination_is_unsigned_64bit_safe():
    ft = scheduler._FileTime()
    ft.low = 10
    ft.high = 2
    assert scheduler._filetime_number(ft) == (2 << 32) + 10


def test_no_load_of_nonwindows_metrics(monkeypatch):
    monkeypatch.setattr(scheduler.sys, "platform", "linux")
    with pytest.raises(OSError, match="requires Windows"):
        scheduler.read_admission()
