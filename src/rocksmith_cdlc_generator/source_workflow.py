from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .guitarpro_import import import_project_guitarpro
from .midi_import import import_project_midi
from .musicxml_import import import_project_musicxml
from .project import create_project
from .psarc_import import import_project_psarc
from .source_intake import SourceIntakeDescriptor, SourceRightsClass
from .source_router import SourceRoute, route_local_source


class AddSourceResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["complete", "queued"]
    route: SourceRoute
    output_path: str | None = None
    human_rights_review_required: bool


def add_local_source(
    source: Path,
    *,
    project: Path | None = None,
    title: str | None = None,
    artist: str | None = None,
    instruments: list[str] | None = None,
    projects_root: Path = Path("projects"),
    rights_class: SourceRightsClass = SourceRightsClass.unknown,
    license_note: str | None = None,
    instrument: Literal["bass", "lead", "rhythm"] = "bass",
    track_index: int | None = None,
    part_index: int | None = None,
    bridge_path: Path | None = None,
) -> AddSourceResult:
    """Route and execute one explicitly supplied local source.

    This is deliberately local-only. Streaming/video references belong to the
    reference-discovery path and are never converted into ingest bytes here.
    """

    source = source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if rights_class is SourceRightsClass.streaming_reference_only:
        raise ValueError("streaming-reference-only material cannot be added as local source bytes")

    route = route_local_source(
        source,
        rights_class=rights_class,
        license_note=license_note,
    )
    review_required = route.descriptor.requires_human_rights_review

    if route.action == "reject_unknown":
        raise ValueError(route.reason)

    if route.action == "queue_adapter":
        return AddSourceResult(
            status="queued",
            route=route,
            human_rights_review_required=review_required,
        )

    if route.action == "project_audio":
        if project is not None:
            raise ValueError("audio project creation does not accept --project; omit it for a new project")
        if title is None or not title.strip():
            raise ValueError("recognized audio requires --title so a new project can be created")
        output = create_project(
            audio=source,
            projects_root=projects_root,
            artist=artist,
            title=title.strip(),
            instruments=instruments or ["bass"],
        )
    else:
        if project is None:
            raise ValueError(f"{route.descriptor.source_format.value} import requires --project")
        project = project.expanduser().resolve()
        if route.action == "import_midi":
            output = import_project_midi(
                project,
                source,
                track_index=track_index,
                instrument=instrument,
            )
        elif route.action == "import_guitarpro":
            output = import_project_guitarpro(
                project,
                source,
                track_index=track_index,
                instrument=instrument,
            )
        elif route.action == "import_musicxml":
            output = import_project_musicxml(
                project,
                source,
                part_index=part_index,
                instrument=instrument,
            )
        elif route.action == "import_psarc":
            if instrument != "bass":
                raise ValueError("current PSARC bridge imports Bass arrangements only")
            output = import_project_psarc(project, source, bridge_path=bridge_path)
        else:  # pragma: no cover - SourceRoute constrains executable actions.
            raise ValueError(f"No executor registered for route {route.action}")

    return AddSourceResult(
        status="complete",
        route=route,
        output_path=str(output),
        human_rights_review_required=review_required,
    )
