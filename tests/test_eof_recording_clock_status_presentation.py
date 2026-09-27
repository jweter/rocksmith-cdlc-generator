from __future__ import annotations

from rocksmith_cdlc_generator.eof_recording_clock_status_presentation import (
    present_eof_recording_clock_status,
)


def test_matched_comparison_is_pass() -> None:
    presentation = present_eof_recording_clock_status(
        matched=True, detail="Lead · aligned"
    )

    assert presentation.status_state == "pass"
    assert "PASS" in presentation.text


def test_mismatched_comparison_requires_review() -> None:
    presentation = present_eof_recording_clock_status(
        matched=False, detail="Lead · drifted"
    )

    assert presentation.status_state == "review_required"
    assert "REVIEW REQUIRED" in presentation.text


def test_detail_text_is_preserved_verbatim() -> None:
    """Only the leading symbol/label/color changes -- existing detail is not lost."""

    detail = (
        "EOF recording-clock: Lead · aligned · first playable delta +0.012s · "
        "median |error| 0.004s · max |error| 0.019s · 42 observation(s). "
        "Advisory only; EOF evidence never changes chart authority automatically."
    )

    presentation = present_eof_recording_clock_status(matched=True, detail=detail)

    assert detail in presentation.text


def test_status_text_never_relies_on_color_alone() -> None:
    """Every state must carry a symbol + label, per the #305 non-color-only rule."""

    for matched in (True, False):
        presentation = present_eof_recording_clock_status(matched=matched, detail="x")
        assert presentation.text.split(" ", 1)[0]
        assert presentation.text.split(" ")[1].isupper()
