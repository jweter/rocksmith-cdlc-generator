from __future__ import annotations

from pydantic import BaseModel, Field


class LiveAuditionBackendEvidence(BaseModel):
    """Evidence required before an audio backend can power production live audition."""

    backend_name: str = Field(min_length=1)
    functional_full_duplex_proven: bool = False
    low_latency_proven: bool = False
    vendor_state_preserved: bool = False
    reconnect_recovery_proven: bool = False
    requires_state_change_opt_in: bool = False
    notes: list[str] = Field(default_factory=list)


class LiveAuditionBackendDecision(BaseModel):
    backend_name: str
    production_eligible: bool
    blockers: list[str] = Field(default_factory=list)


def assess_live_audition_backend(
    evidence: LiveAuditionBackendEvidence,
) -> LiveAuditionBackendDecision:
    """Fail closed until every production live-audition safety property is proven."""

    blockers: list[str] = []
    if not evidence.functional_full_duplex_proven:
        blockers.append("functional full-duplex instrument I/O has not been proven")
    if not evidence.low_latency_proven:
        blockers.append("the configured low-latency target has not been proven")
    if not evidence.vendor_state_preserved:
        blockers.append("opening the backend is not proven to preserve vendor driver state")
    if not evidence.reconnect_recovery_proven:
        blockers.append("device disconnect/reconnect recovery has not been proven")
    if evidence.requires_state_change_opt_in:
        blockers.append("the backend requires explicit opt-in to a potentially state-changing operation")

    return LiveAuditionBackendDecision(
        backend_name=evidence.backend_name,
        production_eligible=not blockers,
        blockers=blockers,
    )
