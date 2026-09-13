from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .beats import read_tempo_map
from .build_identity import current_build_identity
from .hashing import sha256_file
from .models import ProjectManifest
from .reviewed_arrangement_timing import reviewed_arrangement_timing
from .reviewed_export_events import reviewed_export_arrangement
from .reviewed_timing_transform import map_reviewed_source_time
from .score_source import ArrangementRole
from .timing_review import authoritative_tempo_map_path

ProductRealityStatus = Literal["PASS", "FAIL", "REVIEW_REQUIRED"]


class SharedTimingExpectations(BaseModel):
    model_config = ConfigDict(frozen=True)

    first_playable_seconds: float = Field(ge=0.0)
    first_playable_tolerance_seconds: float = Field(default=0.20, gt=0.0)
    max_arrangement_spread_seconds: float = Field(default=0.05, ge=0.0)
    max_checkpoint_error_seconds: float = Field(default=0.20, gt=0.0)
    max_drift_seconds: float = Field(default=0.20, ge=0.0)


class TimingCheckpoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    source_time_seconds: float = Field(ge=0.0)
    expected_audio_seconds: float = Field(ge=0.0)
    role: ArrangementRole | None = None
    tolerance_seconds: float | None = Field(default=None, gt=0.0)


class PrivateProductRealityScenario(BaseModel):
    """Private local acceptance scenario. Song-specific expectations are test data only."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    scenario_id: str = Field(min_length=1)
    scenario_type: Literal["shared_timing"] = "shared_timing"
    project_dir: Path
    roles: list[ArrangementRole] = Field(
        default_factory=lambda: [
            ArrangementRole.bass,
            ArrangementRole.lead,
            ArrangementRole.rhythm,
        ]
    )
    expected: SharedTimingExpectations
    checkpoints: list[TimingCheckpoint] = Field(default_factory=list)
    human_only_acceptance: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def roles_are_unique(self) -> "PrivateProductRealityScenario":
        if not self.roles:
            raise ValueError("private Product Reality scenario requires at least one arrangement role")
        if len(set(self.roles)) != len(self.roles):
            raise ValueError("private Product Reality scenario roles must be unique")
        return self


class BuildObservation(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: str
    commit_sha: str | None = None
    built_at_utc: str | None = None
    packaged: bool


class RoleTimingObservation(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: ArrangementRole
    source_track_index: int = Field(ge=0)
    first_source_seconds: float = Field(ge=0.0)
    first_playable_seconds: float = Field(ge=0.0)
    note_count: int = Field(gt=0)
    recording_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    timing_points_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CheckpointObservation(BaseModel):
    model_config = ConfigDict(frozen=True)

    checkpoint_id: str
    role: ArrangementRole
    source_time_seconds: float = Field(ge=0.0)
    expected_audio_seconds: float = Field(ge=0.0)
    observed_audio_seconds: float = Field(ge=0.0)


class SharedTimingObservation(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    scenario_id: str
    project_dir: str
    observed_at_utc: str
    build: BuildObservation
    project_recording_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    tempo_map_path: str | None = None
    tempo_map_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    tempo_beat_count: int | None = Field(default=None, ge=0)
    roles: list[RoleTimingObservation] = Field(default_factory=list)
    checkpoints: list[CheckpointObservation] = Field(default_factory=list)
    collection_errors: list[str] = Field(default_factory=list)


class ProductRealityCheck(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    status: ProductRealityStatus
    message: str
    observed: float | str | int | None = None
    expected: float | str | int | None = None


class PrivateProductRealityEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    scenario_id: str
    scenario_type: Literal["shared_timing"] = "shared_timing"
    observed_at_utc: str
    scenario_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    result: ProductRealityStatus
    build: BuildObservation
    project_recording_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    tempo_map_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    role_observations: list[RoleTimingObservation] = Field(default_factory=list)
    checkpoint_observations: list[CheckpointObservation] = Field(default_factory=list)
    checks: list[ProductRealityCheck]
    human_only_acceptance: list[str] = Field(default_factory=list)

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileExistsError(f"Product Reality evidence is append-only; refusing to overwrite {path}")
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path


def _content_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _timing_points_sha256(points: list[object]) -> str:
    normalized = [
        point.model_dump(mode="json") if hasattr(point, "model_dump") else point
        for point in points
    ]
    return _content_sha256(normalized)


def load_private_product_reality_scenario(path: Path) -> PrivateProductRealityScenario:
    scenario_path = path.expanduser().resolve()
    scenario = PrivateProductRealityScenario.model_validate_json(
        scenario_path.read_text(encoding="utf-8")
    )
    project = scenario.project_dir.expanduser()
    if not project.is_absolute():
        project = (scenario_path.parent / project).resolve()
    else:
        project = project.resolve()
    return scenario.model_copy(update={"project_dir": project})


def collect_shared_timing_observation(
    scenario: PrivateProductRealityScenario,
) -> SharedTimingObservation:
    project = scenario.project_dir.expanduser().resolve()
    build_identity = current_build_identity()
    build = BuildObservation(
        version=build_identity.version,
        commit_sha=build_identity.commit_sha,
        built_at_utc=build_identity.built_at_utc,
        packaged=build_identity.packaged,
    )
    errors: list[str] = []

    project_recording_sha256: str | None = None
    try:
        project_recording_sha256 = ProjectManifest.load(project).source_sha256
    except (OSError, ValueError) as exc:
        errors.append(f"project manifest is unavailable or invalid: {exc}")

    tempo_path_text: str | None = None
    tempo_sha256: str | None = None
    tempo_beat_count: int | None = None
    try:
        tempo_path = authoritative_tempo_map_path(project)
        tempo_path_text = str(tempo_path)
        tempo_map = read_tempo_map(tempo_path)
        tempo_beat_count = len(tempo_map.beats)
        tempo_sha256 = sha256_file(tempo_path)
    except (OSError, ValueError) as exc:
        errors.append(f"authoritative tempo map is unavailable or invalid: {exc}")

    role_observations: list[RoleTimingObservation] = []
    timing_by_role: dict[ArrangementRole, object] = {}
    for role in scenario.roles:
        try:
            arrangement = reviewed_export_arrangement(project, role)
            if not arrangement.notes:
                raise ValueError("reviewed arrangement contains no notes")
            timing = reviewed_arrangement_timing(project, role)
            first = arrangement.notes[0]
            role_observations.append(
                RoleTimingObservation(
                    role=role,
                    source_track_index=arrangement.source_track_index,
                    first_source_seconds=first.source_start_seconds,
                    first_playable_seconds=first.reviewed_start_seconds,
                    note_count=len(arrangement.notes),
                    recording_sha256=arrangement.recording_sha256,
                    score_sha256=arrangement.score_sha256,
                    source_output_sha256=arrangement.source_output_sha256,
                    timing_points_sha256=_timing_points_sha256(timing.points),
                )
            )
            timing_by_role[role] = timing
        except (OSError, ValueError) as exc:
            errors.append(f"{role.value} reviewed timing authority is unavailable or stale: {exc}")

    checkpoint_observations: list[CheckpointObservation] = []
    default_role = scenario.roles[0]
    for checkpoint in scenario.checkpoints:
        role = checkpoint.role or default_role
        timing = timing_by_role.get(role)
        if timing is None:
            errors.append(
                f"checkpoint {checkpoint.id} cannot run because {role.value} timing authority is unavailable"
            )
            continue
        try:
            observed = map_reviewed_source_time(timing, checkpoint.source_time_seconds)
        except ValueError as exc:
            errors.append(f"checkpoint {checkpoint.id} could not map source time: {exc}")
            continue
        checkpoint_observations.append(
            CheckpointObservation(
                checkpoint_id=checkpoint.id,
                role=role,
                source_time_seconds=checkpoint.source_time_seconds,
                expected_audio_seconds=checkpoint.expected_audio_seconds,
                observed_audio_seconds=observed,
            )
        )

    return SharedTimingObservation(
        scenario_id=scenario.scenario_id,
        project_dir=str(project),
        observed_at_utc=datetime.now(timezone.utc).isoformat(),
        build=build,
        project_recording_sha256=project_recording_sha256,
        tempo_map_path=tempo_path_text,
        tempo_map_sha256=tempo_sha256,
        tempo_beat_count=tempo_beat_count,
        roles=role_observations,
        checkpoints=checkpoint_observations,
        collection_errors=errors,
    )


def _status_for_error(error: float, tolerance: float) -> ProductRealityStatus:
    return "PASS" if abs(error) <= tolerance else "FAIL"


def evaluate_shared_timing_observation(
    scenario: PrivateProductRealityScenario,
    observation: SharedTimingObservation,
    *,
    scenario_sha256: str,
) -> PrivateProductRealityEvidence:
    checks: list[ProductRealityCheck] = []

    checks.append(
        ProductRealityCheck(
            code="build_identity",
            status="PASS" if observation.build.commit_sha else "REVIEW_REQUIRED",
            message=(
                f"Exact build commit is {observation.build.commit_sha}."
                if observation.build.commit_sha
                else "Exact build commit is unavailable; deterministic evidence cannot be bound to one build."
            ),
            observed=observation.build.commit_sha or "unknown",
        )
    )

    if observation.tempo_beat_count is None:
        checks.append(
            ProductRealityCheck(
                code="audio_beat_grid",
                status="REVIEW_REQUIRED",
                message="Authoritative audio beat grid could not be read.",
            )
        )
    elif observation.tempo_beat_count < 2:
        checks.append(
            ProductRealityCheck(
                code="audio_beat_grid",
                status="FAIL",
                message="Authoritative audio beat grid has fewer than two beats.",
                observed=observation.tempo_beat_count,
                expected=2,
            )
        )
    else:
        checks.append(
            ProductRealityCheck(
                code="audio_beat_grid",
                status="PASS",
                message=f"Authoritative audio beat grid contains {observation.tempo_beat_count} beats.",
                observed=observation.tempo_beat_count,
            )
        )

    role_by_name = {item.role: item for item in observation.roles}
    first_errors: dict[ArrangementRole, float] = {}
    for role in scenario.roles:
        item = role_by_name.get(role)
        if item is None:
            checks.append(
                ProductRealityCheck(
                    code=f"{role.value}_first_event",
                    status="REVIEW_REQUIRED",
                    message=f"Current reviewed {role.value} arrangement could not be observed.",
                )
            )
            continue
        error = item.first_playable_seconds - scenario.expected.first_playable_seconds
        first_errors[role] = error
        checks.append(
            ProductRealityCheck(
                code=f"{role.value}_first_event",
                status=_status_for_error(error, scenario.expected.first_playable_tolerance_seconds),
                message=(
                    f"{role.value} first playable event is {item.first_playable_seconds:.3f}s "
                    f"(delta {error:+.3f}s)."
                ),
                observed=item.first_playable_seconds,
                expected=scenario.expected.first_playable_seconds,
            )
        )

    if len(role_by_name) == len(scenario.roles):
        first_times = [role_by_name[role].first_playable_seconds for role in scenario.roles]
        spread = max(first_times) - min(first_times)
        checks.append(
            ProductRealityCheck(
                code="arrangement_first_event_spread",
                status=(
                    "PASS"
                    if spread <= scenario.expected.max_arrangement_spread_seconds
                    else "FAIL"
                ),
                message=f"Arrangement first-event spread is {spread:.3f}s.",
                observed=spread,
                expected=scenario.expected.max_arrangement_spread_seconds,
            )
        )

        recording_hashes = {role_by_name[role].recording_sha256 for role in scenario.roles}
        score_hashes = {role_by_name[role].score_sha256 for role in scenario.roles}
        transform_hashes = {role_by_name[role].timing_points_sha256 for role in scenario.roles}
        shared_identity_ok = (
            len(recording_hashes) == 1
            and len(score_hashes) == 1
            and len(transform_hashes) == 1
        )
        checks.append(
            ProductRealityCheck(
                code="shared_timing_transform",
                status="PASS" if shared_identity_ok else "FAIL",
                message=(
                    "All requested arrangements share the same recording, score, and reviewed timing transform."
                    if shared_identity_ok
                    else "Requested arrangements do not share one recording/score/timing authority."
                ),
            )
        )
    else:
        checks.append(
            ProductRealityCheck(
                code="shared_timing_transform",
                status="REVIEW_REQUIRED",
                message="Not every requested arrangement had current reviewed timing evidence.",
            )
        )

    observed_checkpoint_ids = {item.checkpoint_id for item in observation.checkpoints}
    checkpoint_by_id = {item.checkpoint_id: item for item in observation.checkpoints}
    for checkpoint in scenario.checkpoints:
        item = checkpoint_by_id.get(checkpoint.id)
        if item is None:
            checks.append(
                ProductRealityCheck(
                    code=f"checkpoint_{checkpoint.id}",
                    status="REVIEW_REQUIRED",
                    message=f"Checkpoint {checkpoint.id} could not be evaluated.",
                )
            )
            continue
        tolerance = (
            checkpoint.tolerance_seconds
            if checkpoint.tolerance_seconds is not None
            else scenario.expected.max_checkpoint_error_seconds
        )
        error = item.observed_audio_seconds - item.expected_audio_seconds
        checks.append(
            ProductRealityCheck(
                code=f"checkpoint_{checkpoint.id}",
                status=_status_for_error(error, tolerance),
                message=(
                    f"Checkpoint {checkpoint.id} mapped to {item.observed_audio_seconds:.3f}s "
                    f"(delta {error:+.3f}s)."
                ),
                observed=item.observed_audio_seconds,
                expected=item.expected_audio_seconds,
            )
        )

        baseline_error = first_errors.get(item.role)
        if baseline_error is None:
            checks.append(
                ProductRealityCheck(
                    code=f"checkpoint_{checkpoint.id}_drift",
                    status="REVIEW_REQUIRED",
                    message=f"Checkpoint {checkpoint.id} drift cannot be measured without a first-event baseline.",
                )
            )
        else:
            drift = error - baseline_error
            checks.append(
                ProductRealityCheck(
                    code=f"checkpoint_{checkpoint.id}_drift",
                    status=(
                        "PASS"
                        if abs(drift) <= scenario.expected.max_drift_seconds
                        else "FAIL"
                    ),
                    message=(
                        f"Checkpoint {checkpoint.id} changes timing error by {drift:+.3f}s "
                        "relative to the first-event baseline."
                    ),
                    observed=drift,
                    expected=scenario.expected.max_drift_seconds,
                )
            )

    missing_checkpoint_ids = {checkpoint.id for checkpoint in scenario.checkpoints} - observed_checkpoint_ids
    if observation.collection_errors:
        checks.extend(
            ProductRealityCheck(
                code=f"collection_{index + 1}",
                status="REVIEW_REQUIRED",
                message=message,
            )
            for index, message in enumerate(observation.collection_errors)
        )
    if missing_checkpoint_ids and not observation.collection_errors:
        checks.append(
            ProductRealityCheck(
                code="checkpoint_collection",
                status="REVIEW_REQUIRED",
                message="One or more configured checkpoints were not collected.",
            )
        )

    statuses = {check.status for check in checks}
    if "FAIL" in statuses:
        result: ProductRealityStatus = "FAIL"
    elif "REVIEW_REQUIRED" in statuses:
        result = "REVIEW_REQUIRED"
    else:
        result = "PASS"

    return PrivateProductRealityEvidence(
        scenario_id=scenario.scenario_id,
        observed_at_utc=observation.observed_at_utc,
        scenario_sha256=scenario_sha256,
        result=result,
        build=observation.build,
        project_recording_sha256=observation.project_recording_sha256,
        tempo_map_sha256=observation.tempo_map_sha256,
        role_observations=observation.roles,
        checkpoint_observations=observation.checkpoints,
        checks=checks,
        human_only_acceptance=list(scenario.human_only_acceptance),
    )


def _evidence_filename(evidence: PrivateProductRealityEvidence) -> str:
    timestamp = datetime.fromisoformat(evidence.observed_at_utc).astimezone(timezone.utc)
    stamp = timestamp.strftime("%Y%m%dT%H%M%S.%fZ")
    build = evidence.build.commit_sha[:8] if evidence.build.commit_sha else "unknown"
    return f"{stamp}-{build}.json"


def run_private_product_reality(
    scenario_path: Path,
    *,
    results_dir: Path | None = None,
) -> tuple[PrivateProductRealityEvidence, Path]:
    path = scenario_path.expanduser().resolve()
    scenario = load_private_product_reality_scenario(path)
    observation = collect_shared_timing_observation(scenario)
    evidence = evaluate_shared_timing_observation(
        scenario,
        observation,
        scenario_sha256=sha256_file(path),
    )
    root = (
        results_dir.expanduser().resolve()
        if results_dir is not None
        else (path.parent / "results" / scenario.scenario_id).resolve()
    )
    destination = root / _evidence_filename(evidence)
    evidence.write_json(destination)
    return evidence, destination


def format_private_product_reality_report(evidence: PrivateProductRealityEvidence) -> str:
    build = evidence.build.commit_sha or "unknown"
    lines = [
        "PRODUCT REALITY — shared timing",
        f"Build: {build}",
        f"Scenario: {evidence.scenario_id}",
        "",
    ]
    for check in evidence.checks:
        lines.append(f"{check.code:32} {check.status:15} {check.message}")
    lines.extend(["", f"RESULT: {evidence.result}"])
    if evidence.human_only_acceptance:
        lines.append("")
        lines.append("Human-only acceptance debt:")
        lines.extend(f"- {item}" for item in evidence.human_only_acceptance)
    else:
        lines.extend(["", "Human-only acceptance debt: none"])
    return "\n".join(lines)
