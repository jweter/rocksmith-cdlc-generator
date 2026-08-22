from __future__ import annotations

from rocksmith_cdlc_generator.desktop_polish import _REVIEW_AID_LABELS
from rocksmith_cdlc_generator.timing_review_ui import (
    CLICK_TRACK_HELP_TEXT,
    CLICK_TRACK_LABEL,
)


def test_click_track_label_still_matches_desktop_polish_promotion() -> None:
    """Regression guard for #305 Product Reality feedback: the click/beat-grid
    audition toggle is promoted from its literal build-time text
    ("Variable-tempo click") to "Click Track · Audition Beat Grid" and a
    visually-promoted style by desktop_polish.polish_widget_tree's exact-text
    allow-list, entirely independent of timing_review_ui.py.

    If CLICK_TRACK_LABEL ever drifts from the key desktop_polish matches on,
    the promotion silently stops applying with no error -- this test exists so
    that drift fails loudly instead.
    """
    assert CLICK_TRACK_LABEL in _REVIEW_AID_LABELS
    assert _REVIEW_AID_LABELS[CLICK_TRACK_LABEL] == "Click Track · Audition Beat Grid"


def test_click_track_help_text_explains_purpose_without_relying_on_color() -> None:
    """The #305 Product Reality request asked for 'a concise tooltip explaining
    that it plays an audible pulse on detected/reviewed beats so the user can
    judge alignment against the recording.' The caption text carries that
    meaning as plain text (never color-alone), matching this project's existing
    convention of explaining controls in visible text rather than relying on a
    hover-only affordance.
    """
    lowered = CLICK_TRACK_HELP_TEXT.lower()
    assert "pulse" in lowered
    assert "beat" in lowered
    assert CLICK_TRACK_HELP_TEXT.strip() == CLICK_TRACK_HELP_TEXT
    assert CLICK_TRACK_HELP_TEXT.endswith(".")
