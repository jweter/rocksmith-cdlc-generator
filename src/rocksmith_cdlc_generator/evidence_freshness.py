"""Invalidate verification evidence when the code, model or audio changed (#796 slice 60).

A test report only proves anything about the exact inputs it ran against. This module
binds a report to ``(code_revision, model_id, audio_sha256)`` and says, in a fixed order
and with named reasons, why a recorded binding no longer matches the current one. A
missing or blank binding is never fresh: absence of proof cannot be treated as freshness.
``model_id`` and ``audio_sha256`` may legitimately be ``None`` on *both* sides (a run
with no model or audio) and then compare equal; ``None`` on only one side is a change.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class EvidenceBinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    code_revision: str
    model_id: str | None = None
    audio_sha256: str | None = None


def _valid(binding: object) -> bool:
    if not isinstance(binding, EvidenceBinding):
        return False
    if not isinstance(binding.code_revision, str) or not binding.code_revision.strip():
        return False
    if binding.model_id is not None and not binding.model_id.strip():
        return False
    return binding.audio_sha256 is None or bool(_SHA256.fullmatch(binding.audio_sha256))


def stale_reasons(recorded: object, current: object) -> tuple[str, ...]:
    """Named reasons the recorded evidence is stale; an empty tuple means fresh."""

    if not _valid(recorded) or not _valid(current):
        return ("BINDING_MISSING",)
    assert isinstance(recorded, EvidenceBinding) and isinstance(current, EvidenceBinding)
    reasons: list[str] = []
    if recorded.code_revision != current.code_revision:
        reasons.append("CODE_REVISION_CHANGED")
    if recorded.model_id != current.model_id:
        reasons.append("MODEL_CHANGED")
    if recorded.audio_sha256 != current.audio_sha256:
        reasons.append("AUDIO_CHANGED")
    return tuple(reasons)


def is_fresh(recorded: object, current: object) -> bool:
    """True only when the recorded binding is valid and identical to the current one."""

    return not stale_reasons(recorded, current)
