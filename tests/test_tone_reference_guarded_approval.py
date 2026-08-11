import pytest

from rocksmith_cdlc_generator.tone_reference_final_ack import acknowledge_staged_settings_diff
from rocksmith_cdlc_generator.tone_reference_guarded_approval import approve_acknowledged_staged_review
from rocksmith_cdlc_generator.tone_reference_review_diff import build_staged_settings_diff
from rocksmith_cdlc_generator.tone_review import (
    ToneComponentReview,
    ToneReviewArtifact,
    ToneReviewItem,
)


def _review(*, device_key: str = "amp-a", gain: float = 0.5, resolved: bool = True) -> ToneReviewArtifact:
    component = ToneComponentReview(
        family="amp_high_gain",
        device_key=device_key if resolved else None,
        device_name="High Gain Amp" if resolved else None,
        slot="Amp" if resolved else None,
        knob_values={"Gain": gain},
    )
    return ToneReviewArtifact(
        artist="Artist",
        title="Song",
        catalog_sha256="c" * 64,
        bound_plan_sha256="b" * 64,
        tones=[ToneReviewItem(arrangement="lead", label="Lead", components=[component])],
        ready_for_injection=False,
    )


def _acknowledged_pair():
    original = _review(device_key="amp-a", gain=0.5)
    staged = _review(device_key="amp-b", gain=0.7)
    report = build_staged_settings_diff(original, staged)
    acknowledgement = acknowledge_staged_settings_diff(report, reviewer="Jeremy")
    return original, staged, report, acknowledgement


def test_guarded_approval_closes_gate_without_changing_settings() -> None:
    original, staged, report, acknowledgement = _acknowledged_pair()

    approved, receipt = approve_acknowledged_staged_review(
        original,
        staged,
        report,
        acknowledgement,
        reviewer="Jeremy",
        confirm_approval=True,
        reviewer_note="Audited staged settings.",
    )

    assert approved.ready_for_injection is True
    assert approved.tones[0].decision == "approved"
    component = approved.tones[0].components[0]
    assert component.decision == "approved"
    assert component.device_key == "amp-b"
    assert component.knob_values == {"Gain": 0.7}
    assert receipt.ready_for_injection is True
    assert receipt.settings_changed_during_approval is False
    assert receipt.approved_components == ["lead/amp_high_gain"]
    assert receipt.approved_tones == ["lead"]


def test_guarded_approval_requires_explicit_confirmation() -> None:
    original, staged, report, acknowledgement = _acknowledged_pair()

    with pytest.raises(ValueError, match="confirm_approval"):
        approve_acknowledged_staged_review(
            original,
            staged,
            report,
            acknowledgement,
            reviewer="Jeremy",
            confirm_approval=False,
        )


def test_guarded_approval_rejects_different_reviewer() -> None:
    original, staged, report, acknowledgement = _acknowledged_pair()

    with pytest.raises(ValueError, match="must match"):
        approve_acknowledged_staged_review(
            original,
            staged,
            report,
            acknowledgement,
            reviewer="Other Reviewer",
            confirm_approval=True,
        )


def test_guarded_approval_rejects_staged_changes_after_acknowledgement() -> None:
    original, staged, report, acknowledgement = _acknowledged_pair()
    changed_after_ack = _review(device_key="amp-b", gain=0.9)

    with pytest.raises(ValueError, match="stale|current staged review"):
        approve_acknowledged_staged_review(
            original,
            changed_after_ack,
            report,
            acknowledgement,
            reviewer="Jeremy",
            confirm_approval=True,
        )


def test_guarded_approval_rejects_unresolved_component() -> None:
    original = _review(resolved=False)
    staged = _review(resolved=False)
    report = build_staged_settings_diff(original, staged)
    acknowledgement = acknowledge_staged_settings_diff(report, reviewer="Jeremy")

    with pytest.raises(ValueError, match="unresolved"):
        approve_acknowledged_staged_review(
            original,
            staged,
            report,
            acknowledgement,
            reviewer="Jeremy",
            confirm_approval=True,
        )
