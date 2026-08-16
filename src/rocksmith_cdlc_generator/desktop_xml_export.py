from __future__ import annotations

from pathlib import Path
from typing import Literal

from .authoring_export import export_project_bass_authoring, export_project_guitar_authoring

ArrangementName = Literal["bass", "lead", "rhythm"]


def export_project_arrangement_xml(
    project_dir: Path,
    *,
    arrangement: ArrangementName,
) -> dict[str, Path]:
    """Run the existing validation-gated Rocksmith XML exporter for one arrangement.

    This adapter intentionally exports one arrangement at a time. It adds no new review
    authority and does not weaken the underlying Bass or guitar packaging/validation gates.
    """

    project = project_dir.expanduser().resolve()
    if arrangement == "bass":
        return export_project_bass_authoring(project)
    if arrangement in {"lead", "rhythm"}:
        return export_project_guitar_authoring(project, arrangement=arrangement)
    raise ValueError(f"Unsupported Rocksmith XML arrangement: {arrangement}")
