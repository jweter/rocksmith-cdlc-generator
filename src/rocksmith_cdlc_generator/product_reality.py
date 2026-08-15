from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import ProjectManifest
from .score_source import ProjectScoreSource

ArrangementName = Literal["bass", "lead", "rhythm"]
CorrectionCategory = Literal[
    "timing",
    "position",
    "technique",
    "chord_fingering",
    "chord_identity",
    "other",
]
ObservationSeverity = Literal["note", "friction", "blocker"]
GateResult = Literal["pending", "pass", "fail"]

PRODUCT_REALITY_DIR = Path("diagnostics") / "product-reality"
ACTIVE_SESSION_PATH = PRODUCT_REALITY_DIR / "active-session.json"


class ProductRealityStageRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    counts_as_editing: bool
    started_at: datetime
    completed_at: datetime
    elapsed_seconds: float = Field(ge=0)


class ProductRealityCorrectionCount(BaseModel):
    model_config = ConfigDict(frozen=True)

    arrangement: ArrangementName
    category: CorrectionCategory
    count: int = Field(ge=1)


class ProductRealityObservation(BaseModel):
    model_config = ConfigDict(frozen=True)

    area: str = Field(min_length=1)
    severity: ObservationSeverity
    text: str = Field(min_length=1)
    requires_cli_or_powershell: bool = False
    recorded_at: datetime


