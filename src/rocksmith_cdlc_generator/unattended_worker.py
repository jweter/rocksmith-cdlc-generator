from __future__ import annotations

import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .build_identity import current_build_identity
from .models import ProjectManifest
from .private_product_reality import (
    PrivateProductRealityEvidence,
    PrivateProductRealityScenario,
    load_private_product_reality_scenario,
    run_private_product_reality,
)
from .shared_timeline import load_current_shared_timeline
from .source_timing_qualification import SourceTimingQualification, qualify_project_score_timing

WorkerStatus = Literal["PASS", "FAIL", "REVIEW_REQUIRED", "IDLE", "BUSY"]


class OllamaDiagnosisSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    enabled: bool = True
    base_url: str = "http://127.0.0.1:11434"
    model: str = "gemma3:4b"
    timeout_seconds: float = Field(default=90.0, gt=0.0, le=600.0)


class UnattendedWorkerConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    scenario_roots: list[Path] = Field(default_factory=list)
    results_dir: Path | None = None
    state_dir: Path | None = None
    include_recent_projects: bool = True
    ollama: OllamaDiagnosisSettings = Field(default_factory=OllamaDiagnosisSettings)


class LocalDiagnosis(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    category: Literal[
        "timing_phase",
        "timing_drift",
        "stale_authority",
        "missing_evidence",
        "build_environment",
        "unknown",
    ]
    summary: str = Field(min_length=1, max_length=600)
    likely_root_cause: str = Field(min_length=1, max_length=1200)
    next_automated_action: str = Field(min_length=1, max_length=1200)
    human_required: bool = False
    human_reason: str | None = Field(default=None, max_length=600)
    confidence: float = Field(ge=0.0, le=1.0)


class WorkerScenarioResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    scenario_id: str
    status: Literal["PASS", "FAIL", "REVIEW_REQUIRED"]
    evidence_path: str
    checks: list[dict]


class RecentProjectHealth(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_name: str
    recording_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["PASS", "FAIL", "REVIEW_REQUIRED"]
    qualification_status: Literal["pass", "review_required", "insufficient_evidence"]
    best_shift_seconds: float
    first_projected_note_seconds: float | None = None
    first_audio_note_seconds: float | None = None
    reason: str


class UnattendedWorkerReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    started_at_utc: str
    completed_at_utc: str
    hostname: str
    build_version: str
    build_commit_sha: str | None = None
    status: WorkerStatus
    scenario_results: list[WorkerScenarioResult] = Field(default_factory=list)
    recent_project_health: list[RecentProjectHealth] = Field(default_factory=list)
    diagnosis: LocalDiagnosis | None = None
    diagnosis_error: str | None = None
    notes: list[str] = Field(default_factory=list)

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path


class WorkerRunResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    report: UnattendedWorkerReport
    report_path: Path


def _local_appdata_root() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base).expanduser().resolve() / "RocksmithCDLCGenerator"
    return (Path.home() / ".rocksmith-cdlc-generator" / "RocksmithCDLCGenerator").resolve()


def default_worker_state_dir() -> Path:
    return _local_appdata_root() / "unattended-worker"


def default_worker_config_path() -> Path:
    return default_worker_state_dir() / "worker.json"


def _default_scenario_roots(repo_root: Path | None) -> list[Path]:
    roots = [default_worker_state_dir() / "scenarios"]
    if repo_root is not None:
        roots.extend(
            [
                repo_root / "private" / "product-reality-scenarios",
                repo_root / "private" / "product-reality-inbox",
            ]
        )
    return roots


def load_worker_config(path: Path | None = None, *, repo_root: Path | None = None) -> UnattendedWorkerConfig:
    config_path = (path or default_worker_config_path()).expanduser().resolve()
    if config_path.is_file():
        config = UnattendedWorkerConfig.model_validate_json(config_path.read_text(encoding="utf-8"))
    else:
        config = UnattendedWorkerConfig()

    roots = list(config.scenario_roots) or _default_scenario_roots(repo_root)
    normalized_roots = [root.expanduser().resolve() for root in roots]
    state = (config.state_dir or default_worker_state_dir()).expanduser().resolve()
    results = (config.results_dir or (state / "results")).expanduser().resolve()
    return config.model_copy(
        update={
            "scenario_roots": normalized_roots,
            "state_dir": state,
            "results_dir": results,
        }
    )


def discover_private_scenarios(config: UnattendedWorkerConfig) -> list[Path]:
    found: dict[str, Path] = {}
    for root in config.scenario_roots:
        if not root.is_dir():
            continue
        for candidate in sorted(root.rglob("*.json")):
            try:
                scenario = load_private_product_reality_scenario(candidate)
            except (OSError, ValueError, ValidationError):
                continue
            found.setdefault(scenario.scenario_id, candidate.resolve())
    return [found[key] for key in sorted(found)]


def _recent_projects_settings_path() -> Path:
    return _local_appdata_root() / "desktop.json"


def recent_project_paths() -> list[Path]:
    try:
        payload = json.loads(_recent_projects_settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []
    raw = payload.get("recent_projects", []) if isinstance(payload, dict) else []
    projects: list[Path] = []
    for value in raw[:10]:
        if not isinstance(value, str):
            continue
        candidate = Path(value).expanduser().resolve()
        if candidate.is_dir():
            projects.append(candidate)
    return projects


def _qualification_health(project: Path) -> RecentProjectHealth | None:
    """Run independent timing qualification on a recent project when applicable.

    This deliberately uses the existing audio-vs-symbolic multi-event qualification
    rather than asking an LLM to judge timing. Projects without a current shared timing
    authority are simply not applicable to this health lane.
    """

    try:
        manifest = ProjectManifest.load(project)
        timeline = load_current_shared_timeline(project)
    except (OSError, ValueError):
        return None

    try:
        qualification = qualify_project_score_timing(project, timeline)
    except (OSError, ValueError):
        return None

    if qualification.status == "pass":
        status: Literal["PASS", "FAIL", "REVIEW_REQUIRED"] = "PASS"
    elif qualification.status == "review_required":
        status = "FAIL"
    else:
        status = "REVIEW_REQUIRED"

    return RecentProjectHealth(
        project_name=manifest.project_name,
        recording_sha256=manifest.source_sha256,
        status=status,
        qualification_status=qualification.status,
        best_shift_seconds=qualification.best_shift_seconds,
        first_projected_note_seconds=qualification.first_projected_note_seconds,
        first_audio_note_seconds=qualification.first_audio_note_seconds,
        reason=qualification.reason,
    )


def collect_recent_project_health() -> list[RecentProjectHealth]:
    results: list[RecentProjectHealth] = []
    seen: set[Path] = set()
    for project in recent_project_paths():
        if project in seen:
            continue
        seen.add(project)
        health = _qualification_health(project)
        if health is not None:
            results.append(health)
    return results


def _ollama_chat_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Ollama base URL must use http or https")
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Unattended diagnosis is local-only; refusing a non-loopback Ollama host")
    return base_url.rstrip("/") + "/api/chat"


def _post_json(url: str, payload: dict, timeout_seconds: float) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Local Ollama HTTP {exc.code}: {detail[:300]}") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Local Ollama diagnosis unavailable: {exc}") from exc


def _diagnosis_payload(
    *,
    scenario_results: list[WorkerScenarioResult],
    recent_health: list[RecentProjectHealth],
) -> dict:
    """Return derived evidence only; no private paths, media, or source bytes."""

    return {
        "scenario_results": [
            {
                "scenario_id": item.scenario_id,
                "status": item.status,
                "checks": item.checks,
            }
            for item in scenario_results
            if item.status != "PASS"
        ],
        "recent_project_health": [
            {
                "project_name": item.project_name,
                "status": item.status,
                "qualification_status": item.qualification_status,
                "best_shift_seconds": item.best_shift_seconds,
                "first_projected_note_seconds": item.first_projected_note_seconds,
                "first_audio_note_seconds": item.first_audio_note_seconds,
                "reason": item.reason,
            }
            for item in recent_health
            if item.status != "PASS"
        ],
    }


def diagnose_with_local_ollama(
    settings: OllamaDiagnosisSettings,
    *,
    scenario_results: list[WorkerScenarioResult],
    recent_health: list[RecentProjectHealth],
) -> LocalDiagnosis:
    evidence = _diagnosis_payload(
        scenario_results=scenario_results,
        recent_health=recent_health,
    )
    prompt = (
        "You are the local diagnostic analyst for a Rocksmith CDLC generator. "
        "The JSON below contains derived machine measurements only. Do not invent facts. "
        "Classify the most likely defect class, summarize the evidence, state a cautious likely root cause, "
        "and propose the next AUTOMATED engineering/test action. Set human_required=true only when the evidence "
        "really requires subjective musical/gameplay judgment or a new human decision; routine reruns, timestamp "
        "inspection, log reading, code debugging, and deterministic testing are not human tasks.\n\n"
        + json.dumps(evidence, sort_keys=True)
    )
    body = _post_json(
        _ollama_chat_url(settings.base_url),
        {
            "model": settings.model,
            "messages": [{"role": "user", "content": prompt}],
            "format": LocalDiagnosis.model_json_schema(),
            "stream": False,
            "options": {"temperature": 0},
        },
        settings.timeout_seconds,
    )
    try:
        content = body["message"]["content"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError("Local Ollama response did not contain message.content") from exc
    if not isinstance(content, str):
        raise RuntimeError("Local Ollama response message.content was not text")
    try:
        return LocalDiagnosis.model_validate_json(content)
    except ValidationError as exc:
        raise RuntimeError(f"Local Ollama diagnosis failed schema validation: {exc}") from exc


def _aggregate_status(
    scenarios: list[WorkerScenarioResult],
    health: list[RecentProjectHealth],
) -> WorkerStatus:
    statuses = [item.status for item in scenarios] + [item.status for item in health]
    if not statuses:
        return "IDLE"
    if "FAIL" in statuses:
        return "FAIL"
    if "REVIEW_REQUIRED" in statuses:
        return "REVIEW_REQUIRED"
    return "PASS"


def _lock_path(state_dir: Path) -> Path:
    return state_dir / "worker.lock"


def _acquire_lock(state_dir: Path) -> int | None:
    state_dir.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(_lock_path(state_dir), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return None
    os.write(fd, str(os.getpid()).encode("ascii"))
    return fd


def _release_lock(state_dir: Path, fd: int) -> None:
    try:
        os.close(fd)
    finally:
        _lock_path(state_dir).unlink(missing_ok=True)


def _busy_result(state_dir: Path) -> WorkerRunResult:
    now = datetime.now(timezone.utc).isoformat()
    identity = current_build_identity()
    report = UnattendedWorkerReport(
        started_at_utc=now,
        completed_at_utc=now,
        hostname=socket.gethostname(),
        build_version=identity.version,
        build_commit_sha=identity.commit_sha,
        status="BUSY",
        notes=["Another unattended worker instance already holds the local worker lock."],
    )
    path = state_dir / "latest.json"
    report.write_json(path)
    return WorkerRunResult(report=report, report_path=path)


def run_unattended_worker(
    *,
    config_path: Path | None = None,
    repo_root: Path | None = None,
) -> WorkerRunResult:
    started = datetime.now(timezone.utc)
    config = load_worker_config(config_path, repo_root=repo_root)
    assert config.state_dir is not None
    assert config.results_dir is not None
    state_dir = config.state_dir
    lock_fd = _acquire_lock(state_dir)
    if lock_fd is None:
        return _busy_result(state_dir)

    try:
        scenario_results: list[WorkerScenarioResult] = []
        for scenario_path in discover_private_scenarios(config):
            try:
                scenario = load_private_product_reality_scenario(scenario_path)
                evidence, destination = run_private_product_reality(
                    scenario_path,
                    results_dir=config.results_dir / "scenarios" / scenario.scenario_id,
                )
                scenario_results.append(
                    WorkerScenarioResult(
                        scenario_id=scenario.scenario_id,
                        status=evidence.result,
                        evidence_path=str(destination),
                        checks=[check.model_dump(mode="json") for check in evidence.checks],
                    )
                )
            except (OSError, ValueError, ValidationError) as exc:
                scenario_results.append(
                    WorkerScenarioResult(
                        scenario_id=scenario_path.stem,
                        status="REVIEW_REQUIRED",
                        evidence_path="",
                        checks=[
                            {
                                "code": "worker_scenario_error",
                                "status": "REVIEW_REQUIRED",
                                "message": f"Scenario could not run: {type(exc).__name__}: {exc}",
                            }
                        ],
                    )
                )

        health = collect_recent_project_health() if config.include_recent_projects else []
        status = _aggregate_status(scenario_results, health)
        diagnosis: LocalDiagnosis | None = None
        diagnosis_error: str | None = None
        if config.ollama.enabled and status in {"FAIL", "REVIEW_REQUIRED"}:
            try:
                diagnosis = diagnose_with_local_ollama(
                    config.ollama,
                    scenario_results=scenario_results,
                    recent_health=health,
                )
            except (OSError, RuntimeError, ValueError) as exc:
                diagnosis_error = f"{type(exc).__name__}: {exc}"

        identity = current_build_identity()
        completed = datetime.now(timezone.utc)
        notes: list[str] = []
        if status == "IDLE":
            notes.append(
                "No configured private Product Reality scenarios or applicable recent shared-timing projects were found."
            )
        if diagnosis is not None and not diagnosis.human_required:
            notes.append("Local diagnosis found no reason to involve the user; continue with automated engineering.")

        report = UnattendedWorkerReport(
            started_at_utc=started.isoformat(),
            completed_at_utc=completed.isoformat(),
            hostname=socket.gethostname(),
            build_version=identity.version,
            build_commit_sha=identity.commit_sha,
            status=status,
            scenario_results=scenario_results,
            recent_project_health=health,
            diagnosis=diagnosis,
            diagnosis_error=diagnosis_error,
            notes=notes,
        )
        history = state_dir / "history"
        history.mkdir(parents=True, exist_ok=True)
        stamp = completed.strftime("%Y%m%dT%H%M%S.%fZ")
        history_path = history / f"{stamp}.json"
        report.write_json(history_path)
        latest_path = state_dir / "latest.json"
        report.write_json(latest_path)
        return WorkerRunResult(report=report, report_path=latest_path)
    finally:
        _release_lock(state_dir, lock_fd)


def format_worker_report(report: UnattendedWorkerReport) -> str:
    lines = [
        "ROCKSMITH UNATTENDED LOCAL WORKER",
        f"Build: {report.build_commit_sha or report.build_version}",
        f"Result: {report.status}",
        "",
    ]
    if report.scenario_results:
        lines.append("Private scenarios:")
        lines.extend(f"- {item.scenario_id}: {item.status}" for item in report.scenario_results)
    if report.recent_project_health:
        lines.append("Recent-project timing health:")
        lines.extend(
            f"- {item.project_name}: {item.status} (best residual shift {item.best_shift_seconds:+.3f}s)"
            for item in report.recent_project_health
        )
    if report.diagnosis is not None:
        lines.extend(
            [
                "",
                f"Ollama diagnosis: {report.diagnosis.category} ({report.diagnosis.confidence:.0%})",
                report.diagnosis.summary,
                f"Likely root cause: {report.diagnosis.likely_root_cause}",
                f"Next automated action: {report.diagnosis.next_automated_action}",
                f"Human required: {'yes' if report.diagnosis.human_required else 'no'}",
            ]
        )
        if report.diagnosis.human_reason:
            lines.append(f"Human reason: {report.diagnosis.human_reason}")
    elif report.diagnosis_error:
        lines.extend(["", f"Ollama diagnosis unavailable: {report.diagnosis_error}"])
    if report.notes:
        lines.extend(["", *report.notes])
    return "\n".join(lines)
