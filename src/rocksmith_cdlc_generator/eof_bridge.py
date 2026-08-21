from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .score_mapping_review import load_score_for_mapping_review

_SUPPORTED_EOF_SCORE_FORMATS = {"gp3", "gp4", "gp5"}
_SUPPORTED_EOF_SUFFIXES = {".gp3", ".gp4", ".gp5"}
_EOF_ENV_VARS = ("ROCKSMITH_CDLC_EOF_EXE", "EOF_EXE")


class EOFBridgeError(RuntimeError):
    """Raised when the optional Editor on Fire reference bridge cannot launch safely."""


def discover_eof_executable(explicit: Path | str | None = None) -> Path | None:
    """Return a verified EOF executable without scanning arbitrary user directories.

    Discovery is intentionally narrow: an explicit path, one of the documented
    environment variables, or an executable already on PATH. The project does not
    download, install, modify, or bundle EOF automatically.
    """

    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(Path(explicit).expanduser())
    for variable in _EOF_ENV_VARS:
        value = os.environ.get(variable)
        if value:
            candidates.append(Path(value).expanduser())
    for command in ("eof.exe", "eof"):
        located = shutil.which(command)
        if located:
            candidates.append(Path(located))

    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved
    return None


def resolve_registered_score_for_eof(project_dir: Path) -> Path:
    """Resolve the immutable project-local GP3/GP4/GP5 score EOF should inspect."""

    project = project_dir.expanduser().resolve()
    score = load_score_for_mapping_review(project)
    if score.source_format not in _SUPPORTED_EOF_SCORE_FORMATS:
        raise EOFBridgeError(
            f"EOF reference launch currently supports registered GP3/GP4/GP5 scores; "
            f"this project uses {score.source_format}."
        )

    relative = Path(score.imported_relative_path)
    if relative.is_absolute():
        raise EOFBridgeError("Registered score path must remain inside the project")
    stored = (project / relative).resolve()
    if not stored.is_relative_to(project):
        raise EOFBridgeError("Registered score path must remain inside the project")
    if stored.suffix.lower() not in _SUPPORTED_EOF_SUFFIXES:
        raise EOFBridgeError(f"EOF cannot import registered score extension {stored.suffix!r} through this bridge")
    if not stored.is_file():
        raise EOFBridgeError(f"Registered score file is missing: {stored}")
    return stored


def build_eof_launch_command(
    project_dir: Path,
    *,
    eof_executable: Path | str | None = None,
) -> list[str]:
    """Build the argv used to open the project's reviewed score in EOF."""

    executable = discover_eof_executable(eof_executable)
    if executable is None:
        raise EOFBridgeError(
            "Editor on Fire was not found. Set ROCKSMITH_CDLC_EOF_EXE to eof.exe, "
            "pass an explicit executable path, or place eof.exe on PATH."
        )
    score_path = resolve_registered_score_for_eof(project_dir)
    return [str(executable), str(score_path)]


def launch_project_score_in_eof(
    project_dir: Path,
    *,
    eof_executable: Path | str | None = None,
) -> subprocess.Popen[bytes]:
    """Launch EOF as an optional external reference view of the registered score.

    EOF remains a review/oracle tool. Launching it does not accept mappings, change
    project authority, rewrite generated charts, or bypass validation gates.
    """

    command = build_eof_launch_command(project_dir, eof_executable=eof_executable)
    executable = Path(command[0])
    return subprocess.Popen(command, cwd=str(executable.parent))
