from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .beats import read_tempo_map
from .build_identity import current_build_identity
from .build_staging import PsarcRegistrationVerification, verify_psarc_registration
from .hashing import sha256_file
from .models import ProjectManifest
from .private_library_corpus import corpus_evidence_summary
from .product_reality_official_tab import (
    OfficialTabProductRealityEvidence,
    collect_official_tab_registration_evidence,
)
from .product_reality_printed_score import (
    PrintedScoreProductRealityEvidence,
    collect_printed_score_recognition_evidence,
)
from .reviewed_arrangement_timing import reviewed_arrangement_timing
from .reviewed_export_events import reviewed_export_arrangement
from .reviewed_timing_transform import map_reviewed_source_time
from .score_measure_recognition import PRIVATE_RECOGNITION_RELATIVE_PATH
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
    corpus_inventory_path: Path | None = None
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
    commit_sha: str | None = Field(default=None, pattern=r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
    built_at_utc: str | None = None
    packaged: bool

    @field_validator("commit_sha")
    @classmethod
    def commit_sha_is_exact(cls, value: str | None) -> str | None:
        if value is not None and (
            len(value) not in {40, 64} or any(ch not in "0123456789abcdef" for ch in value)
        ):
            raise ValueError("commit_sha must be a full 40- or 64-character lowercase Git object ID")
        return value


class CorpusEvidenceObservation(BaseModel):
    """Repository-safe aggregate evidence derived from a private local corpus inventory."""

    model_config = ConfigDict(frozen=True)

    corpus_evidence_schema_version: Literal[1] = 1
    item_count: int = Field(ge=0)
    total_bytes: int = Field(ge=0)
    trust_tier_counts: dict[str, int]
    corpus_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def trust_tiers_are_aggregate_only(self) -> "CorpusEvidenceObservation":
        if set(self.trust_tier_counts) != {"A", "B", "C"}:
            raise ValueError("corpus trust_tier_counts must contain exactly A, B, and C")
        if any(isinstance(value, bool) or value < 0 for value in self.trust_tier_counts.values()):
            raise ValueError("corpus trust tier counts must be non-negative integers")
        if sum(self.trust_tier_counts.values()) != self.item_count:
            raise ValueError("corpus trust tier counts must sum to item_count")
        return self


class RoleTimingObservation(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: ArrangementRole
    source_track_index: int = Field(ge=0)
    first_source_seconds: float = Field(ge=0.0)
    first_playable_seconds: float = Field(ge=0.0)
    note_count: int = Field(ge=1)
    recording_sha256: str
    score_sha256: str
    source_output_sha256: str
    timing_points_sha256: str


class CheckpointObservation(BaseModel):
    model_config = ConfigDict(frozen=True)

    checkpoint_id: str
    role: ArrangementRole
    source_time_seconds: float
    expected_audio_seconds: float
    observed_audio_seconds: float


class SharedTimingObservation(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    scenario_id: str
    project_dir: str
    observed_at_utc: str
    build: BuildObservation
    project_recording_sha256: str | None = None
    tempo_map_path: str | None = None
    tempo_map_sha256: str | None = None
    tempo_beat_count: int | None = None
    roles: list[RoleTimingObservation] = Field(default_factory=list)
    checkpoints: list[CheckpointObservation] = Field(default_factory=list)
    psarc_registration: PsarcRegistrationVerification | None = None
    official_tab_registration: OfficialTabProductRealityEvidence | None = None
    printed_score_recognition: PrintedScoreProductRealityEvidence | None = None
    corpus_evidence: CorpusEvidenceObservation | None = None
    collection_errors: list[str] = Field(default_factory=list)


class ProductRealityCheck(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    status: ProductRealityStatus
    message: str
    measured: float | str | None = None
    expected: float | str | None = None
    tolerance: float | None = None


class PrivateProductRealityEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    runner_version: str = "private-product-reality-v1"
    scenario_id: str
    scenario_type: Literal["shared_timing"] = "shared_timing"
    observed_at_utc: str
    scenario_sha256: str
    result: ProductRealityStatus
    build: BuildObservation
    checks: list[ProductRealityCheck]
    psarc_registration: PsarcRegistrationVerification | None = None
    official_tab_registration: OfficialTabProductRealityEvidence | None = None
    printed_score_recognition: PrintedScoreProductRealityEvidence | None = None
    corpus_evidence: CorpusEvidenceObservation | None = None
    human_only_acceptance: list[str] = Field(default_factory=list)
    collection_errors: list[str] = Field(default_factory=list)

    def write_json(self, path: Path) -> Path:
        destination = path.expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf-8") as handle:
            handle.write(self.model_dump_json(indent=2))
            handle.write("\n")
        return destination


def collect_shared_timing_observation(scenario: PrivateProductRealityScenario) -> SharedTimingObservation:
    project = scenario.project_dir.expanduser().resolve()
    manifest = ProjectManifest.load(project / "project.json")
    build_identity = current_build_identity()
    errors: list[str] = []
    roles: list[RoleTimingObservation] = []
    checkpoints: list[CheckpointObservation] = []

    tempo_path = authoritative_tempo_map_path(project)
    tempo_hash: str | None = None
    tempo_count: int | None = None
    if tempo_path.exists():
        try:
            tempo_hash = sha256_file(tempo_path)
            tempo_count = len(read_tempo_map(tempo_path))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"tempo authority is unreadable: {type(exc).__name__}: {exc}")
    else:
        errors.append("authoritative tempo map is missing")

    for role in scenario.roles:
        try:
            arrangement = reviewed_export_arrangement(project, role)
            timing = reviewed_arrangement_timing(project, role)
            if not arrangement.notes:
                raise ValueError("reviewed arrangement has no playable notes")
            first_note = arrangement.notes[0]
            roles.append(
                RoleTimingObservation(
                    role=role,
                    source_track_index=arrangement.source_track_index,
                    first_source_seconds=first_note.source_start_seconds,
                    first_playable_seconds=first_note.start_seconds,
                    note_count=len(arrangement.notes),
                    recording_sha256=arrangement.recording_sha256,
                    score_sha256=arrangement.score_sha256,
                    source_output_sha256=arrangement.source_output_sha256,
                    timing_points_sha256=timing.timing_points_sha256,
                )
            )
        except (FileNotFoundError, OSError, ValueError, ValidationError) as exc:
            errors.append(f"{role.value} reviewed timing authority is unavailable or stale: {type(exc).__name__}: {exc}")

    role_map = {role.role: role for role in roles}
    for checkpoint in scenario.checkpoints:
        role = checkpoint.role or scenario.roles[0]
        if role not in role_map:
            errors.append(f"checkpoint {checkpoint.id!r} cannot be evaluated because {role.value} authority is unavailable")
            continue
        try:
            timing = reviewed_arrangement_timing(project, role)
            checkpoints.append(
                CheckpointObservation(
                    checkpoint_id=checkpoint.id,
                    role=role,
                    source_time_seconds=checkpoint.source_time_seconds,
                    expected_audio_seconds=checkpoint.expected_audio_seconds,
                    observed_audio_seconds=map_reviewed_source_time(timing, checkpoint.source_time_seconds),
                )
            )
        except (FileNotFoundError, OSError, ValueError, ValidationError) as exc:
            errors.append(f"checkpoint {checkpoint.id!r} authority is unavailable or stale: {type(exc).__name__}: {exc}")

    psarc_registration: PsarcRegistrationVerification | None = None
    try:
        psarc_registration = verify_psarc_registration(project)
    except FileNotFoundError:
        pass
    except (OSError, ValueError, ValidationError, json.JSONDecodeError) as exc:
        errors.append(f"PSARC registration receipt is unreadable or invalid: {type(exc).__name__}: {exc}")

    official_tab_registration: OfficialTabProductRealityEvidence | None = None
    try:
        official_tab_registration = collect_official_tab_registration_evidence(project)
    except FileNotFoundError:
        pass
    except (OSError, ValueError, ValidationError, json.JSONDecodeError) as exc:
        errors.append(f"Official TAB registration evidence is unreadable or invalid: {type(exc).__name__}: {exc}")

    printed_score_recognition: PrintedScoreProductRealityEvidence | None = None
    recognition_root = project / PRIVATE_RECOGNITION_RELATIVE_PATH
    if recognition_root.exists():
        try:
            printed_score_recognition = collect_printed_score_recognition_evidence(project)
        except (OSError, ValueError, ValidationError, json.JSONDecodeError) as exc:
            errors.append(f"printed-score recognition evidence is unreadable or invalid: {type(exc).__name__}: {exc}")

    corpus_evidence: CorpusEvidenceObservation | None = None
    if scenario.corpus_inventory_path is not None:
        try:
            summary = corpus_evidence_summary(scenario.corpus_inventory_path)
            corpus_evidence = CorpusEvidenceObservation(
                item_count=summary.item_count,
                total_bytes=summary.total_bytes,
                trust_tier_counts=summary.trust_tier_counts,
                corpus_sha256=summary.corpus_sha256,
            )
        except (FileNotFoundError, OSError, ValueError, ValidationError, json.JSONDecodeError) as exc:
            errors.append(f"private corpus evidence is unavailable or invalid: {type(exc).__name__}: {exc}")

    return SharedTimingObservation(
        scenario_id=scenario.scenario_id,
        project_dir=str(project),
        observed_at_utc=datetime.now(timezone.utc).isoformat(),
        build=BuildObservation(
            version=build_identity.version,
            commit_sha=build_identity.commit_sha,
            built_at_utc=build_identity.built_at_utc,
            packaged=build_identity.packaged,
        ),
        project_recording_sha256=manifest.recording_sha256,
        tempo_map_path=str(tempo_path) if tempo_path.exists() else None,
        tempo_map_sha256=tempo_hash,
        tempo_beat_count=tempo_count,
        roles=roles,
        checkpoints=checkpoints,
        psarc_registration=psarc_registration,
        official_tab_registration=official_tab_registration,
        printed_score_recognition=printed_score_recognition,
        corpus_evidence=corpus_evidence,
        collection_errors=errors,
    )


def evaluate_shared_timing_observation(
    scenario: PrivateProductRealityScenario,
    observation: SharedTimingObservation,
    *,
    scenario_sha256: str,
) -> PrivateProductRealityEvidence:
    checks: list[ProductRealityCheck] = []

    if observation.tempo_beat_count is None or observation.tempo_beat_count < 2:
        checks.append(
            ProductRealityCheck(
                code="tempo_authority",
                status="REVIEW_REQUIRED",
                message="Authoritative tempo map is unavailable or invalid.",
            )
        )
    else:
        checks.append(
            ProductRealityCheck(
                code="tempo_authority",
                status="PASS",
                message="Authoritative tempo map is present.",
                measured=str(observation.tempo_beat_count),
            )
        )

    if observation.build.commit_sha is None:
        checks.append(
            ProductRealityCheck(
                code="build_identity",
                status="REVIEW_REQUIRED",
                message="Running build is not bound to an exact commit SHA.",
            )
        )
    else:
        checks.append(
            ProductRealityCheck(
                code="build_identity",
                status="PASS",
                message="Running build is bound to an exact commit SHA.",
                measured=observation.build.commit_sha,
            )
        )

    observed_roles = {role.role: role for role in observation.roles}
    for role in scenario.roles:
        role_observation = observed_roles.get(role)
        if role_observation is None:
            checks.append(
                ProductRealityCheck(
                    code=f"{role.value}_first_event",
                    status="REVIEW_REQUIRED",
                    message=f"{role.value.title()} reviewed timing authority is unavailable.",
                )
            )
            continue
        error = role_observation.first_playable_seconds - scenario.expected.first_playable_seconds
        checks.append(
            ProductRealityCheck(
                code=f"{role.value}_first_event",
                status="PASS" if abs(error) <= scenario.expected.first_playable_tolerance_seconds else "FAIL",
                message=f"{role.value.title()} first playable event compared with private expected recording entrance.",
                measured=role_observation.first_playable_seconds,
                expected=scenario.expected.first_playable_seconds,
                tolerance=scenario.expected.first_playable_tolerance_seconds,
            )
        )

    if len(observation.roles) >= 2:
        spread = max(role.first_playable_seconds for role in observation.roles) - min(
            role.first_playable_seconds for role in observation.roles
        )
        checks.append(
            ProductRealityCheck(
                code="arrangement_first_event_spread",
                status="PASS" if spread <= scenario.expected.max_arrangement_spread_seconds else "FAIL",
                message="Requested arrangements compared for shared first-event timing.",
                measured=spread,
                expected=0.0,
                tolerance=scenario.expected.max_arrangement_spread_seconds,
            )
        )

    if len(observation.roles) == len(scenario.roles) and observation.roles:
        shared_recording = {role.recording_sha256 for role in observation.roles}
        shared_score = {role.score_sha256 for role in observation.roles}
        shared_transform = {role.timing_points_sha256 for role in observation.roles}
        if len(shared_recording) != 1 or len(shared_score) != 1 or len(shared_transform) != 1:
            checks.append(
                ProductRealityCheck(
                    code="shared_timing_transform",
                    status="FAIL",
                    message="Requested arrangements do not share one recording/score/reviewed timing transform.",
                )
            )
        else:
            checks.append(
                ProductRealityCheck(
                    code="shared_timing_transform",
                    status="PASS",
                    message="Requested arrangements share recording, score, and reviewed timing transform authority.",
                )
            )
    else:
        checks.append(
            ProductRealityCheck(
                code="shared_timing_transform",
                status="REVIEW_REQUIRED",
                message="Not all requested arrangements have current reviewed timing authority.",
            )
        )

    first_error_by_role: dict[ArrangementRole, float] = {}
    for role, role_observation in observed_roles.items():
        first_error_by_role[role] = role_observation.first_playable_seconds - scenario.expected.first_playable_seconds

    checkpoint_by_id = {checkpoint.checkpoint_id: checkpoint for checkpoint in observation.checkpoints}
    for expected_checkpoint in scenario.checkpoints:
        observed_checkpoint = checkpoint_by_id.get(expected_checkpoint.id)
        if observed_checkpoint is None:
            checks.append(
                ProductRealityCheck(
                    code=f"checkpoint_{expected_checkpoint.id}",
                    status="REVIEW_REQUIRED",
                    message="Configured later timing checkpoint could not be evaluated.",
                )
            )
            continue
        tolerance = expected_checkpoint.tolerance_seconds or scenario.expected.max_checkpoint_error_seconds
        checkpoint_error = observed_checkpoint.observed_audio_seconds - expected_checkpoint.expected_audio_seconds
        status: ProductRealityStatus = "PASS" if abs(checkpoint_error) <= tolerance else "FAIL"
        role = observed_checkpoint.role
        first_error = first_error_by_role.get(role)
        if first_error is not None and abs(checkpoint_error - first_error) > scenario.expected.max_drift_seconds:
            status = "FAIL"
        checks.append(
            ProductRealityCheck(
                code=f"checkpoint_{expected_checkpoint.id}",
                status=status,
                message="Later source-time checkpoint compared with expected recording time and first-event error.",
                measured=observed_checkpoint.observed_audio_seconds,
                expected=expected_checkpoint.expected_audio_seconds,
                tolerance=tolerance,
            )
        )

    if observation.psarc_registration is not None:
        if observation.psarc_registration.status == "PASS":
            checks.append(
                ProductRealityCheck(
                    code="psarc_registration",
                    status="PASS",
                    message="Registered PSARC staging inputs still match the receipt.",
                )
            )
        else:
            drift_codes = ", ".join(item.code for item in observation.psarc_registration.drift)
            checks.append(
                ProductRealityCheck(
                    code="psarc_registration",
                    status="FAIL",
                    message=f"Registered PSARC staging inputs drifted: {drift_codes or 'unknown drift'}.",
                )
            )

    if observation.official_tab_registration is not None:
        official_tab = observation.official_tab_registration
        if official_tab.status == "PASS":
            checks.append(
                ProductRealityCheck(
                    code="official_tab_registration",
                    status="PASS",
                    message="Official TAB registration remains bound to the current project evidence.",
                )
            )
        elif official_tab.status == "FAIL":
            checks.append(
                ProductRealityCheck(
                    code="official_tab_registration",
                    status="FAIL",
                    message="Official TAB registration deterministically drifted from the current project evidence.",
                )
            )
        else:
            checks.append(
                ProductRealityCheck(
                    code="official_tab_registration",
                    status="REVIEW_REQUIRED",
                    message="Official TAB registration evidence requires review.",
                )
            )

    if observation.printed_score_recognition is not None:
        printed_score = observation.printed_score_recognition
        if printed_score.status == "PASS":
            checks.append(
                ProductRealityCheck(
                    code="printed_score_recognition",
                    status="PASS",
                    message="Printed-score recognition candidates have complete human review records.",
                )
            )
        elif printed_score.status == "FAIL":
            checks.append(
                ProductRealityCheck(
                    code="printed_score_recognition",
                    status="FAIL",
                    message="Printed-score recognition evidence contains a deterministic failure.",
                )
            )
        else:
            checks.append(
                ProductRealityCheck(
                    code="printed_score_recognition",
                    status="REVIEW_REQUIRED",
                    message="Printed-score recognition evidence requires review.",
                )
            )

    if observation.corpus_evidence is not None:
        checks.append(
            ProductRealityCheck(
                code="private_corpus_evidence",
                status="PASS",
                message="Configured private library corpus evidence is bound as repository-safe aggregates.",
                measured=str(observation.corpus_evidence.item_count),
            )
        )

    if observation.collection_errors:
        checks.append(
            ProductRealityCheck(
                code="collection_completeness",
                status="REVIEW_REQUIRED",
                message="One or more required authorities could not be collected.",
                measured=str(len(observation.collection_errors)),
            )
        )

    result: ProductRealityStatus = "PASS"
    if any(check.status == "FAIL" for check in checks):
        result = "FAIL"
    elif any(check.status == "REVIEW_REQUIRED" for check in checks):
        result = "REVIEW_REQUIRED"

    return PrivateProductRealityEvidence(
        scenario_id=scenario.scenario_id,
        observed_at_utc=observation.observed_at_utc,
        scenario_sha256=scenario_sha256,
        result=result,
        build=observation.build,
        checks=checks,
        psarc_registration=observation.psarc_registration,
        official_tab_registration=observation.official_tab_registration,
        printed_score_recognition=observation.printed_score_recognition,
        corpus_evidence=observation.corpus_evidence,
        human_only_acceptance=scenario.human_only_acceptance,
        collection_errors=observation.collection_errors,
    )


def load_private_product_reality_scenario(path: Path) -> PrivateProductRealityScenario:
    source = path.expanduser().resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    scenario = PrivateProductRealityScenario.model_validate(payload)
    project_dir = scenario.project_dir
    if not project_dir.is_absolute():
        project_dir = source.parent / project_dir
    corpus_inventory_path = scenario.corpus_inventory_path
    if corpus_inventory_path is not None and not corpus_inventory_path.is_absolute():
        corpus_inventory_path = source.parent / corpus_inventory_path
    return scenario.model_copy(
        update={
            "project_dir": project_dir.resolve(),
            "corpus_inventory_path": corpus_inventory_path.resolve() if corpus_inventory_path is not None else None,
        }
    )


def run_private_product_reality(
    scenario_path: Path,
    *,
    output_root: Path | None = None,
) -> tuple[PrivateProductRealityEvidence, Path]:
    source = scenario_path.expanduser().resolve()
    scenario = load_private_product_reality_scenario(source)
    observation = collect_shared_timing_observation(scenario)
    evidence = evaluate_shared_timing_observation(scenario, observation, scenario_sha256=sha256_file(source))

    root = output_root or (source.parent / "evidence")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    destination = root / scenario.scenario_id / f"{timestamp}.json"
    evidence.write_json(destination)
    return evidence, destination
