import pytest
from pydantic import ValidationError

from rocksmith_cdlc_generator.intent import (
    IdealStateCriterion,
    ProbeResult,
    ProbeStatus,
    TaskIntent,
    verify_intent,
)


def make_intent() -> TaskIntent:
    return TaskIntent(
        task_id="bass-export-001",
        task_type="arrangement_export",
        current_state={"arrangement": "Bass", "validated": False},
        ideal_state="A reviewable, schema-valid Bass arrangement is safe to export.",
        constraints={"live_install_write": False},
        criteria=[
            IdealStateCriterion(
                id="ISC-01",
                claim="All mapped notes are within the configured Bass range.",
                probe="validate_instrument_range",
            ),
            IdealStateCriterion(
                id="ISC-02",
                claim="No unresolved physical positions remain.",
                probe="count_unresolved_positions == 0",
            ),
            IdealStateCriterion(
                id="ISC-03",
                claim="Low-confidence techniques are surfaced for human review.",
                probe="review_queue_written",
                required=False,
            ),
        ],
    )


def test_required_passes_allow_close_with_optional_warning() -> None:
    report = verify_intent(
        make_intent(),
        [
            ProbeResult(criterion_id="ISC-01", status=ProbeStatus.PASS, summary="range valid"),
            ProbeResult(criterion_id="ISC-02", status=ProbeStatus.PASS, summary="0 unresolved"),
            ProbeResult(criterion_id="ISC-03", status=ProbeStatus.WARNING, summary="3 review items"),
        ],
    )

    assert report.close_allowed is True
    assert report.failed_required_criteria == []
    assert report.warned_criteria == ["ISC-03"]


def test_required_failure_blocks_close() -> None:
    report = verify_intent(
        make_intent(),
        [
            ProbeResult(criterion_id="ISC-01", status=ProbeStatus.PASS, summary="range valid"),
            ProbeResult(criterion_id="ISC-02", status=ProbeStatus.FAIL, summary="2 unresolved positions"),
        ],
    )

    assert report.close_allowed is False
    assert report.failed_required_criteria == ["ISC-02"]
    assert report.missing_criteria == ["ISC-03"]


def test_missing_required_probe_blocks_close() -> None:
    report = verify_intent(
        make_intent(),
        [ProbeResult(criterion_id="ISC-01", status=ProbeStatus.PASS, summary="range valid")],
    )

    assert report.close_allowed is False
    assert report.failed_required_criteria == ["ISC-02"]
    assert report.missing_criteria == ["ISC-02", "ISC-03"]


def test_unknown_or_duplicate_probe_results_are_rejected() -> None:
    intent = make_intent()

    with pytest.raises(ValueError, match="unknown criterion id"):
        verify_intent(
            intent,
            [ProbeResult(criterion_id="ISC-99", status=ProbeStatus.PASS, summary="wrong task")],
        )

    duplicate = ProbeResult(criterion_id="ISC-01", status=ProbeStatus.PASS, summary="ok")
    with pytest.raises(ValueError, match="duplicate result"):
        verify_intent(intent, [duplicate, duplicate])


def test_duplicate_criterion_ids_are_invalid() -> None:
    with pytest.raises(ValidationError):
        TaskIntent(
            task_id="duplicate",
            task_type="test",
            ideal_state="valid",
            criteria=[
                IdealStateCriterion(id="ISC-01", claim="a", probe="a"),
                IdealStateCriterion(id="ISC-01", claim="b", probe="b"),
            ],
        )
