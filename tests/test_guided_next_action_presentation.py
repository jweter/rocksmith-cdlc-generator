from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.guided_next_action_presentation import present_guided_next_action


def test_human_gate_is_explicit_and_non_color_only() -> None:
    presentation = present_guided_next_action("Review Score Tracks", needs_human=True)

    assert presentation.eyebrow == "NEXT REQUIRED ACTION ›"
    assert presentation.button_text == "› Review Score Tracks"
    assert presentation.button_style == "Primary.TButton"


def test_automatic_action_is_prominent_without_claiming_human_gate() -> None:
    presentation = present_guided_next_action("Continue Automatically", needs_human=False)

    assert presentation.eyebrow == "NEXT ACTION ›"
    assert presentation.button_text == "› Continue Automatically"
    assert presentation.button_style == "Primary.TButton"


def test_empty_action_label_fails_closed() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        present_guided_next_action("   ", needs_human=True)
