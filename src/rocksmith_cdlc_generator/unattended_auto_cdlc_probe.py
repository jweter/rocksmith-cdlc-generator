"""Opt-in, read-only auto-cdlc environment evidence for the idle Windows worker.

This lane never executes models, installs dependencies, changes the game or
promotes song Product Reality results. Only allow-listed, path-free status is
copied into the worker's local report. Model readiness is NOT musical truth.
"""
from __future__ import annotations

from math import isfinite
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .auto_cdlc_readiness import inspect_upstream_readiness

_ALLOWED_BLOCKERS = frozenset({
    "PHYSICAL_RAM_AT_LEAST_7_GIB",
    "RUN_VOLUME_FREE_DISK_AT_LEAST_8_GIB",
    "SYNTHETIC_FIXTURE_VERIFIED",
    "UPSTREAM_REVIEWED_CHECKOUT",
    "BASS_ONNX_MODEL_CACHED",
    "BEAT_THIS_CHECKPOINT_PINNED",
    "PYTHON_313_PACKAGE_SET",
})


class AutoCdlcWorkerSettings(BaseModel):
    """Explicit local paths; disabled until configured. No implicit library scan."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = False
    fixture_dir: Path | None = None
    upstream_checkout: Path | None = None
    python_313_exe: Path | None = None
    run_parent: Path | None = None
    wwise_console: Path | None = None


class AutoCdlcWorkerSnapshot(BaseModel):
    """Strictly sanitized monitoring evidence; never an accuracy or gameplay PASS."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["READY_TO_ATTEMPT_SYNTHETIC", "BLOCKED", "UNAVAILABLE"]
    blocked_codes: list[str] = Field(default_factory=list)
    installed_package_count: int | None = Field(default=None, ge=0)
    missing_package_count: int | None = Field(default=None, ge=0)
    available_ram_gib: float | None = Field(default=None, ge=0)
    available_disk_gib: float | None = Field(default=None, ge=0)
    wwise_console_located: bool = False
    error_code: str | None = None
    real_model_transcription_proven: Literal[False] = False
    wwise_packaging_proven: Literal[False] = False
    rocksmith_gameplay_proven: Literal[False] = False


def _metric(checks: list[dict], code: str, key: str) -> float | None:
    candidate = next((c for c in checks if c.get("code") == code), None)
    if not isinstance(candidate, dict):
        return None
    detail = candidate.get("detail")
    value = detail.get(key) if isinstance(detail, dict) else None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    num = float(value)
    return round(num, 3) if isfinite(num) and 0 <= num <= 1024 else None


def _summarize(report: dict) -> AutoCdlcWorkerSnapshot:
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        raise ValueError("Unexpected auto-cdlc doctor report schema")
    blocked = report.get("synthetic_blocker_codes")
    ready = report.get("synthetic_transcription_ready")
    checks = report.get("checks")
    if (
        not isinstance(blocked, list)
        or not all(isinstance(x, str) and x in _ALLOWED_BLOCKERS for x in blocked)
        or not isinstance(ready, bool)
        or not isinstance(checks, list)
        or ready != (not blocked)
    ):
        raise ValueError("Untrusted auto-cdlc doctor status")

    codes_seen = [c.get("code") for c in checks if isinstance(c, dict)]
    if len(codes_seen) != len(set(codes_seen)) or not _ALLOWED_BLOCKERS.issubset(set(codes_seen)):
        raise ValueError("Incomplete/duplicated doctor checks")
    failures = {
        check.get("code") for check in checks
        if isinstance(check, dict)
        and check.get("code") in _ALLOWED_BLOCKERS
        and check.get("passed") is False
    }
    if failures != set(blocked):
        raise ValueError("Doctor check results disagree with blocker codes")
    packages = next(c for c in checks if c["code"] == "PYTHON_313_PACKAGE_SET")
    details = packages.get("detail")
    installed_count = details.get("installed_count") if isinstance(details, dict) else None
    required_count = details.get("required_count") if isinstance(details, dict) else None
    if isinstance(installed_count, bool) or not isinstance(installed_count, int) or installed_count < 0:
        installed_count = None
    if isinstance(required_count, bool) or not isinstance(required_count, int) or required_count < 0:
        required_count = None
    missing_count = (
        required_count - installed_count
        if required_count is not None and installed_count is not None
        and installed_count <= required_count
        else None
    )

    return AutoCdlcWorkerSnapshot(
        status="READY_TO_ATTEMPT_SYNTHETIC" if ready else "BLOCKED",
        blocked_codes=sorted(set(blocked)),
        installed_package_count=installed_count,
        missing_package_count=missing_count,
        available_ram_gib=_metric(checks, "PHYSICAL_RAM_AT_LEAST_7_GIB", "available_gib"),
        available_disk_gib=_metric(checks, "RUN_VOLUME_FREE_DISK_AT_LEAST_8_GIB", "available_gib"),
        wwise_console_located=report.get("wwise_console_located") is True,
    )


def collect_auto_cdlc_worker_probe(
    settings: AutoCdlcWorkerSettings,
) -> AutoCdlcWorkerSnapshot | None:
    """Collect a monitoring-only report. Never turn exceptions into READY."""

    if not settings.enabled:
        return None
    try:
        doctor = inspect_upstream_readiness(
            fixture_dir=settings.fixture_dir,
            upstream_checkout=settings.upstream_checkout,
            python_313_exe=settings.python_313_exe,
            run_parent=settings.run_parent,
            wwise_console=settings.wwise_console,
        )
        return _summarize(doctor)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        # Do not persist error messages: exceptions may include private paths
        # and arbitrary subprocess output.
        return AutoCdlcWorkerSnapshot(
            status="UNAVAILABLE",
            blocked_codes=[],
            error_code=type(exc).__name__,
        )
