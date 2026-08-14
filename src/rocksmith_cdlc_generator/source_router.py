from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .source_intake import (
    AdapterStatus,
    SourceFamily,
    SourceFormat,
    SourceIntakeDescriptor,
    SourceRightsClass,
    describe_local_source,
)

RouteAction = Literal[
    "project_audio",
    "import_midi",
    "import_guitarpro",
    "import_musicxml",
    "import_psarc",
    "queue_adapter",
    "reject_unknown",
]


@dataclass(frozen=True)
class SourceRoute:
    descriptor: SourceIntakeDescriptor
    action: RouteAction
    importer_command: str | None
    reason: str

    @property
    def immediately_processable(self) -> bool:
        return self.action not in {"queue_adapter", "reject_unknown"}


_COMMANDS: dict[SourceFormat, tuple[RouteAction, str]] = {
    SourceFormat.midi: ("import_midi", "import-midi"),
    SourceFormat.gp3: ("import_guitarpro", "import-gp"),
    SourceFormat.gp4: ("import_guitarpro", "import-gp"),
    SourceFormat.gp5: ("import_guitarpro", "import-gp"),
    SourceFormat.musicxml: ("import_musicxml", "import-musicxml"),
    SourceFormat.mxl: ("import_musicxml", "import-musicxml"),
    SourceFormat.psarc: ("import_psarc", "import-psarc"),
}


def route_local_source(
    path: str | Path,
    *,
    rights_class: SourceRightsClass = SourceRightsClass.unknown,
    license_note: str | None = None,
) -> SourceRoute:
    """Classify one user-supplied local file and select the existing workflow adapter.

    Routing does not execute an importer and does not elevate trust. Planned formats
    are retained as queued candidates instead of being rejected or mis-parsed.
    """

    descriptor = describe_local_source(
        path,
        rights_class=rights_class,
        license_note=license_note,
    )

    if descriptor.source_format is SourceFormat.unknown:
        return SourceRoute(
            descriptor=descriptor,
            action="reject_unknown",
            importer_command=None,
            reason="File extension is not recognized by the source intake registry.",
        )

    if descriptor.family is SourceFamily.audio:
        return SourceRoute(
            descriptor=descriptor,
            action="project_audio",
            importer_command="new",
            reason="Recognized audio is routed through immutable project ingest and normalization.",
        )

    command = _COMMANDS.get(descriptor.source_format)
    if command is not None:
        action, importer_command = command
        return SourceRoute(
            descriptor=descriptor,
            action=action,
            importer_command=importer_command,
            reason="An existing source adapter can handle this format.",
        )

    if descriptor.adapter_status is AdapterStatus.planned:
        return SourceRoute(
            descriptor=descriptor,
            action="queue_adapter",
            importer_command=None,
            reason="Format is recognized, but its parser adapter is not implemented yet.",
        )

    return SourceRoute(
        descriptor=descriptor,
        action="queue_adapter",
        importer_command=None,
        reason="Format is recognized but no executable route is registered.",
    )
