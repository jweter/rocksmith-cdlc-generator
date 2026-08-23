from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import traceback

from .alignment import align_project_source
from .guitar_validation import validate_guitar_project, validate_guitar_project_to_disk
from .mapping_pipeline import map_project_bass
from .project import normalize_project
from .reconciliation import reconcile_project_bass
from .score_fanout import fanout_confirmed_score_mappings
from .shared_guitar_bounds import build_project_shared_guitar_chart_bounded
from .tempo_pipeline import analyze_project_tempo
from .transcription_pipeline import analyze_project_bass
from .validation import validate_project, validate_project_to_disk


_DESKTOP_WORKER_FLAG = "--desktop-worker"
_DESKTOP_WORKER_ENV = "ROCKSMITH_CDLC_DESKTOP_WORKER"
_DESKTOP_WORKER_RESULT_ENV = "ROCKSMITH_CDLC_DESKTOP_WORKER_RESULT"
_TASK_STATUS_NAME = "automatic_task_status.json"
_TASK_LOG_NAME = "automatic_task_log.jsonl"


def _option(argv: list[str], name: str, default: str | None = None) -> str | None:
    if name not in argv:
        return default
    index = argv.index(name)
    if index + 1 >= len(argv):
        raise ValueError(f"Missing value for {name}")
    return argv[index + 1]


def _project(argv: list[str], index: int) -> Path:
    try:
        return Path(argv[index]).expanduser().resolve()
    except IndexError as exc:
        raise ValueError("Desktop workflow command is missing its project path") from exc


def _should_isolate_packaged_bass_transcription(argv: list[str]) -> bool:
    return (
        getattr(sys, "frozen", False)
        and os.environ.get(_DESKTOP_WORKER_ENV) != "1"
        and len(argv) >= 3
        and argv[0] == "cdlc"
        and argv[1] == "transcribe-bass"
    )


def _write_worker_result(payload: dict[str, object]) -> None:
    result_path = os.environ.get(_DESKTOP_WORKER_RESULT_ENV)
    if not result_path:
        return
    Path(result_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_task_status(
    project: Path,
    *,
    status: str,
    percent: float,
    message: str,
    started_at: float,
) -> None:
    review_dir = project / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "task": "Generate audio-derived Bass draft",
        "status": status,
        "percent": max(0.0, min(100.0, float(percent))),
        "message": message,
        "started_at": started_at,
        "updated_at": time.time(),
    }
    destination = review_dir / _TASK_STATUS_NAME
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(destination)
    with (review_dir / _TASK_LOG_NAME).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, separators=(",", ":")) + "\n")


def run_desktop_worker(argv: list[str]) -> int:
    """Execute one closed desktop command and persist its result for the GUI parent."""

    try:
        return_code = desktop_command_runner(argv)
    except Exception as exc:
        _write_worker_result(
            {
                "status": "error",
                "error_type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
        return 1
    _write_worker_result({"status": "ok", "return_code": return_code})
    return return_code


def _run_packaged_worker(argv: list[str]) -> int:
    """Run one planner-owned command outside the packaged GUI process."""

    env = os.environ.copy()
    env[_DESKTOP_WORKER_ENV] = "1"
    with tempfile.NamedTemporaryFile(
        prefix="rocksmith-cdlc-worker-",
        suffix=".json",
        delete=False,
    ) as handle:
        result_path = Path(handle.name)
    env[_DESKTOP_WORKER_RESULT_ENV] = str(result_path)

    try:
        process = subprocess.run(
            [sys.executable, _DESKTOP_WORKER_FLAG, *argv],
            check=False,
            env=env,
            creationflags=getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0),
        )
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError) as exc:
            raise RuntimeError(
                f"Packaged Bass transcription worker exited without a readable result (exit code {process.returncode})."
            ) from exc

        if payload.get("status") == "error":
            error_type = payload.get("error_type") or "WorkerError"
            message = payload.get("message") or "Unknown packaged worker failure"
            worker_traceback = payload.get("traceback") or ""
            details = f"{error_type}: {message}"
            if worker_traceback:
                details += f"\n\nWorker traceback:\n{worker_traceback}"
            raise RuntimeError(details)

        if payload.get("status") != "ok":
            raise RuntimeError("Packaged Bass transcription worker returned an invalid result payload.")
        return_code = payload.get("return_code")
        if not isinstance(return_code, int):
            raise RuntimeError("Packaged Bass transcription worker result omitted its return code.")
        if return_code != process.returncode:
            raise RuntimeError(
                "Packaged Bass transcription worker return code did not match its result payload."
            )
        return return_code
    finally:
        result_path.unlink(missing_ok=True)


