from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Mapping

DLCBUILDER_EXE_ENV = "ROCKSMITH_DLCBUILDER_EXE"


def _existing_executable(value: str | os.PathLike[str] | None) -> Path | None:
    if value is None:
        return None
    text = str(value).strip().strip('"')
    if not text:
        return None
    path = Path(text).expanduser().resolve()
    return path if path.is_file() else None


def discover_dlcbuilder_executable(
    *,
    environ: Mapping[str, str] | None = None,
) -> Path | None:
    """Resolve DLC Builder from an explicit environment override or PATH.

    The desktop intentionally does not scan arbitrary directories or Rocksmith locations.
    DLC Builder is an external authoring tool, so discovery stays opt-in/predictable.
    """

    environment = os.environ if environ is None else environ
    explicit = _existing_executable(environment.get(DLCBUILDER_EXE_ENV))
    if explicit is not None:
        return explicit

    for command in ("DLCBuilder.exe", "DLCBuilder"):
        discovered = shutil.which(command)
        candidate = _existing_executable(discovered)
        if candidate is not None:
            return candidate
    return None


def require_dlcbuilder_executable(value: str | os.PathLike[str]) -> Path:
    path = _existing_executable(value)
    if path is None:
        raise FileNotFoundError(f"DLC Builder executable not found: {value}")
    if os.name == "nt" and path.suffix.lower() != ".exe":
        raise ValueError("DLC Builder executable must be a Windows .exe file")
    return path
