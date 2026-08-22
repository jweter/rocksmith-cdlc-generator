from __future__ import annotations

from rocksmith_cdlc_generator.score_mapping_status_presentation import present_mapping_role_status


def test_no_score_registered_is_informational_not_actionable() -> None:
    presentation = present_mapping_role_status(has_score=False, has_selection=False, human_confirmed=False)

    assert presentation.status_state == "info"
    assert "No score registered" in presentation.text


def test_score_registered_with_no_selection_requires_review() -> None:
    presentation = present_mapping_role_status(has_score=True, has_selection=False, human_confirmed=False)

    assert presentation.status_state == "review_required"
    assert "No track selected" in presentation.text


def test_selection_without_confirmation_still_requires_review() -> None:
    """Selecting a track is never itself confirmation -- mappings are never auto-accepted."""

    presentation = present_mapping_role_status(has_score=True, has_selection=True, human_confirmed=False)

    assert presentation.status_state == "review_required"
    assert "Confirm" in presentation.text


def test_human_confirmed_selection_is_pass() -> None:
    presentation = present_mapping_role_status(has_score=True, has_selection=True, human_confirmed=True)

    assert presentation.status_state == "pass"
    assert "Confirmed" in presentation.text


def test_confirmed_flag_wins_even_if_selection_flag_disagrees() -> None:
    """Persisted human-confirmed authority (see confirm_score_mapping) is decisive;
    a caller should never be able to pass has_selection=False alongside
    human_confirmed=True in practice, but if it happens the confirmed status must
    still win rather than silently downgrading confirmed mapping authority."""

    presentation = present_mapping_role_status(has_score=True, has_selection=False, human_confirmed=True)

    assert presentation.status_state == "pass"


def test_status_text_never_relies_on_color_alone() -> None:
    """Every state must carry a symbol + label, per the #305 non-color-only rule."""

    for has_selection in (False, True):
        for human_confirmed in (False, True):
            presentation = present_mapping_role_status(
                has_score=True, has_selection=has_selection, human_confirmed=human_confirmed
            )
            # format_status always renders "<symbol> <LABEL>[ — detail]"; assert both
            # a non-space symbol prefix and an uppercase semantic label are present.
            assert presentation.text.split(" ", 1)[0]
            assert presentation.text.split(" ")[1].isupper()
