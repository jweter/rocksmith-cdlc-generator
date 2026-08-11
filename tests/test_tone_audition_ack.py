import pytest

from rocksmith_cdlc_generator.tone_audition_ack import (
    acknowledge_tone_listening,
    verify_tone_listening_acknowledgement,
)
from rocksmith_cdlc_generator.tone_reference_review_diff import ToneReviewSettingsDiff


def _report() -> ToneReviewSettingsDiff:
    return ToneReviewSettingsDiff(
        artist="Artist",
        title="Song",
        bound_plan_sha256="b" * 64,
        catalog_sha256="c" * 64,
        changes=[],
        unchanged_component_count=2,
        human_review_required=True,
        can_approve=False,
        can_inject=False,
    )


def test_listening_acknowledgement_binds_exact_diff() -> None:
    report = _report()
    acknowledgement = acknowledge_tone_listening(
        report,
        reviewer="Jeremy",
        audition_method="live_instrument",
        arrangements=["lead", "rhythm"],
        decision="continue_to_review",
    )

    verify_tone_listening_acknowledgement(
        acknowledgement,
        report,
        require_continue_to_review=True,
    )
    assert acknowledgement.can_approve is False
    assert acknowledgement.can_inject is False
    assert acknowledgement.arrangements == ["lead", "rhythm"]


def test_changed_diff_invalidates_listening_acknowledgement() -> None:
    report = _report()
    acknowledgement = acknowledge_tone_listening(
        report,
        reviewer="Jeremy",
        audition_method="private_di_replay",
        arrangements=["lead"],
        decision="continue_to_review",
    )
    changed = report.model_copy(update={"unchanged_component_count": 3})

    with pytest.raises(ValueError, match="different staged settings diff"):
        verify_tone_listening_acknowledgement(acknowledgement, changed)


def test_reject_decision_cannot_satisfy_final_review_requirement() -> None:
    report = _report()
    acknowledgement = acknowledge_tone_listening(
        report,
        reviewer="Jeremy",
        audition_method="external_preview",
        arrangements=["bass"],
        decision="rejected",
    )

    with pytest.raises(ValueError, match="continue_to_review"):
        verify_tone_listening_acknowledgement(
            acknowledgement,
            report,
            require_continue_to_review=True,
        )


def test_duplicate_arrangements_are_rejected() -> None:
    report = _report()
    with pytest.raises(ValueError, match="unique"):
        acknowledge_tone_listening(
            report,
            reviewer="Jeremy",
            audition_method="live_instrument",
            arrangements=["lead", "Lead"],
            decision="keep_editing",
        )


def test_blank_reviewer_is_rejected() -> None:
    with pytest.raises(ValueError, match="reviewer"):
        acknowledge_tone_listening(
            _report(),
            reviewer="   ",
            audition_method="live_instrument",
            arrangements=["lead"],
            decision="continue_to_review",
        )
