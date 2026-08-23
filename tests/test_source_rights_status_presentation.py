from __future__ import annotations

from rocksmith_cdlc_generator.source_rights_status_presentation import present_source_rights_status


def test_unregistered_source_is_informational_not_actionable() -> None:
    presentation = present_source_rights_status(registered=False, reviewed=False)

    assert presentation.status_state == "info"
    assert "Not registered" in presentation.text


def test_registered_unreviewed_source_requires_review() -> None:
    presentation = present_source_rights_status(registered=True, reviewed=False)

    assert presentation.status_state == "review_required"
    assert "review required" in presentation.text


def test_registered_reviewed_source_is_pass() -> None:
    presentation = present_source_rights_status(registered=True, reviewed=True)

    assert presentation.status_state == "pass"
    assert "Reviewed" in presentation.text


def test_reviewed_flag_is_ignored_when_not_registered() -> None:
    """Registering a source is never itself a rights/provenance decision, but a
    source that was never registered has nothing to review yet either -- an
    unregistered source must always read as informational, regardless of what a
    caller passes for ``reviewed``."""

    presentation = present_source_rights_status(registered=False, reviewed=True)

    assert presentation.status_state == "info"


def test_status_text_never_relies_on_color_alone() -> None:
    """Every state must carry a symbol + label, per the #305 non-color-only rule."""

    for registered in (False, True):
        for reviewed in (False, True):
            presentation = present_source_rights_status(registered=registered, reviewed=reviewed)
            # format_status always renders "<symbol> <LABEL>[ — detail]"; assert both
            # a non-space symbol prefix and an uppercase semantic label are present.
            assert presentation.text.split(" ", 1)[0]
            assert presentation.text.split(" ")[1].isupper()
