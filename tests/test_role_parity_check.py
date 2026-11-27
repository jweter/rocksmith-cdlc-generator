from __future__ import annotations

import math
from typing import Any

import pytest
from pydantic import ValidationError

from rocksmith_cdlc_generator.role_parity_check import check_role_parity


def _role(duration: float = 200.0, events: list[Any] | None = None) -> dict[str, Any]:
    return {"duration_s": duration, "event_times_s": [1.0, 2.0, 3.0] if events is None else events}


def _roles(**overrides: Any) -> dict[str, Any]:
    base = {"Bass": _role(), "Lead": _role(), "Rhythm": _role()}
    base.update(overrides)
    return base


def test_three_matching_roles_have_parity() -> None:
    result = check_role_parity(_roles())

    assert result.status == "PARITY"
    assert result.findings == ()
    assert result.duration_spread_s == 0.0


def test_event_counts_may_differ_between_roles() -> None:
    result = check_role_parity(_roles(Bass=_role(events=[1.0]), Lead=_role(events=[1.0, 2.0, 9.0, 10.0])))

    assert result.status == "PARITY"


def test_a_shortened_role_is_a_duration_mismatch() -> None:
    result = check_role_parity(_roles(Lead=_role(duration=190.0)))

    assert result.status == "MISMATCH"
    assert result.reason == "DURATION_DISAGREES"
    assert [(f.role, f.reason) for f in result.findings] == [("Lead", "DURATION_DISAGREES")]
    assert result.duration_spread_s == pytest.approx(10.0)


def test_spread_equal_to_the_tolerance_is_allowed_and_just_over_is_not() -> None:
    assert check_role_parity(_roles(Lead=_role(duration=200.25)), duration_tolerance_s=0.25).status == "PARITY"
    assert check_role_parity(_roles(Lead=_role(duration=200.5)), duration_tolerance_s=0.25).status == "MISMATCH"


def test_decimal_durations_exactly_one_tolerance_apart_have_parity() -> None:
    # Codex review: 200.05 - 200.0 is 0.05000000000001137 in floating point, which wrongly
    # exceeded the default 0.05 tolerance although the documented boundary is inclusive.
    roles = _roles(Lead=_role(duration=200.05))

    result = check_role_parity(roles)

    assert result.status == "PARITY"
    assert check_role_parity(_roles(Lead=_role(duration=200.1))).status == "MISMATCH"


def test_event_exactly_one_tolerance_past_the_end_is_allowed_for_decimal_durations() -> None:
    assert check_role_parity(_roles(Bass=_role(events=[1.0, 200.05]))).status == "PARITY"
    assert check_role_parity(_roles(Bass=_role(events=[1.0, 200.06]))).status == "MISMATCH"


def test_event_past_the_song_end_is_flagged() -> None:
    result = check_role_parity(_roles(Rhythm=_role(events=[1.0, 250.0])))

    assert result.status == "MISMATCH"
    assert [(f.role, f.reason) for f in result.findings] == [("Rhythm", "EVENT_AFTER_SONG_END")]


def test_event_within_tolerance_of_the_end_is_allowed() -> None:
    assert check_role_parity(_roles(Bass=_role(events=[1.0, 200.04]))).status == "PARITY"


def test_unsorted_events_are_flagged() -> None:
    result = check_role_parity(_roles(Bass=_role(events=[2.0, 1.0, 3.0])))

    assert result.status == "MISMATCH"
    assert [(f.role, f.reason) for f in result.findings] == [("Bass", "EVENTS_NOT_SORTED")]


def test_every_finding_is_listed_not_just_the_first() -> None:
    result = check_role_parity(
        _roles(Bass=_role(events=[3.0, 1.0]), Lead=_role(duration=100.0, events=[1.0, 300.0]))
    )

    reasons = {(f.role, f.reason) for f in result.findings}
    assert reasons == {
        ("Bass", "EVENTS_NOT_SORTED"),
        ("Lead", "EVENT_AFTER_SONG_END"),
        ("Lead", "DURATION_DISAGREES"),
    }


def test_extra_roles_are_ignored_and_required_roles_are_configurable() -> None:
    roles = {"Bass": _role(), "Vocals": _role(duration=1.0)}

    assert check_role_parity(roles, required_roles=["Bass"]).status == "PARITY"


def test_a_missing_required_role_is_invalid_not_parity() -> None:
    roles = {"Bass": _role(), "Lead": _role()}

    result = check_role_parity(roles)

    assert result.status == "INVALID_INPUT"
    assert result.reason == "ROLE_MISSING:Rhythm"


@pytest.mark.parametrize(
    "roles, reason",
    [
        (None, "ROLES_NOT_A_MAPPING"),
        ([], "ROLES_NOT_A_MAPPING"),
        (_roles(Lead="x"), "ROLE_ENTRY_NOT_A_MAPPING:Lead"),
        (_roles(Lead={"event_times_s": [1.0]}), "DURATION_INVALID:Lead"),
        (_roles(Lead=_role(duration=0.0)), "DURATION_INVALID:Lead"),
        (_roles(Lead=_role(duration=-5.0)), "DURATION_INVALID:Lead"),
        (_roles(Lead=_role(duration=math.nan)), "DURATION_INVALID:Lead"),
        (_roles(Lead={"duration_s": True, "event_times_s": [1.0]}), "DURATION_INVALID:Lead"),
        (_roles(Lead={"duration_s": 200.0}), "EVENTS_NOT_A_SEQUENCE:Lead"),
        (_roles(Lead={"duration_s": 200.0, "event_times_s": "1,2"}), "EVENTS_NOT_A_SEQUENCE:Lead"),
        (_roles(Lead=_role(events=[])), "NO_EVENTS:Lead"),
        (_roles(Lead=_role(events=[1.0, math.nan])), "EVENT_TIME_INVALID:Lead"),
        (_roles(Lead=_role(events=[1.0, -0.5])), "EVENT_TIME_INVALID:Lead"),
        (_roles(Lead=_role(events=[1.0, "2"])), "EVENT_TIME_INVALID:Lead"),
        (_roles(Lead=_role(events=[True])), "EVENT_TIME_INVALID:Lead"),
    ],
)
def test_invalid_roles_are_reported_never_parity(roles: object, reason: str) -> None:
    result = check_role_parity(roles)

    assert result.status == "INVALID_INPUT"
    assert result.reason == reason
    assert result.findings == ()


@pytest.mark.parametrize(
    "required, tolerance, reason",
    [
        ("Bass", 0.05, "REQUIRED_ROLES_INVALID"),
        ([], 0.05, "REQUIRED_ROLES_INVALID"),
        (["Bass", "Bass"], 0.05, "REQUIRED_ROLES_INVALID"),
        (["Bass", 3], 0.05, "REQUIRED_ROLES_INVALID"),
        (["Bass"], -1.0, "DURATION_TOLERANCE_INVALID"),
        (["Bass"], math.nan, "DURATION_TOLERANCE_INVALID"),
        (["Bass"], True, "DURATION_TOLERANCE_INVALID"),
    ],
)
def test_invalid_configuration_is_reported(required: object, tolerance: object, reason: str) -> None:
    result = check_role_parity(_roles(), required, tolerance)

    assert result.status == "INVALID_INPUT"
    assert result.reason == reason


def test_results_are_frozen() -> None:
    result = check_role_parity(_roles())
    with pytest.raises(ValidationError):
        result.status = "MISMATCH"  # type: ignore[misc]
