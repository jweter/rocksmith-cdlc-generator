from __future__ import annotations

from rocksmith_cdlc_generator.song_workspace_health_presentation import (
    present_workspace_health,
    progressbar_style_name,
)


def test_blocked_maps_to_fail_status() -> None:
    presentation = present_workspace_health("BLOCKED")

    assert presentation.status_state == "fail"
    assert presentation.health_text.startswith("✗ FAIL")
    assert presentation.progressbar_style == "Status.Fail.Horizontal.TProgressbar"


def test_review_maps_to_review_required_status() -> None:
    presentation = present_workspace_health("REVIEW")

    assert presentation.status_state == "review_required"
    assert presentation.health_text.startswith("◉ REVIEW REQUIRED")
    assert presentation.progressbar_style == "Status.ReviewRequired.Horizontal.TProgressbar"


def test_ready_maps_to_pass_status() -> None:
    presentation = present_workspace_health("READY")

    assert presentation.status_state == "pass"
    assert presentation.health_text.startswith("✓ PASS")
    assert presentation.progressbar_style == "Status.Pass.Horizontal.TProgressbar"


def test_new_maps_to_info_status() -> None:
    presentation = present_workspace_health("NEW")

    assert presentation.status_state == "info"
    assert presentation.health_text.startswith("ℹ INFO")


def test_in_progress_maps_to_info_status_distinct_from_new() -> None:
    """NEW and IN_PROGRESS share the same semantic StatusState (info -- neither is a
    problem or a completed state) but must remain distinguishable in the detail text.
    """

    new_presentation = present_workspace_health("NEW")
    in_progress_presentation = present_workspace_health("IN_PROGRESS")

    assert new_presentation.status_state == in_progress_presentation.status_state == "info"
    assert new_presentation.health_text != in_progress_presentation.health_text


def test_unrecognized_health_falls_back_to_info_instead_of_raising() -> None:
    """Defensive only: WorkspaceHealth is a Literal, so normal callers can never reach
    this path, but the presentation layer must not crash a real header render if that
    contract is ever loosened.
    """

    presentation = present_workspace_health("SOMETHING_NEW")

    assert presentation.status_state == "info"
    assert presentation.health_text.startswith("ℹ INFO")


def test_health_text_never_conveys_state_by_color_alone() -> None:
    """Every status text must pair a distinct symbol with readable label text so the
    state is legible even in a context that renders no color at all.
    """

    texts = {
        present_workspace_health(health).health_text
        for health in ("NEW", "IN_PROGRESS", "REVIEW", "BLOCKED", "READY")
    }
    assert len(texts) == 5
    for text in texts:
        symbol, rest = text.split(" ", 1)
        assert symbol
        assert rest


def test_progressbar_style_name_is_a_distinct_horizontal_progressbar_variant() -> None:
    names = {progressbar_style_name(state) for state in ("pass", "warning", "fail", "stale", "review_required", "info")}
    assert len(names) == 6
    for name in names:
        assert name.startswith("Status.")
        assert name.endswith(".Horizontal.TProgressbar")
