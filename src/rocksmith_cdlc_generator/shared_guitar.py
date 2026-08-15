from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .guitar_authoring import GuitarAuthoringChart, build_guitar_authoring_chart
from .hashing import sha256_file
from .package_generation import bump_package_generation
from .reviewed_chords import current_reviewed_chords_sha256, reviewed_chord_groups
from .reviewed_event_timing import (
    apply_reviewed_event_timing_to_source,
    current_reviewed_event_timing_sha256,
)
from .reviewed_positions import apply_reviewed_positions, current_reviewed_positions_sha256
from .reviewed_techniques import (
    apply_reviewed_techniques_to_source,
    current_reviewed_techniques_sha256,
)
from .score_source import ArrangementRole
from .shared_timeline import alignment_for_role, load_current_shared_timeline
from .source_import import ImportedSource

SharedGuitarRole = Literal["lead", "rhythm"]


class SharedGuitarDraftManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    arrangement: SharedGuitarRole
    recording_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    shared_timeline_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_path: str
    source_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_track_index: int = Field(ge=0)
    position_review_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    event_timing_review_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    technique_review_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    chord_review_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
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
    # Publish a new package generation before stale package files are removed. A
    # concurrent register-psarc operation bound to the old generation then fails closed.
    bump_package_generation(project)
    for relative in (
        f"review/{arrangement}_validation_report.json",
        f"review/{arrangement}_flags.json",
        f"review/{arrangement}_summary.md",
        f"eof/arr_{arrangement}_RS2.xml",
        f"eof/{arrangement}_export_manifest.json",
        f"eof/{arrangement.upper()}_README.md",
    ):
        (project / relative).unlink(missing_ok=True)
    for stale_dir in (project / "build" / "dlcbuilder", project / "build" / "staging"):
        if stale_dir.exists():
            shutil.rmtree(stale_dir)
        if stale_dir.exists():
            raise OSError(f"Failed to invalidate stale package staging: {stale_dir}")


def build_project_shared_guitar_chart(project_dir: Path, *, arrangement: SharedGuitarRole) -> Path:
    project = project_dir.expanduser().resolve()
    timeline = load_current_shared_timeline(project)
    timeline_path = _shared_timeline_path(project)
    role = _role(arrangement)
    alignment = alignment_for_role(project, role)
    source_path = _safe_project_file(project, Path(alignment.source_path))
    source = ImportedSource.read_json(source_path)
    reviewed_source, _applied_positions = apply_reviewed_positions(
        project,
        source,
        arrangement=arrangement,
        source_track_index=alignment.track_index,
    )
    reviewed_source, _applied_timing = apply_reviewed_event_timing_to_source(
        project,
        reviewed_source,
        arrangement=arrangement,
        source_track_index=alignment.track_index,
    )
    reviewed_source, _applied_techniques = apply_reviewed_techniques_to_source(
        project,
        reviewed_source,
        arrangement=arrangement,
        source_track_index=alignment.track_index,
    )
    explicit_chords = reviewed_chord_groups(
        project,
        arrangement=arrangement,
        source_track_index=alignment.track_index,
    )
    chart = build_guitar_authoring_chart(
        reviewed_source,
        alignment,
        arrangement=arrangement,
        track_index=alignment.track_index,
        reviewed_chord_groups=explicit_chords,
    )
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
        position_review_sha256=current_reviewed_positions_sha256(project),
        event_timing_review_sha256=current_reviewed_event_timing_sha256(project),
        technique_review_sha256=current_reviewed_techniques_sha256(project),
        chord_review_sha256=current_reviewed_chords_sha256(project),
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
    if manifest.position_review_sha256 != current_reviewed_positions_sha256(project):
        raise ValueError(f"shared {arrangement} draft reviewed-position layer is stale")
    if manifest.event_timing_review_sha256 != current_reviewed_event_timing_sha256(project):
        raise ValueError(f"shared {arrangement} draft reviewed-event-timing layer is stale")
    if manifest.technique_review_sha256 != current_reviewed_techniques_sha256(project):
        raise ValueError(f"shared {arrangement} draft reviewed-technique layer is stale")
    if manifest.chord_review_sha256 != current_reviewed_chords_sha256(project):
        raise ValueError(f"shared {arrangement} draft reviewed-chord layer is stale")
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