def desktop_command_runner(argv: list[str]) -> int:
    """Execute planner-owned automatic work for the packaged desktop app.

    The normal workflow runner remains authoritative. The dispatcher never invokes a
    shell and accepts only deterministic planner commands. CPU-heavy packaged Bass
    transcription is isolated into a below-normal-priority child process and publishes
    media-free task status so the GUI can show live progress while long-song analysis runs.
    """

    if not argv:
        raise ValueError("Empty desktop workflow command")

    if _should_isolate_packaged_bass_transcription(argv):
        return _run_packaged_worker(argv)

    if argv[0] == "cdlc-score-fanout":
        if len(argv) != 2:
            raise ValueError("Unexpected score fan-out arguments")
        fanout_confirmed_score_mappings(_project(argv, 1))
        return 0

    if argv[0] == "cdlc-build-shared-guitar":
        project = _project(argv, 1)
        instrument = _option(argv, "--instrument")
        if instrument not in {"lead", "rhythm"}:
            raise ValueError("Shared guitar build requires Lead or Rhythm")
        build_project_shared_guitar_chart_bounded(project, arrangement=instrument)
        return 0

    if argv[0] != "cdlc" or len(argv) < 3:
        raise ValueError(f"Unsupported desktop workflow command: {' '.join(argv)}")

    command = argv[1]
    project = _project(argv, 2)

    if command == "normalize":
        normalize_project(project)
        return 0

    if command == "tempo":
        analyze_project_tempo(project, engine=_option(argv, "--engine", "librosa") or "librosa")
        return 0

    if command == "transcribe-bass":
        started_at = time.time()

        def report_progress(percent: float, message: str) -> None:
            _write_task_status(
                project,
                status="running",
                percent=percent,
                message=message,
                started_at=started_at,
            )

        report_progress(0.0, "Starting Bass transcription worker")
        try:
            analyze_project_bass(
                project,
                engine=_option(argv, "--engine", "librosa-pyin") or "librosa-pyin",
                progress_callback=report_progress,
            )
        except Exception as exc:
            _write_task_status(
                project,
                status="error",
                percent=0.0,
                message=f"Bass transcription failed: {type(exc).__name__}: {exc}",
                started_at=started_at,
            )
            raise
        _write_task_status(
            project,
            status="complete",
            percent=100.0,
            message="Bass transcription complete",
            started_at=started_at,
        )
        return 0

    if command == "align-source":
        source = _option(argv, "--source")
        if source is None:
            raise ValueError("Alignment requires an explicit planner-selected source")
        track_index = _option(argv, "--track-index")
        align_project_source(
            project,
            Path(source),
            track_index=int(track_index) if track_index is not None else None,
        )
        return 0

    if command == "reconcile-bass":
        source = _option(argv, "--source")
        if source is None:
            raise ValueError("Reconciliation requires the previously aligned source")
        reconcile_project_bass(project, Path(source))
        return 0

    if command == "map-bass":
        map_project_bass(
            project,
            tuning_name=_option(argv, "--tuning", "E Standard") or "E Standard",
            max_fret=int(_option(argv, "--max-fret", "24") or "24"),
            source=_option(argv, "--source", "auto") or "auto",
        )
        return 0

    if command == "validate":
        instrument = _option(argv, "--instrument", "bass") or "bass"
        if instrument == "bass":
            report = validate_project(project)
            validate_project_to_disk(project)
        elif instrument in {"lead", "rhythm"}:
            report = validate_guitar_project(project, arrangement=instrument)
            validate_guitar_project_to_disk(project, arrangement=instrument)
        else:
            raise ValueError(f"Unsupported validation arrangement: {instrument}")
        return 0 if report.can_package else 2

    raise ValueError(f"Unsupported desktop workflow command: {' '.join(argv)}")
