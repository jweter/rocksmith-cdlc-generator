"""Intent-engineering and deterministic close-gate primitives.

This module adapts the most portable LifeOS ideas to the Rocksmith CDLC
pipeline without introducing a dependency on LifeOS itself.  A pipeline task
states what must become true, deterministic probes report evidence, and a
close gate decides whether the task is actually complete.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ProbeStatus(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    NOT_RUN = "not_run"


class IdealStateCriterion(BaseModel):
    """One falsifiable claim that defines part of a task's ideal state."""

    id: str = Field(min_length=1)
    claim: str = Field(min_length=1)
    probe: str = Field(min_length=1)
    required: bool = True
    rationale: str | None = None


class TaskIntent(BaseModel):
    """Task-scoped intent contract.

    The contract deliberately describes WHAT must be true, not a prescribed
    chain-of-thought or rigid implementation recipe.
    """

    schema_version: int = Field(default=1, ge=1)
    task_id: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    current_state: dict[str, Any] = Field(default_factory=dict)
    ideal_state: str = Field(min_length=1)
    constraints: dict[str, Any] = Field(default_factory=dict)
    criteria: list[IdealStateCriterion] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_criterion_ids(self) -> "TaskIntent":
        ids = [criterion.id for criterion in self.criteria]
        if len(ids) != len(set(ids)):
            raise ValueError("criterion ids must be unique")
        return self


class ProbeResult(BaseModel):
    """Evidence-bearing result produced by a deterministic verification probe."""

    criterion_id: str = Field(min_length=1)
    status: ProbeStatus
    summary: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)
    metrics: dict[str, float | int | str | bool | None] = Field(default_factory=dict)


class VerificationReport(BaseModel):
    """Close-gate decision for a TaskIntent."""

    task_id: str
    close_allowed: bool
    results: list[ProbeResult]
    missing_criteria: list[str] = Field(default_factory=list)
    failed_required_criteria: list[str] = Field(default_factory=list)
    warned_criteria: list[str] = Field(default_factory=list)


def verify_intent(intent: TaskIntent, results: list[ProbeResult]) -> VerificationReport:
    """Evaluate an intent using explicit probe results.

    Rules:
    * every criterion must have exactly one probe result;
    * any required FAIL or NOT_RUN blocks close;
    * missing required criteria block close;
    * WARNING is surfaced but does not block close by itself;
    * optional failures remain visible but do not block close.

    Unknown criterion IDs are rejected so stale or misrouted probe output
    cannot accidentally satisfy the wrong task.
    """

    criteria_by_id = {criterion.id: criterion for criterion in intent.criteria}
    result_by_id: dict[str, ProbeResult] = {}

    for result in results:
        if result.criterion_id not in criteria_by_id:
            raise ValueError(f"unknown criterion id: {result.criterion_id}")
        if result.criterion_id in result_by_id:
            raise ValueError(f"duplicate result for criterion: {result.criterion_id}")
        result_by_id[result.criterion_id] = result

    missing = [criterion.id for criterion in intent.criteria if criterion.id not in result_by_id]
    failed_required: list[str] = []
    warned: list[str] = []

    for criterion in intent.criteria:
        result = result_by_id.get(criterion.id)
        if result is None:
            if criterion.required:
                failed_required.append(criterion.id)
            continue
        if result.status is ProbeStatus.WARNING:
            warned.append(criterion.id)
        if criterion.required and result.status in {ProbeStatus.FAIL, ProbeStatus.NOT_RUN}:
            failed_required.append(criterion.id)

    return VerificationReport(
        task_id=intent.task_id,
        close_allowed=not failed_required,
        results=results,
        missing_criteria=missing,
        failed_required_criteria=failed_required,
        warned_criteria=warned,
    )
