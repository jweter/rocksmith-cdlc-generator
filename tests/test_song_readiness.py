from rocksmith_cdlc_generator.guided_desktop import GuidedDesktopApp
from rocksmith_cdlc_generator.song_readiness import build_song_readiness
from rocksmith_cdlc_generator.workflow_plan import ProjectWorkflowPlan, WorkflowStep


def _plan(*steps: WorkflowStep) -> ProjectWorkflowPlan:
    next_step = next((step.step_id for step in steps if step.status in {"blocked", "ready"}), None)
    return ProjectWorkflowPlan(
        project_path="C:/project",
        steps=list(steps),
        next_step_id=next_step,
        automatic_ready_steps=sum(
            step.status == "ready" and step.mode == "automatic" for step in steps
        ),
        human_blocking_steps=sum(
            step.status == "blocked" and step.mode == "human" for step in steps
        ),
    )


def _step(step_id: str, status: str, mode: str, title: str = "Internal title") -> WorkflowStep:
    return WorkflowStep(
        step_id=step_id,
        title=title,
        status=status,
        mode=mode,
        reason=f"Reason for {step_id}",
    )


def test_readiness_uses_first_actionable_step_not_later_human_dependency() -> None:
    readiness = build_song_readiness(
        _plan(
            _step("recording-audio", "complete", "human"),
            _step("normalize", "ready", "automatic"),
            _step("human-review", "blocked", "human"),
        )
    )

    assert readiness.percent == 33
    assert readiness.headline == "Ready to continue automatically"
    assert readiness.next_action is not None
    assert readiness.next_action.kind == "automatic"
    assert readiness.next_action.step_id == "normalize"
    assert readiness.needs_you == ()


def test_actionable_ready_human_step_is_needs_you() -> None:
    readiness = build_song_readiness(
        _plan(
            _step("recording-audio", "complete", "human"),
            _step("score-arrangements", "ready", "human"),
            _step("normalize", "blocked", "automatic"),
        )
    )

    assert readiness.headline == "Needs you: 1 decision"
    assert readiness.next_action is not None
    assert readiness.next_action.kind == "needs_you"
    assert readiness.next_action.step_id == "score-arrangements"


def test_optional_steps_do_not_reduce_readiness_percentage() -> None:
    readiness = build_song_readiness(
        _plan(
            _step("recording-audio", "complete", "human"),
            _step("recording-reference", "optional", "human"),
        )
    )

    assert readiness.percent == 100
    assert readiness.required_steps == 1
    assert readiness.completed_steps == 1
    assert readiness.next_action is None


def test_terminal_human_review_is_100_percent_prepared_but_still_needs_user() -> None:
    readiness = build_song_readiness(
        _plan(
            _step("recording-audio", "complete", "human"),
            _step("normalize", "complete", "automatic"),
            _step("validate", "complete", "automatic"),
            _step("human-review", "ready", "human"),
        )
    )

    assert readiness.percent == 100
    assert readiness.completed_steps == readiness.required_steps
    assert readiness.headline == "Needs you: 1 decision"
    assert readiness.next_action is not None
    assert readiness.next_action.kind == "needs_you"
    assert readiness.next_action.step_id == "human-review"
    assert "generated song draft" in readiness.next_action.title

    headline, detail = GuidedDesktopApp.readiness_display(readiness)
    assert headline.startswith("100% prepared — Needs you")
    assert "100% ready" not in headline
    assert detail.startswith("Needs you next:")


def test_automatic_ready_step_becomes_next_action_when_no_human_gate_blocks() -> None:
    readiness = build_song_readiness(
        _plan(
            _step("recording-audio", "complete", "human"),
            _step("normalize", "ready", "automatic"),
            _step("tempo", "blocked", "automatic"),
        )
    )

    assert readiness.headline == "Ready to continue automatically"
    assert readiness.next_action is not None
    assert readiness.next_action.kind == "automatic"
    assert readiness.next_action.step_id == "normalize"


def test_guided_display_uses_plain_user_direction() -> None:
    readiness = build_song_readiness(
        _plan(
            _step("source-rights", "blocked", "human"),
            _step("normalize", "blocked", "automatic"),
        )
    )

    headline, detail = GuidedDesktopApp.readiness_display(readiness)

    assert headline.startswith("0% prepared — Needs you")
    assert detail.startswith("Needs you next:")
    assert "allowed to use" in detail
    assert "cdlc" not in detail.lower()


def test_guided_display_points_to_continue_automatically() -> None:
    readiness = build_song_readiness(
        _plan(
            _step("recording-audio", "complete", "human"),
            _step("tempo", "ready", "automatic"),
        )
    )

    headline, detail = GuidedDesktopApp.readiness_display(readiness)

    assert "% prepared" in headline
    assert "Continue Automatically" in detail
    assert "Map the song timing" in detail


def test_guided_action_routes_automatic_work_to_continue() -> None:
    readiness = build_song_readiness(
        _plan(
            _step("recording-audio", "complete", "human"),
            _step("normalize", "ready", "automatic"),
        )
    )

    assert GuidedDesktopApp.guided_action_spec(readiness) == (
        "Continue Automatically",
        "automatic",
    )


def test_guided_action_routes_score_mapping_to_existing_review_tab() -> None:
    readiness = build_song_readiness(
        _plan(_step("score-arrangements", "blocked", "human"))
    )

    assert GuidedDesktopApp.guided_action_spec(readiness) == (
        "Review Score Tracks",
        "score",
    )


def test_guided_action_routes_source_rights_to_existing_review_tab() -> None:
    readiness = build_song_readiness(_plan(_step("source-rights", "blocked", "human")))

    assert GuidedDesktopApp.guided_action_spec(readiness) == (
        "Review Source Rights",
        "rights",
    )


def test_guided_rights_target_skips_already_reviewed_recording() -> None:
    choices = {
        "Recording audio — aaaa…": "audio-sha",
        "Complete score — bbbb…": "score-sha",
    }
    reviews = {"audio-sha": object()}

    assert GuidedDesktopApp.first_unreviewed_source_label(choices, reviews) == (
        "Complete score — bbbb…"
    )


def test_guided_rights_target_is_none_when_every_source_is_reviewed() -> None:
    choices = {
        "Recording audio — aaaa…": "audio-sha",
        "Complete score — bbbb…": "score-sha",
    }
    reviews = {"audio-sha": object(), "score-sha": object()}

    assert GuidedDesktopApp.first_unreviewed_source_label(choices, reviews) is None


def test_guided_action_routes_terminal_review_to_song_workspace() -> None:
    readiness = build_song_readiness(_plan(_step("human-review", "ready", "human")))

    assert GuidedDesktopApp.guided_action_spec(readiness) == (
        "Open Song Review",
        "song-review",
    )


def test_unknown_human_gate_falls_back_to_workflow_details_without_guessing_authority() -> None:
    readiness = build_song_readiness(_plan(_step("future-review", "blocked", "human")))

    assert GuidedDesktopApp.guided_action_spec(readiness) == (
        "Show Workflow Details",
        "workflow",
    )
