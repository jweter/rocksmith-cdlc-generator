from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.tone_reference_audition_ack import (
    acknowledge_tone_audition,
    verify_tone_audition_acknowledgement,
)
from rocksmith_cdlc_generator.tone_reference_review_diff import ToneReviewSettingsDiff


def _report() -> ToneReviewSettingsDiff:
    return ToneReviewSettingsDiff(
        artist="Example Artist",
        title="Example Song",
        bound_plan_sha256="a" * 64,
        catalog_sha256="b" * 64,
        changes=[],
        unchanged_component_count=2,
        human_review_required=True,
        can_approve=False,
        can_inject=False,
    )


def test_audition_acknowledgement_binds_exact_diff():
    report = _report()
    ack = acknowledge_tone_audition(
        report,
        reviewer="Jeremy",
        decision="sounds_right",
        audition_method="Scarlett 2i2 live monitor",
    )
    verify_tone_audition_acknowledgement(ack, report)
    assert ack.human_listening_confirmed is True
    assert ack.can_approve is False
    assert ack.can_inject is False


def test_changed_diff_invalidates_audition_acknowledgement():
    report = _report()
    ack = acknowledge_tone_audition(
        report,
        reviewer="Jeremy",
        decision="sounds_right",
        audition_method="private dry DI A/B",
    )
    changed = report.model_copy(deep=True)
    changed.unchanged_component_count = 3
    with pytest.raises(ValueError, match="different staged settings diff"):
        verify_tone_audition_acknowledgement(ack, changed)


def test_revision_decision_is_not_approval():
    ack = acknowledge_tone_audition(
        _report(),
        reviewer="Jeremy",
        decision="needs_revision",
        audition_method="Scarlett 2i2 live monitor",
        reviewer_note="Delay too wet.",
    )
    assert ack.decision == "needs_revision"
    assert ack.can_approve is False
    assert ack.can_inject is False


def test_blank_identity_or_method_is_rejected():
    with pytest.raises(ValueError, match="reviewer"):
        acknowledge_tone_audition(_report(), reviewer="   ", decision="sounds_right", audition_method="Scarlett")
    with pytest.raises(ValueError, match="audition_method"):
        acknowledge_tone_audition(_report(), reviewer="Jeremy", decision="sounds_right", audition_method="   ")


def test_unsafe_diff_is_rejected():
    data = _report().model_dump()
    data["can_approve"] = True
    unsafe = ToneReviewSettingsDiff.model_construct(**data)
    with pytest.raises(ValueError, match="not valid"):
        acknowledge_tone_audition(unsafe, reviewer="Jeremy", decision="sounds_right", audition_method="Scarlett")
