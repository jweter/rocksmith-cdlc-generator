from __future__ import annotations

from pathlib import Path

from .alignment import align_project_source
from .guitar_validation import validate_guitar_project, validate_guitar_project_to_disk
from .mapping_pipeline import map_project_bass
from .project import normalize_project
from .reconciliation import reconcile_project_bass
from .score_fanout import fanout_confirmed_score_mappings
from .shared_guitar import build_project_shared_guitar_chart
from .tempo_pipeline import analyze_project_tempo
from .transcription_pipeline import analyze_project_bass
from .validation import validate_project, validate_project_to_disk


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


def desktop_command_runner(argv: list[str]) -> int:
    """Execute planner-owned automatic work in-process for the packaged desktop app.

    The normal workflow runner still decides what is eligible to run. This adapter is
    intentionally a closed dispatcher: it never invokes a shell, does not accept arbitrary
    programs, and maps only deterministic planner commands to the same core functions used
    by the CLI. Keeping execution in-process is required for a PyInstaller Windows build,
    where ``sys.executable`` is the GUI executable rather than a Python interpreter.
    """

    if not argv:
        raise ValueError("Empty desktop workflow command")

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
        build_project_shared_guitar_chart(project, arrangement=instrument)
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
        analyze_project_bass(
            project,
            engine=_option(argv, "--engine", "librosa-pyin") or "librosa-pyin",
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
