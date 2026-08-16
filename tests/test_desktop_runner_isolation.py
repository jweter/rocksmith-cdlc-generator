from __future__ import annotations

import json
from pathlib import Path

import pytest

from rocksmith_cdlc_generator import desktop_runner


def test_packaged_bass_transcription_reenters_executable_worker(monkeypatch, tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    captured: dict[str, object] = {}

    monkeypatch.setattr(desktop_runner.sys, "frozen", True, raising=False)
    monkeypatch.delenv(desktop_runner._DESKTOP_WORKER_ENV, raising=False)

    def fail_in_process(*args, **kwargs):
        raise AssertionError("Packaged parent process must not run pYIN in-process")

    monkeypatch.setattr(desktop_runner, "analyze_project_bass", fail_in_process)

    class Completed:
        returncode = 0

    def fake_run(argv, *, check, env):
        captured["argv"] = argv
        captured["check"] = check
        captured["env"] = env
        Path(env[desktop_runner._DESKTOP_WORKER_RESULT_ENV]).write_text(
            json.dumps({"status": "ok", "return_code": 0}),
            encoding="utf-8",
        )
        return Completed()

    monkeypatch.setattr(desktop_runner.subprocess, "run", fake_run)

    result = desktop_runner.desktop_command_runner(
        ["cdlc", "transcribe-bass", str(project), "--engine", "librosa-pyin"]
    )

    assert result == 0
    assert captured["argv"] == [
        desktop_runner.sys.executable,
        desktop_runner._DESKTOP_WORKER_FLAG,
        "cdlc",
        "transcribe-bass",
        str(project),
        "--engine",
        "librosa-pyin",
    ]
    assert captured["check"] is False
    assert captured["env"][desktop_runner._DESKTOP_WORKER_ENV] == "1"
    assert desktop_runner._DESKTOP_WORKER_RESULT_ENV in captured["env"]


def test_packaged_worker_failure_raises_actionable_parent_error(monkeypatch, tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    monkeypatch.setattr(desktop_runner.sys, "frozen", True, raising=False)
    monkeypatch.delenv(desktop_runner._DESKTOP_WORKER_ENV, raising=False)

    class Completed:
        returncode = 1

    def fake_run(argv, *, check, env):
        Path(env[desktop_runner._DESKTOP_WORKER_RESULT_ENV]).write_text(
            json.dumps(
                {
                    "status": "error",
                    "error_type": "RuntimeError",
                    "message": "decoder failed",
                    "traceback": "Traceback: decoder failed",
                }
            ),
            encoding="utf-8",
        )
        return Completed()

    monkeypatch.setattr(desktop_runner.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="decoder failed") as exc_info:
        desktop_runner.desktop_command_runner(["cdlc", "transcribe-bass", str(project)])

    assert "Worker traceback" in str(exc_info.value)
    assert "Traceback: decoder failed" in str(exc_info.value)


def test_packaged_worker_executes_bass_transcription_without_recursing(
    monkeypatch, tmp_path: Path
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    called: dict[str, object] = {}

    monkeypatch.setattr(desktop_runner.sys, "frozen", True, raising=False)
    monkeypatch.setenv(desktop_runner._DESKTOP_WORKER_ENV, "1")

    def fail_subprocess(*args, **kwargs):
        raise AssertionError("Worker process must execute the closed dispatcher directly")

    monkeypatch.setattr(desktop_runner.subprocess, "run", fail_subprocess)

    def fake_analyze(project_dir: Path, *, engine: str, progress_callback=None):
        called["project"] = project_dir
        called["engine"] = engine
        assert progress_callback is not None
        progress_callback(42.0, "Pitch analysis chunk 2 of 5")
        return {}

    monkeypatch.setattr(desktop_runner, "analyze_project_bass", fake_analyze)

    result = desktop_runner.desktop_command_runner(
        ["cdlc", "transcribe-bass", str(project), "--engine", "librosa-pyin"]
    )

    assert result == 0
    assert called == {"project": project.resolve(), "engine": "librosa-pyin"}
    payload = json.loads(
        (project / "review" / desktop_runner._TASK_STATUS_NAME).read_text(encoding="utf-8")
    )
    assert payload["status"] == "complete"
    assert payload["percent"] == 100.0
    assert payload["task"] == "Generate audio-derived Bass draft"
    log_lines = (project / "review" / desktop_runner._TASK_LOG_NAME).read_text(encoding="utf-8").splitlines()
    assert any("Pitch analysis chunk 2 of 5" in line for line in log_lines)


def test_bass_transcription_failure_persists_visible_task_error(monkeypatch, tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.delattr(desktop_runner.sys, "frozen", raising=False)

    def fail_analyze(project_dir: Path, *, engine: str, progress_callback=None):
        assert progress_callback is not None
        progress_callback(25.0, "Pitch analysis chunk 1 of 4")
        raise RuntimeError("pYIN failed")

    monkeypatch.setattr(desktop_runner, "analyze_project_bass", fail_analyze)

    with pytest.raises(RuntimeError, match="pYIN failed"):
        desktop_runner.desktop_command_runner(["cdlc", "transcribe-bass", str(project)])

    payload = json.loads(
        (project / "review" / desktop_runner._TASK_STATUS_NAME).read_text(encoding="utf-8")
    )
    assert payload["status"] == "error"
    assert "pYIN failed" in payload["message"]


def test_worker_entry_persists_exception_details(monkeypatch, tmp_path: Path) -> None:
    result_path = tmp_path / "worker-result.json"
    monkeypatch.setenv(desktop_runner._DESKTOP_WORKER_RESULT_ENV, str(result_path))

    def fail_runner(argv):
        raise ValueError("bad worker input")

    monkeypatch.setattr(desktop_runner, "desktop_command_runner", fail_runner)

    assert desktop_runner.run_desktop_worker(["cdlc", "transcribe-bass", "project"]) == 1
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["status"] == "error"
    assert payload["error_type"] == "ValueError"
    assert payload["message"] == "bad worker input"
    assert "ValueError: bad worker input" in payload["traceback"]


def test_non_packaged_desktop_keeps_existing_in_process_dispatch(monkeypatch, tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    called: dict[str, object] = {}

    monkeypatch.delattr(desktop_runner.sys, "frozen", raising=False)
    monkeypatch.delenv(desktop_runner._DESKTOP_WORKER_ENV, raising=False)

    def fail_subprocess(*args, **kwargs):
        raise AssertionError("Development/test execution should not re-enter sys.executable")

    monkeypatch.setattr(desktop_runner.subprocess, "run", fail_subprocess)

    def fake_analyze(project_dir: Path, *, engine: str, progress_callback=None):
        called["project"] = project_dir
        called["engine"] = engine
        assert progress_callback is not None
        return {}

    monkeypatch.setattr(desktop_runner, "analyze_project_bass", fake_analyze)

    result = desktop_runner.desktop_command_runner(["cdlc", "transcribe-bass", str(project)])

    assert result == 0
    assert called == {"project": project.resolve(), "engine": "librosa-pyin"}
