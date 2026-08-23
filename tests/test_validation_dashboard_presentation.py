from __future__ import annotations

from rocksmith_cdlc_generator.validation_dashboard import ValidationDashboardRow
from rocksmith_cdlc_generator.validation_dashboard_presentation import (
    present_validation_row,
)


def _row(**updates) -> ValidationDashboardRow:
    data = dict(
        role="bass",
        configured=True,
        state="VALIDATED",
        validation_state="PASS",
        fail_count=0,
        warning_count=0,
        actionable_warning_count=0,
        export_xml_ready=False,
        next_action="Continue.",
    )
    data.update(updates)
    return ValidationDashboardRow(**data)


def test_blocked_row_uses_explicit_fail_semantics() -> None:
    presentation = present_validation_row(
        _row(state="BLOCKED", validation_state="FAIL", fail_count=2)
    )

    assert presentation.status_state == "fail"
    assert presentation.dashboard_text.startswith("✗ FAIL")
    assert presentation.validation_text.startswith("✗ FAIL")
    assert "Blocked" in presentation.dashboard_text


def test_validation_needed_row_never_relies_on_color_alone() -> None:
    presentation = present_validation_row(
        _row(state="VALIDATION_NEEDED", validation_state="NOT_RUN")
    )

    assert presentation.status_state == "review_required"
    assert "REVIEW REQUIRED" in presentation.dashboard_text
    assert "REVIEW REQUIRED" in presentation.validation_text
    assert "Not run" in presentation.validation_text


def test_warning_row_preserves_warning_count_and_xml_state() -> None:
    presentation = present_validation_row(
        _row(validation_state="WARNING", warning_count=3, actionable_warning_count=3, export_xml_ready=False)
    )

    assert presentation.status_state == "warning"
    assert presentation.validation_text.startswith("⚠ WARNING")
    assert "3 actionable warning groups" in presentation.validation_text
    assert "3 underlying warning events" in presentation.validation_text
    assert presentation.xml_text.startswith("ℹ INFO")
    assert "not ready" in presentation.xml_text


def test_warning_row_shows_actionable_count_distinct_from_raw_event_total() -> None:
    """#375: thousands of raw warning events that group down to a handful of root
    causes must show both numbers -- never present the raw total alone, and never
    silently substitute the actionable count for it.
    """
    presentation = present_validation_row(
        _row(
            validation_state="WARNING",
            fail_count=0,
            warning_count=2851,
            actionable_warning_count=3,
            export_xml_ready=False,
        )
    )

    assert presentation.status_state == "warning"
    assert "3 actionable warning groups" in presentation.validation_text
    assert "2851 underlying warning events" in presentation.validation_text


def test_warning_state_remains_warning_when_count_is_zero() -> None:
    presentation = present_validation_row(
        _row(validation_state="WARNING", warning_count=0)
    )

    assert presentation.status_state == "warning"
    assert presentation.dashboard_text.startswith("⚠ WARNING")
    assert presentation.validation_text == "⚠ WARNING — Warning"


def test_xml_ready_row_is_explicitly_pass() -> None:
    presentation = present_validation_row(
        _row(state="XML_READY", export_xml_ready=True)
    )

    assert presentation.status_state == "pass"
    assert presentation.dashboard_text.startswith("✓ PASS")
    assert presentation.xml_text.startswith("✓ PASS")
    assert "XML ready" in presentation.dashboard_text
