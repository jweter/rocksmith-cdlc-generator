from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError

from .guitar_validation import validate_guitar_project
from .models import ProjectManifest
from .packaging_gate import PackagingBlockedError
from .score_mapping_review import load_score_for_mapping_review
from .score_source import ArrangementRole as ScoreArrangementRole
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


def _human_confirmed_roles(project_dir: Path) -> list[ArrangementRole]:
    try:
        score = load_score_for_mapping_review(project_dir)
    except (OSError, ValueError, ValidationError, FileNotFoundError):
        return []
    confirmed: list[ArrangementRole] = []
    for role in (ScoreArrangementRole.bass, ScoreArrangementRole.lead, ScoreArrangementRole.rhythm):
        mapping = score.mapping_for(role)
        if mapping is not None and mapping.human_confirmed:
            confirmed.append(role.value)  # type: ignore[arg-type]
    return confirmed


def configured_arrangement_roles(project_dir: Path) -> list[ArrangementRole]:
    project_dir = project_dir.resolve()
    manifest = ProjectManifest.load(project_dir)
    roles: list[ArrangementRole] = []
    for raw in manifest.arrangement_instruments:
        role = raw.lower().strip()
        if role not in {"bass", "lead", "rhythm"}:
            raise ValueError(f"Unsupported configured arrangement: {raw}")
        if role not in roles:
            roles.append(role)  # type: ignore[arg-type]
    # manifest.arrangement_instruments is fixed at project creation (the shipped desktop
    # shell always declares all three, but `cdlc new --instrument bass` -- the documented
    # CLI/"deterministic engine" path -- can create a project with only Bass declared).
    # A role becomes real project work the moment its score mapping is human-confirmed
    # (score_mapping_review.confirm_score_mapping has no arrangement_instruments check,
    # and multi_arrangement_plan._confirmed_guitar_roles builds real Lead/Rhythm workflow
    # steps, exports, and validation reports from that same confirmation alone). Without
    # this, a human-confirmed-but-undeclared role's Rocksmith XML was silently excluded
    # from require_configured_arrangements_ready's pre-package validation gate and from
    # prepare_dlcbuilder_project's build loop, so a FAIL/broken Lead or Rhythm arrangement
    # could not block packaging and a PASSing one could not be included in the shipped
    # DLC -- the same #304/#193 "two independent sources of truth for which arrangements
    # are in this project" pattern already fixed for the Song Workspace dashboard's
    # `configured` flag (see docs/product-reality/issue-304-undeclared-confirmed-role-not-configured.md).
    for role in _human_confirmed_roles(project_dir):
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
