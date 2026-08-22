from __future__ import annotations

from rocksmith_cdlc_generator.review_queue_row_presentation import (
    present_review_queue_row_severity,
)


def test_fail_maps_to_fail_status_with_symbol_and_label() -> None:
    presentation = present_review_queue_row_severity("FAIL")

    assert presentation.status_state == "fail"
    assert presentation.severity_text == "✗ FAIL"


def test_warning_maps_to_warning_status_with_symbol_and_label() -> None:
    presentation = present_review_queue_row_severity("WARNING")

    assert presentation.status_state == "warning"
    assert presentation.severity_text == "⚠ WARNING"


def test_info_maps_to_info_status_with_symbol_and_label() -> None:
    presentation = present_review_queue_row_severity("INFO")

    assert presentation.status_state == "info"
    assert presentation.severity_text == "ℹ INFO"


def test_unrecognized_severity_falls_back_to_info_instead_of_raising() -> None:
    """Defensive only: WorkspaceReviewItem.severity is a Literal, so normal callers
    can never reach this path, but the presentation layer must not crash a real
    Review Queue tab render if that contract is ever loosened.
    """

    presentation = present_review_queue_row_severity("SOMETHING_NEW")

    assert presentation.status_state == "info"
    assert presentation.severity_text == "ℹ INFO"


def test_severity_text_never_conveys_state_by_color_alone() -> None:
    """Every status text must pair a distinct symbol with readable label text so
    the state is legible even in a context that renders no color at all.
    """

    texts = {
        present_review_queue_row_severity(severity).severity_text
        for severity in ("FAIL", "WARNING", "INFO")
    }
    assert len(texts) == 3
    for text in texts:
        symbol, label = text.split(" ", 1)
        assert symbol
        assert label
