from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.tone_reference_final_ack import (
    acknowledge_staged_settings_diff,
    staged_diff_digest,
    verify_final_review_acknowledgement,
)
from rocksmith_cdlc_generator.tone_reference_review_diff import (
    ComponentSettingsDiff,
    KnobValueChange,
    ToneReviewSettingsDiff,
)


def _diff() -> ToneReviewSettingsDiff:
    return ToneReviewSettingsDiff(
        artist="Example Artist",
        title="Example Song",
        bound_plan_sha256="a" * 64,
        catalog_sha256="b" * 64,
        changes=[
            ComponentSettingsDiff(
                arrangement="lead",
                arrangement_label="Lead",
                family="amp",
                slot="Amp",
                original_device_key="old_amp",
                staged_device_key="new_amp",
                original_device_name="Old Amp",
                staged_device_name="New Amp",
                knob_changes=[KnobValueChange(name="Gain", original=0.4, staged=0.7)],
            )
        ],
        unchanged_component_count=2,
    )


def test_acknowledgement_binds_reviewer_to_exact_diff() -> None:
    report = _diff()
    acknowledgement = acknowledge_staged_settings_diff(
        report,
        reviewer="Jeremy Weter",
        reviewer_note="Compared staged amp and gain against original.",
    )

    assert acknowledgement.reviewer == "Jeremy Weter"
    assert acknowledgement.staged_diff_sha256 == staged_diff_digest(report)
    assert acknowledgement.human_review_confirmed is True
    assert acknowledgement.can_approve is False
    assert acknowledgement.can_inject is False
    verify_final_review_acknowledgement(acknowledgement, report)


def test_acknowledgement_rejects_blank_reviewer() -> None:
    with pytest.raises(ValueError, match="non-whitespace"):
        acknowledge_staged_settings_diff(_diff(), reviewer="   ")


def test_acknowledgement_rejects_tampered_diff() -> None:
    report = _diff()
    acknowledgement = acknowledge_staged_settings_diff(report, reviewer="Reviewer")
    changed = report.model_copy(deep=True)
    changed.changes[0].knob_changes[0].staged = 0.8

    with pytest.raises(ValueError, match="different staged settings diff"):
        verify_final_review_acknowledgement(acknowledgement, changed)


def test_acknowledgement_rejects_unsafe_diff_flags() -> None:
    report = _diff().model_copy(update={"can_approve": True})

    with pytest.raises(ValueError, match="safety flags"):
        acknowledge_staged_settings_diff(report, reviewer="Reviewer")


def test_acknowledgement_itself_cannot_claim_approval() -> None:
    report = _diff()
    acknowledgement = acknowledge_staged_settings_diff(report, reviewer="Reviewer")
    unsafe = acknowledgement.model_copy(update={"can_inject": True})

    with pytest.raises(ValueError, match="cannot grant approval or injection"):
        verify_final_review_acknowledgement(unsafe, report)
