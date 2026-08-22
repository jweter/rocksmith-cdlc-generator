from __future__ import annotations

from rocksmith_cdlc_generator.track_trust_status_presentation import present_track_trust_status
from rocksmith_cdlc_generator.track_trust_workspace_controls import TrackTrustWorkspaceControl


def _control(review_state: str) -> TrackTrustWorkspaceControl:
    return TrackTrustWorkspaceControl(
        arrangement="bass",
        source_track_index=0,
        source_track_name="Bass",
        note_count=412,
        review_state=review_state,
        button_text="Accept Track Source",
        button_enabled=True,
        status_text="Bass source trust has not been explicitly accepted for Bass (412 events).",
    )


def test_current_review_state_is_pass() -> None:
    presentation = present_track_trust_status(_control("current"))

    assert presentation.status_state == "pass"
    assert "PASS" in presentation.text


def test_stale_review_state_is_stale() -> None:
    presentation = present_track_trust_status(_control("stale"))

    assert presentation.status_state == "stale"
    assert "STALE" in presentation.text


def test_unreviewed_review_state_requires_review() -> None:
    presentation = present_track_trust_status(_control("unreviewed"))

    assert presentation.status_state == "review_required"
    assert "REVIEW REQUIRED" in presentation.text


def test_detail_text_is_preserved_verbatim() -> None:
    """Only the leading symbol/label/color changes -- existing detail is not lost."""

    presentation = present_track_trust_status(_control("current"))

    assert "Bass" in presentation.text
    assert "412 notes" in presentation.text
    assert "Bass source trust has not been explicitly accepted for Bass (412 events)." in presentation.text


def test_status_text_never_relies_on_color_alone() -> None:
    """Every state must carry a symbol + label, per the #305 non-color-only rule."""

    for review_state in ("current", "stale", "unreviewed"):
        presentation = present_track_trust_status(_control(review_state))
        assert presentation.text.split(" ", 1)[0]
        assert presentation.text.split(" ")[1].isupper()
