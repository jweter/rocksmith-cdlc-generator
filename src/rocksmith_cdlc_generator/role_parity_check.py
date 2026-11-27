"""Check that every packaged arrangement role agrees on song length (#796 slice 44).

Bass, Lead and Rhythm arrangements of one song must describe the same recording. If one
role is cut short or padded, switching roles in the game moves the player against the audio.
This pure check compares each role's reported song duration and validates that its events
are finite, sorted and inside that duration. It never reads or changes a package.

``roles`` maps a role name to ``{"duration_s": float, "event_times_s": [float, ...]}``. Every
name in ``required_roles`` (default Bass, Lead, Rhythm) must be present and each must have at
least one event. Durations must agree within ``duration_tolerance_s`` (default 0.05; a spread
exactly equal to the tolerance is allowed). Invalid input returns ``INVALID_INPUT`` with a named
reason; structurally valid input that disagrees returns ``MISMATCH`` with every finding listed.
It never raises and never reports ``PARITY`` for input it could not validate.
"""
from __future__ import annotations

import itertools
import math
from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict

DEFAULT_REQUIRED_ROLES = ("Bass", "Lead", "Rhythm")
DEFAULT_DURATION_TOLERANCE_S = 0.05
# Decimal seconds are not exactly representable (200.05 - 200.0 is 0.05000000000001137), so the
# inclusive tolerance boundary is compared with a tiny slack, far below any audible timing.
_BOUNDARY_SLACK_S = 1e-9

ParityStatus = Literal["PARITY", "MISMATCH", "INVALID_INPUT"]


class RoleFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: str
    reason: str


class RoleParityResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: ParityStatus
    reason: str = ""
    duration_spread_s: float | None = None
    findings: tuple[RoleFinding, ...] = ()


def _is_number(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
    )


def _invalid(reason: str) -> RoleParityResult:
    return RoleParityResult(status="INVALID_INPUT", reason=reason)


def check_role_parity(
    roles: object,
    required_roles: object = DEFAULT_REQUIRED_ROLES,
    duration_tolerance_s: object = DEFAULT_DURATION_TOLERANCE_S,
) -> RoleParityResult:
    """Compare per-role duration and validate each role's event times."""
    if not isinstance(roles, Mapping):
        return _invalid("ROLES_NOT_A_MAPPING")
    if (
        isinstance(required_roles, (str, bytes))
        or not isinstance(required_roles, Sequence)
        or not required_roles
        or not all(isinstance(r, str) and r for r in required_roles)
        or len(set(required_roles)) != len(required_roles)
    ):
        return _invalid("REQUIRED_ROLES_INVALID")
    if not _is_number(duration_tolerance_s) or float(duration_tolerance_s) < 0:  # type: ignore[arg-type]
        return _invalid("DURATION_TOLERANCE_INVALID")
    tolerance = float(duration_tolerance_s)  # type: ignore[arg-type]

    durations: dict[str, float] = {}
    events: dict[str, list[float]] = {}
    for name in required_roles:
        if name not in roles:
            return _invalid(f"ROLE_MISSING:{name}")
        entry = roles[name]
        if not isinstance(entry, Mapping):
            return _invalid(f"ROLE_ENTRY_NOT_A_MAPPING:{name}")
        duration = entry.get("duration_s")
        if not _is_number(duration) or float(duration) <= 0:  # type: ignore[arg-type]
            return _invalid(f"DURATION_INVALID:{name}")
        raw_events = entry.get("event_times_s")
        if isinstance(raw_events, (str, bytes)) or not isinstance(raw_events, Sequence):
            return _invalid(f"EVENTS_NOT_A_SEQUENCE:{name}")
        if not raw_events:
            return _invalid(f"NO_EVENTS:{name}")
        if not all(_is_number(t) and float(t) >= 0 for t in raw_events):  # type: ignore[arg-type]
            return _invalid(f"EVENT_TIME_INVALID:{name}")
        durations[name] = float(duration)  # type: ignore[arg-type]
        events[name] = [float(t) for t in raw_events]  # type: ignore[arg-type]

    findings: list[RoleFinding] = []
    for name in required_roles:
        times = events[name]
        if any(b < a for a, b in itertools.pairwise(times)):
            findings.append(RoleFinding(role=name, reason="EVENTS_NOT_SORTED"))
        # the latest event, wherever it sits in the list (an unsorted role can hide it mid-list)
        if max(times) > durations[name] + tolerance + _BOUNDARY_SLACK_S:
            findings.append(RoleFinding(role=name, reason="EVENT_AFTER_SONG_END"))

    spread = max(durations.values()) - min(durations.values())
    if spread > tolerance + _BOUNDARY_SLACK_S:
        shortest = min(required_roles, key=lambda r: durations[r])
        findings.append(RoleFinding(role=shortest, reason="DURATION_DISAGREES"))

    return RoleParityResult(
        status="MISMATCH" if findings else "PARITY",
        reason=findings[0].reason if findings else "",
        duration_spread_s=spread,
        findings=tuple(findings),
    )