class ProductRealitySession(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    session_id: str
    project_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    recording_duration_seconds: float = Field(gt=0)
    score_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    score_format: str | None = None
    packaged_build_id: str | None = None
    started_at: datetime
    active_stage_name: str | None = None
    active_stage_counts_as_editing: bool | None = None
    active_stage_started_at: datetime | None = None
    stages: list[ProductRealityStageRecord] = Field(default_factory=list)
    corrections: list[ProductRealityCorrectionCount] = Field(default_factory=list)
    observations: list[ProductRealityObservation] = Field(default_factory=list)
    gate_result: GateResult = "pending"
    gate_reason: str | None = None
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_state(self) -> "ProductRealitySession":
        active = (
            self.active_stage_name,
            self.active_stage_counts_as_editing,
            self.active_stage_started_at,
        )
        if any(item is not None for item in active) and not all(item is not None for item in active):
            raise ValueError("active Product Reality stage state is incomplete")
        if self.completed_at is not None and self.active_stage_name is not None:
            raise ValueError("completed Product Reality session cannot have an active stage")
        if self.completed_at is None and self.gate_result != "pending":
            raise ValueError("unfinished Product Reality session cannot have a final gate result")
        if self.completed_at is not None and self.gate_result == "pending":
            raise ValueError("completed Product Reality session requires pass/fail")
        keys = [(item.arrangement, item.category) for item in self.corrections]
        if len(keys) != len(set(keys)):
            raise ValueError("Product Reality correction counters must be unique by arrangement/category")
        return self

    @property
    def measured_work_seconds(self) -> float:
        return sum(item.elapsed_seconds for item in self.stages)

    @property
    def editing_seconds(self) -> float:
        return sum(item.elapsed_seconds for item in self.stages if item.counts_as_editing)

    @property
    def editing_minutes_per_finished_minute(self) -> float:
        return self.editing_seconds / self.recording_duration_seconds

    @property
    def total_corrections(self) -> int:
        return sum(item.count for item in self.corrections)

    @property
    def cli_workaround_count(self) -> int:
        return sum(1 for item in self.observations if item.requires_cli_or_powershell)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _active_path(project: Path) -> Path:
    return project / ACTIVE_SESSION_PATH


def _write_json_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def _save_active(project: Path, session: ProductRealitySession) -> ProductRealitySession:
    _write_json_atomic(_active_path(project), session.model_dump_json(indent=2) + "\n")
    return session


def load_active_product_reality_session(project_dir: Path) -> ProductRealitySession | None:
    project = project_dir.expanduser().resolve()
    path = _active_path(project)
    if not path.is_file():
        return None
    return ProductRealitySession.model_validate_json(path.read_text(encoding="utf-8"))


def start_product_reality_session(
    project_dir: Path,
    *,
    packaged_build_id: str | None = None,
    started_at: datetime | None = None,
) -> ProductRealitySession:
    """Start one local evidence session without creating musical authority."""

    project = project_dir.expanduser().resolve()
    if load_active_product_reality_session(project) is not None:
        raise ValueError("A Product Reality session is already active for this project")
    manifest = ProjectManifest.load(project)
    score_path = project / "sources" / "score" / "source.json"
    score = ProjectScoreSource.read_json(score_path) if score_path.is_file() else None
    session = ProductRealitySession(
        session_id=str(uuid4()),
        project_source_sha256=manifest.source_sha256,
        recording_duration_seconds=manifest.source_metadata.duration_seconds,
        score_sha256=None if score is None else score.source_sha256,
        score_format=None if score is None else score.source_format,
        packaged_build_id=(packaged_build_id or "").strip() or None,
        started_at=started_at or _now(),
    )
    return _save_active(project, session)


def start_product_reality_stage(
    project_dir: Path,
    *,
    name: str,
    counts_as_editing: bool,
    started_at: datetime | None = None,
) -> ProductRealitySession:
    project = project_dir.expanduser().resolve()
    session = load_active_product_reality_session(project)
    if session is None:
        raise ValueError("No Product Reality session is active")
    if session.active_stage_name is not None:
        raise ValueError(f"Product Reality stage '{session.active_stage_name}' is already running")
    stage_name = name.strip()
    if not stage_name:
        raise ValueError("Product Reality stage name cannot be empty")
    updated = session.model_copy(
        update={
            "active_stage_name": stage_name,
            "active_stage_counts_as_editing": bool(counts_as_editing),
            "active_stage_started_at": started_at or _now(),
        }
    )
    return _save_active(project, updated)


def stop_product_reality_stage(
    project_dir: Path,
    *,
    completed_at: datetime | None = None,
) -> ProductRealitySession:
    project = project_dir.expanduser().resolve()
    session = load_active_product_reality_session(project)
    if session is None or session.active_stage_name is None or session.active_stage_started_at is None:
        raise ValueError("No Product Reality stage is active")
    end = completed_at or _now()
    elapsed = (end - session.active_stage_started_at).total_seconds()
    if elapsed < 0:
        raise ValueError("Product Reality stage completion cannot precede its start")
    record = ProductRealityStageRecord(
        name=session.active_stage_name,
        counts_as_editing=bool(session.active_stage_counts_as_editing),
        started_at=session.active_stage_started_at,
        completed_at=end,
        elapsed_seconds=elapsed,
    )
    updated = session.model_copy(
        update={
            "active_stage_name": None,
            "active_stage_counts_as_editing": None,
            "active_stage_started_at": None,
            "stages": [*session.stages, record],
        }
    )
    return _save_active(project, updated)


def increment_product_reality_correction(
    project_dir: Path,
    *,
    arrangement: ArrangementName,
    category: CorrectionCategory,
) -> ProductRealitySession:
    project = project_dir.expanduser().resolve()
    session = load_active_product_reality_session(project)
    if session is None:
        raise ValueError("No Product Reality session is active")
    counts = {(item.arrangement, item.category): item.count for item in session.corrections}
    key = (arrangement, category)
    counts[key] = counts.get(key, 0) + 1
    corrections = [
        ProductRealityCorrectionCount(arrangement=role, category=kind, count=count)
        for (role, kind), count in sorted(counts.items())
    ]
    return _save_active(project, session.model_copy(update={"corrections": corrections}))


def add_product_reality_observation(
    project_dir: Path,
    *,
    area: str,
    severity: ObservationSeverity,
    text: str,
    requires_cli_or_powershell: bool = False,
    recorded_at: datetime | None = None,
) -> ProductRealitySession:
    project = project_dir.expanduser().resolve()
    session = load_active_product_reality_session(project)
    if session is None:
        raise ValueError("No Product Reality session is active")
    observation = ProductRealityObservation(
        area=area.strip(),
        severity=severity,
        text=text.strip(),
        requires_cli_or_powershell=requires_cli_or_powershell,
        recorded_at=recorded_at or _now(),
    )
    return _save_active(
        project,
        session.model_copy(update={"observations": [*session.observations, observation]}),
    )


def _report_markdown(session: ProductRealitySession) -> str:
    lines = [
        "# Product Reality Gate session",
        "",
        f"- Session: `{session.session_id}`",
        f"- Gate result: **{session.gate_result.upper()}**",
        f"- Recording duration: {session.recording_duration_seconds / 60.0:.2f} min",
        f"- Measured work time: {session.measured_work_seconds / 60.0:.2f} min",
        f"- Editing time: {session.editing_seconds / 60.0:.2f} min",
        f"- Editing minutes per finished minute: {session.editing_minutes_per_finished_minute:.3f}",
        f"- Total corrections: {session.total_corrections}",
        f"- CLI/PowerShell workarounds recorded: {session.cli_workaround_count}",
        "",
        "## Stage timings",
        "",
    ]
    if session.stages:
        for item in session.stages:
            suffix = " (editing)" if item.counts_as_editing else ""
            lines.append(f"- {item.name}: {item.elapsed_seconds / 60.0:.2f} min{suffix}")
    else:
        lines.append("- None recorded")
    lines.extend(["", "## Corrections", ""])
    if session.corrections:
        for item in session.corrections:
            lines.append(f"- {item.arrangement} / {item.category.replace('_', ' ')}: {item.count}")
    else:
        lines.append("- None recorded")
    lines.extend(["", "## Observations", ""])
    if session.observations:
        for item in session.observations:
            workaround = " [CLI/PowerShell workaround]" if item.requires_cli_or_powershell else ""
            lines.append(f"- **{item.severity}** · {item.area}: {item.text}{workaround}")
    else:
        lines.append("- None recorded")
    lines.extend(["", "## Gate decision", "", session.gate_reason or "No gate reason supplied.", ""])
    return "\n".join(lines)


def finish_product_reality_session(
    project_dir: Path,
    *,
    result: Literal["pass", "fail"],
    reason: str,
    completed_at: datetime | None = None,
) -> tuple[ProductRealitySession, Path, Path]:
    project = project_dir.expanduser().resolve()
    session = load_active_product_reality_session(project)
    if session is None:
        raise ValueError("No Product Reality session is active")
    if session.active_stage_name is not None:
        raise ValueError("Stop the active Product Reality stage before completing the session")
    reason_text = reason.strip()
    if not reason_text:
        raise ValueError("Product Reality pass/fail requires an explicit reason")
    completed = session.model_copy(
        update={
            "gate_result": result,
            "gate_reason": reason_text,
            "completed_at": completed_at or _now(),
        }
    )
    directory = project / PRODUCT_REALITY_DIR
    json_path = directory / f"session-{completed.session_id}.json"
    markdown_path = directory / f"session-{completed.session_id}.md"
    _write_json_atomic(json_path, completed.model_dump_json(indent=2) + "\n")
    _write_json_atomic(markdown_path, _report_markdown(completed))
    _active_path(project).unlink(missing_ok=True)
    return completed, json_path, markdown_path
