from __future__ import annotations

from collections import Counter
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Callable

from .unattended_worker import UnattendedWorkerReport

_REPOSITORY = "jweter/rocksmith-cdlc-generator"
_ISSUE_NUMBER = 612
_STATE_FILE = "github-publication.json"


def _qualification_reason_code(reason: str) -> str:
    """Reduce private qualification text to a stable repository-safe reason code."""

    normalized = reason.casefold()
    if "no audio-derived bass transcription" in normalized:
        return "missing_audio_bass_transcription"
    if "fewer than" in normalized and "event" in normalized:
        return "insufficient_strong_events"
    if "insufficient" in normalized and "event" in normalized:
        return "insufficient_strong_events"
    return "other_insufficient_evidence"


def _public_payload(report: UnattendedWorkerReport) -> dict[str, object]:
    scenario_counts = {status: 0 for status in ("PASS", "FAIL", "REVIEW_REQUIRED")}
    health_counts = {status: 0 for status in ("PASS", "FAIL", "REVIEW_REQUIRED")}
    for item in report.scenario_results:
        scenario_counts[item.status] += 1
    for item in report.recent_project_health:
        health_counts[item.status] += 1

    residuals = [abs(item.best_shift_seconds) for item in report.recent_project_health]
    max_abs_residual = max(residuals) if residuals else None
    human_required = report.diagnosis.human_required if report.diagnosis is not None else None
    qualification_reasons = Counter(
        _qualification_reason_code(item.reason)
        for item in report.recent_project_health
        if item.status == "REVIEW_REQUIRED"
    )
    threshold_diagnostics = Counter()
    for item in report.recent_project_health:
        if (
            item.status != "REVIEW_REQUIRED"
            or _qualification_reason_code(item.reason) != "insufficient_strong_events"
        ):
            continue
        diagnostic_counts = {
            "symbolic_below_minimum": item.compared_symbolic_notes,
            "strong_audio_below_minimum": item.usable_audio_notes,
            "total_audio_below_minimum": item.total_audio_notes,
            "confidence_below_minimum": item.confidence_qualified_audio_notes,
            "timing_below_minimum": item.timing_qualified_audio_notes,
            "pitch_below_minimum": item.pitch_qualified_audio_notes,
        }
        for code, count in diagnostic_counts.items():
            if count is not None and count < 4:
                threshold_diagnostics[code] += 1

    return {
        "build": report.build_commit_sha or report.build_version,
        "status": report.status,
        "completed_at_utc": report.completed_at_utc,
        "scenario_counts": scenario_counts,
        "recent_project_health_counts": health_counts,
        "recent_project_review_reason_counts": dict(sorted(qualification_reasons.items())),
        "recent_project_threshold_diagnostic_counts": dict(sorted(threshold_diagnostics.items())),
        "max_abs_residual_shift_seconds": max_abs_residual,
        "diagnosis_human_required": human_required,
    }


def _body(payload: dict[str, object]) -> str:
    scenarios = payload["scenario_counts"]
    health = payload["recent_project_health_counts"]
    reasons = payload["recent_project_review_reason_counts"]
    threshold_diagnostics = payload["recent_project_threshold_diagnostic_counts"]
    assert isinstance(scenarios, dict)
    assert isinstance(health, dict)
    assert isinstance(reasons, dict)
    assert isinstance(threshold_diagnostics, dict)
    residual = payload["max_abs_residual_shift_seconds"]
    residual_text = "n/a" if residual is None else f"{float(residual):.3f}s"
    human = payload["diagnosis_human_required"]
    human_text = "not assessed" if human is None else "yes" if human else "no"
    reason_text = "none"
    if reasons:
        reason_text = " · ".join(f"{key} {value}" for key, value in sorted(reasons.items()))
    threshold_text = "none"
    if threshold_diagnostics:
        threshold_text = ", ".join(
            f"{key} {value}" for key, value in sorted(threshold_diagnostics.items())
        )
    return "\n".join(
        [
            "## Unattended private Product Reality — sanitized status",
            "",
            f"- **Build:** `{payload['build']}`",
            f"- **Result:** **{payload['status']}**",
            f"- **Completed:** {payload['completed_at_utc']}",
            (
                "- **Configured scenarios:** "
                f"PASS {scenarios['PASS']} · FAIL {scenarios['FAIL']} · "
                f"REVIEW_REQUIRED {scenarios['REVIEW_REQUIRED']}"
            ),
            (
                "- **Recent-project timing health:** "
                f"PASS {health['PASS']} · FAIL {health['FAIL']} · "
                f"REVIEW_REQUIRED {health['REVIEW_REQUIRED']}"
            ),
            f"- **Timing qualification review reasons:** {reason_text}",
            f"- **Strong-event threshold diagnostics:** {threshold_text}",
            f"- **Maximum absolute residual timing shift observed:** {residual_text}",
            f"- **Local diagnosis says human judgment required:** {human_text}",
            "",
            "This publication contains only aggregate derived measurements and allow-listed reason codes. "
            "Private song titles, paths, scenario identifiers, source hashes, media, score/tab content, and "
            "local logs remain on the Windows machine. This status cannot override deterministic PASS/FAIL "
            "authority and does not claim actual Rocksmith gameplay/tone acceptance.",
        ]
    )


def publish_sanitized_status(
    report: UnattendedWorkerReport,
    state_dir: Path,
    *,
    os_name: str | None = None,
    which: Callable[[str], str | None] = shutil.which,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str:
    """Best-effort sanitized GitHub publication for the private Windows worker.

    Publication is deliberately non-authoritative: inability to publish must never alter
    deterministic Product Reality truth. The local dedupe key suppresses repeated comments
    for an unchanged build/result/aggregate measurement state.
    """

    current_os = os.name if os_name is None else os_name
    if current_os != "nt":
        return "LOCAL_ONLY_NON_WINDOWS"

    state_dir.mkdir(parents=True, exist_ok=True)
    payload = _public_payload(report)
    key = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    state_path = state_dir / _STATE_FILE
    try:
        prior = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        prior = {}
    if isinstance(prior, dict) and prior.get("publication_key") == key:
        return "UNCHANGED"

    gh = which("gh.exe") or which("gh")
    if gh is None:
        _write_state(state_path, "LOCAL_ONLY", key, "GitHub CLI is unavailable")
        return "LOCAL_ONLY"

    try:
        auth = runner(
            [gh, "auth", "status"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        _write_state(state_path, "LOCAL_ONLY", key, "GitHub CLI auth check failed")
        return "LOCAL_ONLY"
    if auth.returncode != 0:
        _write_state(state_path, "LOCAL_ONLY", key, "GitHub CLI is not authenticated")
        return "LOCAL_ONLY"

    try:
        posted = runner(
            [
                gh,
                "issue",
                "comment",
                str(_ISSUE_NUMBER),
                "--repo",
                _REPOSITORY,
                "--body",
                _body(payload),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        _write_state(state_path, "LOCAL_ONLY", key, "GitHub issue publication failed")
        return "LOCAL_ONLY"
    if posted.returncode != 0:
        _write_state(state_path, "LOCAL_ONLY", key, "GitHub issue publication was rejected")
        return "LOCAL_ONLY"

    _write_state(state_path, "PUBLISHED", key, "Sanitized status posted to issue #612")
    return "PUBLISHED"


def _write_state(path: Path, status: str, key: str, detail: str) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": status,
                "detail": detail,
                "publication_key": key,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
