from __future__ import annotations

from pathlib import Path

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

    def fake_analyze(project_dir: Path, *, engine: str):
        called["project"] = project_dir
        called["engine"] = engine
        return {}

    monkeypatch.setattr(desktop_runner, "analyze_project_bass", fake_analyze)

    result = desktop_runner.desktop_command_runner(
        ["cdlc", "transcribe-bass", str(project), "--engine", "librosa-pyin"]
    )

    assert result == 0
    assert called == {"project": project.resolve(), "engine": "librosa-pyin"}


def test_non_packaged_desktop_keeps_existing_in_process_dispatch(monkeypatch, tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    called: dict[str, object] = {}

    monkeypatch.delattr(desktop_runner.sys, "frozen", raising=False)
    monkeypatch.delenv(desktop_runner._DESKTOP_WORKER_ENV, raising=False)

    def fail_subprocess(*args, **kwargs):
        raise AssertionError("Development/test execution should not re-enter sys.executable")

    monkeypatch.setattr(desktop_runner.subprocess, "run", fail_subprocess)

    def fake_analyze(project_dir: Path, *, engine: str):
        called["project"] = project_dir
        called["engine"] = engine
        return {}

    monkeypatch.setattr(desktop_runner, "analyze_project_bass", fake_analyze)

    result = desktop_runner.desktop_command_runner(["cdlc", "transcribe-bass", str(project)])

    assert result == 0
    assert called == {"project": project.resolve(), "engine": "librosa-pyin"}
