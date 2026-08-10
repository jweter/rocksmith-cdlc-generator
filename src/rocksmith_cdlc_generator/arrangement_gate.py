from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from .guitar_validation import validate_guitar_project
from .models import ProjectManifest
from .packaging_gate import PackagingBlockedError
from .validation import validate_project

ArrangementRole = Literal["bass", "lead", "rhythm"]


class ArrangementGateResult(BaseModel):
    arrangement: ArrangementRole
    status: str
    warning_count: int
    fail_count: int


class ConfiguredArrangementGate(BaseModel):
    arrangements: list[ArrangementGateResult]

    @property
    def status(self) -> str:
        if any(item.status == "FAIL" for item in self.arrangements):
            return "FAIL"
        if any(item.status == "WARNING" for item in self.arrangements):
            return "WARNING"
        return "PASS"


def configured_arrangement_roles(project_dir: Path) -> list[ArrangementRole]:
    manifest = ProjectManifest.load(project_dir.resolve())
    roles: list[ArrangementRole] = []
    for raw in manifest.arrangement_instruments:
        role = raw.lower().strip()
        if role not in {"bass", "lead", "rhythm"}:
            raise ValueError(f"Unsupported configured arrangement: {raw}")
        if role not in roles:
            roles.append(role)  # type: ignore[arg-type]
    if not roles:
        raise ValueError("Project has no configured playable arrangements")
    return roles


def validate_configured_arrangements(project_dir: Path) -> ConfiguredArrangementGate:
    project_dir = project_dir.resolve()
    results: list[ArrangementGateResult] = []
    for role in configured_arrangement_roles(project_dir):
        if role == "bass":
            report = validate_project(project_dir)
        else:
            report = validate_guitar_project(project_dir, arrangement=role)
        results.append(
            ArrangementGateResult(
                arrangement=role,
                status=report.status,
                warning_count=report.warning_count,
                fail_count=report.fail_count,
            )
        )
    return ConfiguredArrangementGate(arrangements=results)


def require_configured_arrangements_ready(project_dir: Path) -> ConfiguredArrangementGate:
    gate = validate_configured_arrangements(project_dir)
    failed = [item.arrangement for item in gate.arrangements if item.status == "FAIL"]
    if failed:
        joined = ", ".join(failed)
        raise PackagingBlockedError(
            f"Configured arrangement validation is FAIL for: {joined}. "
            "Run `cdlc validate PROJECT --instrument ROLE` for each failing arrangement and resolve hard failures first."
        )
    return gate
