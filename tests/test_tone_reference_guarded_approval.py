import pytest

from rocksmith_cdlc_generator.tone_catalog import (
    BoundRocksmithTone,
    BoundRocksmithTonePlan,
    BoundToneComponent,
)
from rocksmith_cdlc_generator.tone_reference_final_ack import acknowledge_staged_settings_diff
from rocksmith_cdlc_generator.tone_reference_guarded_approval import (
    ComponentApprovalRequest,
    GuardedToneApprovalRequest,
    ToneApprovalRequest,
    guarded_final_tone_approval,
)
from rocksmith_cdlc_generator.tone_reference_review_diff import build_staged_settings_diff
from rocksmith_cdlc_generator.tone_review import ToneReviewArtifact, create_tone_review


def _reviews() -> tuple[ToneReviewArtifact, ToneReviewArtifact]:
    plan = BoundRocksmithTonePlan(
        artist="Example Artist",
        title="Example Song",
        catalog_sha256="a" * 64,
        tones=[
            BoundRocksmithTone(
                arrangement="lead",
                label="Lead",
                components=[
                    BoundToneComponent(
                        family="amp_high_gain",
                        device_key="amp_original",
                        device_name="Original Amp",
                        device_type="Amp",
                        slot="Amp",
                        knob_values={"Gain": 0.5},
                        confidence=0.8,
                        reason="synthetic test",
                    ),
                    BoundToneComponent(
                        family="delay",
                        device_key="delay_original",
                        device_name="Original Delay",
                        device_type="Rack",
                        slot="Rack1",
                        knob_values={"Mix": 0.2},
                        confidence=0.7,
                        reason="synthetic test",
                    ),
                ],
            )
        ],
    )
    original = create_tone_review(plan)
    data = original.model_dump()
    data["tones"][0]["components"][0]["device_key"] = "amp_staged"
    data["tones"][0]["components"][0]["device_name"] = "Staged Amp"
    data["tones"][0]["components"][0]["knob_values"] = {"Gain": 0.7}
    staged = ToneReviewArtifact.model_validate(data)
    return original, staged


def test_guarded_approval_requires_current_acknowledged_diff() -> None:
    original, staged = _reviews()
    diff = build_staged_settings_diff(original, staged)
    acknowledgement = acknowledge_staged_settings_diff(diff, reviewer="Human Reviewer")
    request = GuardedToneApprovalRequest(
        component_approvals=[
            ComponentApprovalRequest(arrangement="lead", family="amp_high_gain"),
            ComponentApprovalRequest(arrangement="lead", family="delay"),
        ],
        tone_approvals=[ToneApprovalRequest(arrangement="lead")],
    )

    approved = guarded_final_tone_approval(original, staged, diff, acknowledgement, request)

    assert approved.ready_for_injection is True
    assert all(item.decision == "approved" for item in approved.tones[0].components)
    assert approved.tones[0].decision == "approved"
    assert approved.tones[0].components[0].device_key == "amp_staged"
    assert approved.tones[0].components[0].knob_values == {"Gain": 0.7}


def test_changed_staged_settings_invalidate_acknowledgement() -> None:
    original, staged = _reviews()
    diff = build_staged_settings_diff(original, staged)
    acknowledgement = acknowledge_staged_settings_diff(diff, reviewer="Human Reviewer")

    changed = staged.model_copy(deep=True)
    changed.tones[0].components[0].knob_values["Gain"] = 0.9

    with pytest.raises(ValueError, match="do not match the acknowledged diff"):
        guarded_final_tone_approval(
            original,
            changed,
            diff,
            acknowledgement,
            GuardedToneApprovalRequest(
                component_approvals=[
                    ComponentApprovalRequest(arrangement="lead", family="amp_high_gain")
                ]
            ),
        )


def test_no_approval_happens_without_explicit_actions() -> None:
    original, staged = _reviews()
    diff = build_staged_settings_diff(original, staged)
    acknowledgement = acknowledge_staged_settings_diff(diff, reviewer="Human Reviewer")

    with pytest.raises(ValueError, match="at least one explicit approval action"):
        guarded_final_tone_approval(
            original,
            staged,
            diff,
            acknowledgement,
            GuardedToneApprovalRequest(),
        )


def test_tone_approval_still_requires_every_component_approved() -> None:
    original, staged = _reviews()
    diff = build_staged_settings_diff(original, staged)
    acknowledgement = acknowledge_staged_settings_diff(diff, reviewer="Human Reviewer")

    with pytest.raises(ValueError, match="all tone components must be approved"):
        guarded_final_tone_approval(
            original,
            staged,
            diff,
            acknowledgement,
            GuardedToneApprovalRequest(
                component_approvals=[
                    ComponentApprovalRequest(arrangement="lead", family="amp_high_gain")
                ],
                tone_approvals=[ToneApprovalRequest(arrangement="lead")],
            ),
        )


def test_duplicate_actions_fail_closed() -> None:
    original, staged = _reviews()
    diff = build_staged_settings_diff(original, staged)
    acknowledgement = acknowledge_staged_settings_diff(diff, reviewer="Human Reviewer")

    with pytest.raises(ValueError, match="duplicate component approval"):
        guarded_final_tone_approval(
            original,
            staged,
            diff,
            acknowledgement,
            GuardedToneApprovalRequest(
                component_approvals=[
                    ComponentApprovalRequest(arrangement="lead", family="delay"),
                    ComponentApprovalRequest(arrangement="LEAD", family="DELAY"),
                ]
            ),
        )
