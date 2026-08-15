from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .guitar_authoring import GuitarAuthoringChart, build_guitar_authoring_chart
from .hashing import sha256_file
from .score_source import ArrangementRole
from .shared_timeline import alignment_for_role, load_current_shared_timeline
from .source_import import ImportedSource


SharedGuitarRole = Literal["lead", "rhythm"]


class SharedGuitarDraftManifest(BaseModel):
    """Provenance binding for a guitar chart derived from the shared song timeline."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    arrangement: SharedGuitarRole
    recording_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    shared_timeline_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_path: str
    source_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_track_index: int = Field(ge=0)
    chart_path: str
    chart_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path

    @classmethod
    def read_json(cls, path: Path) -> "SharedGuitarDraftManifest":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


def _role(arrangement: SharedGuitarRole) -> ArrangementRole:
    return ArrangementRole.lead if arrangement == "lead" else ArrangementRole.rhythm


def _safe_project_file(project: Path, path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_relative_to(project):
        raise ValueError("shared guitar source escaped the project directory")
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return resolved


def _shared_timeline_path(project: Path) -> Path:
    path = project / "analysis" / "shared_timeline.json"
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _invalidate_guitar_derivatives(project: Path, arrangement: SharedGuitarRole) -> None:
    """Fail closed while removing outputs that can reference the previous guitar chart."""

    for relative in (
        f"review/{arrangement}_validation_report.json",
        f"review/{arrangement}_flags.json",
        f"review/{arrangement}_summary.md",
        f"eof/arr_{arrangement}_RS2.xml",
        f"eof/{arrangement}_export_manifest.json",
        f"eof/{arrangement.upper()}_README.md",
    ):
        (project / relative).unlink(missing_ok=True)

    # Any rebuilt arrangement invalidates the combined package state. Remove both the
    # DLC Builder project and downstream staged/registered PSARC receipts so no stale
    # package remains marked safe for manual installation after chart timing changes.
    for stale_dir in (project / "build" / "dlcbuilder", project / "build" / "staging"):
        if stale_dir.exists():
            shutil.rmtree(stale_dir)
        if stale_dir.exists():
            raise OSError(f"Failed to invalidate stale package staging: {stale_dir}")


def build_project_shared_guitar_chart(
    project_dir: Path,
    *,
    arrangement: SharedGuitarRole,
) -> Path:
    """Build Lead/Rhythm from the current score fan-out using one shared timeline.

    No arrangement-local alignment decision is made here. The current shared timeline
    supplies timing and the human-confirmed score fan-out supplies the exact guitar
    source track. Existing string/fret positions and uncertainty gates are preserved by
    the normal guitar authoring pipeline.
    """

    project = project_dir.expanduser().resolve()
    timeline = load_current_shared_timeline(project)
    timeline_path = _shared_timeline_path(project)
    role = _role(arrangement)
    alignment = alignment_for_role(project, role)
    source_path = _safe_project_file(project, Path(alignment.source_path))
    source = ImportedSource.read_json(source_path)

    chart = build_guitar_authoring_chart(
        source,
        alignment,
        arrangement=arrangement,
        track_index=alignment.track_index,
    )

    # Only invalidate downstream artifacts after a replacement chart has been built in
    # memory successfully. If invalidation fails, abort before replacing the current chart.
    _invalidate_guitar_derivatives(project, arrangement)

    chart_path = project / "charts" / f"{arrangement}_source.json"
    chart.write_json(chart_path)

    manifest = SharedGuitarDraftManifest(
        arrangement=arrangement,
        recording_sha256=timeline.recording_sha256,
        score_sha256=timeline.score_sha256,
        shared_timeline_sha256=sha256_file(timeline_path),
        source_path=source_path.relative_to(project).as_posix(),
        source_content_sha256=sha256_file(source_path),
        source_track_index=alignment.track_index,
        chart_path=chart_path.relative_to(project).as_posix(),
        chart_sha256=sha256_file(chart_path),
    )
    manifest.write_json(project / "charts" / f"{arrangement}_shared_timeline.json")
    return chart_path


def load_current_shared_guitar_draft(
    project_dir: Path,
    *,
    arrangement: SharedGuitarRole,
) -> tuple[GuitarAuthoringChart, SharedGuitarDraftManifest]:
    """Load a shared-timeline guitar draft only when every authority binding is current."""

    project = project_dir.expanduser().resolve()
    manifest_path = project / "charts" / f"{arrangement}_shared_timeline.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)

    try:
        timeline = load_current_shared_timeline(project)
        timeline_path = _shared_timeline_path(project)
        alignment = alignment_for_role(project, _role(arrangement))
        manifest = SharedGuitarDraftManifest.read_json(manifest_path)
    except (OSError, ValueError, ValidationError) as exc:
        raise ValueError(f"shared {arrangement} draft is not current: {exc}") from exc

    if manifest.arrangement != arrangement:
        raise ValueError(f"shared {arrangement} draft manifest has the wrong arrangement")
    if manifest.recording_sha256 != timeline.recording_sha256:
        raise ValueError(f"shared {arrangement} draft recording is stale")
    if manifest.score_sha256 != timeline.score_sha256:
        raise ValueError(f"shared {arrangement} draft score is stale")
    if manifest.shared_timeline_sha256 != sha256_file(timeline_path):
        raise ValueError(f"shared {arrangement} draft timing transform is stale")
    if manifest.source_track_index != alignment.track_index:
        raise ValueError(f"shared {arrangement} draft track mapping is stale")

    source_path = _safe_project_file(project, project / manifest.source_path)
    if source_path != Path(alignment.source_path).expanduser().resolve():
        raise ValueError(f"shared {arrangement} draft source path is stale")
    if sha256_file(source_path) != manifest.source_content_sha256:
        raise ValueError(f"shared {arrangement} draft source content is stale")

    chart_path = _safe_project_file(project, project / manifest.chart_path)
    if sha256_file(chart_path) != manifest.chart_sha256:
        raise ValueError(f"shared {arrangement} draft chart content changed after generation")
    chart = GuitarAuthoringChart.model_validate_json(chart_path.read_text(encoding="utf-8"))
    if chart.arrangement != arrangement or chart.source_sha256 != timeline.score_sha256:
        raise ValueError(f"shared {arrangement} chart provenance is stale")
    return chart, manifest


def shared_guitar_draft_is_current(project_dir: Path, arrangement: SharedGuitarRole) -> bool:
    try:
        load_current_shared_guitar_draft(project_dir, arrangement=arrangement)
    except (OSError, ValueError, ValidationError):
        return False
    return True
