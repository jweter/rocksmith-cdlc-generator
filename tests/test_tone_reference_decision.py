from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.tone_reference_decision import (
    build_review_decision,
    stage_accepted_components,
)
from rocksmith_cdlc_generator.tone_reference_proposal import (
    ProposedReferenceComponent,
    ToneReferenceReviewerProposal,
)
from rocksmith_cdlc_generator.tone_review import (
    ToneComponentReview,
    ToneReviewArtifact,
    ToneReviewItem,
)


def _proposal() -> ToneReferenceReviewerProposal:
    return ToneReferenceReviewerProposal(
        artist="Example Artist",
        title="Example Song",
        arrangement="lead",
        arrangement_label="Lead",
        bound_plan_sha256="a" * 64,
        evidence_sha256="b" * 64,
        candidate_fingerprint="c" * 64,
        candidate_source_type="official_rocksmith",
        candidate_source_path="C:/Rocksmith2014/dlc/reference.psarc",
        candidate_source_psarc_sha256="d" * 64,
        candidate_tone_key="reference_tone",
        selected_components=[
            ProposedReferenceComponent(
                slot="Amp",
                device_key="reference_amp",
                device_name="Reference Amp",
                observed_knob_values={"Gain": 0.72, "Treble": 0.61},
            ),
            ProposedReferenceComponent(
                slot="PostPedal1",
                device_key="reference_delay",
                device_name="Reference Delay",
                observed_knob_values={"Mix": 0.25},
            ),
        ],
    )


def _review() -> ToneReviewArtifact:
    return ToneReviewArtifact(
        artist="Example Artist",
        title="Example Song",
        catalog_sha256="catalog",
        bound_plan_sha256="a" * 64,
        tones=[
            ToneReviewItem(
                arrangement="lead",
                label="Lead",
                components=[
                    ToneComponentReview(
                        family="amp_high_gain",
                        slot="Amp",
                        device_key="original_amp",
                        device_name="Original Amp",
                        knob_values={"Gain": 0.4},
                    ),
                    ToneComponentReview(
                        family="delay",
                        slot="PostPedal1",
                        device_key="original_delay",
                        device_name="Original Delay",
                        knob_values={"Mix": 0.1},
                    ),
                ],
            )
        ],
        ready_for_injection=False,
    )


def test_accepted_component_is_staged_but_remains_pending() -> None:
    proposal = _proposal()
    decision = build_review_decision(
        proposal,
        accept_slots=["Amp"],
        reject_slots=["PostPedal1"],
        reviewer_note="Amp sounds closest; keep current delay.",
    )

    staged = stage_accepted_components(_review(), proposal, decision)
    lead = staged.tones[0]
    amp = next(component for component in lead.components if component.slot == "Amp")
    delay = next(component for component in lead.components if component.slot == "PostPedal1")

    assert amp.device_key == "reference_amp"
    assert amp.knob_values == {"Gain": 0.72, "Treble": 0.61}
    assert amp.decision == "pending"
    assert "final component approval is still required" in (amp.reviewer_note or "")
    assert delay.device_key == "original_delay"
    assert delay.knob_values == {"Mix": 0.1}
    assert delay.decision == "pending"
    assert lead.decision == "pending"
    assert staged.ready_for_injection is False
    assert decision.can_auto_apply is False
    assert decision.can_inject is False


def test_every_proposed_component_requires_explicit_decision() -> None:
    with pytest.raises(ValueError, match="every proposed component requires an explicit decision"):
        build_review_decision(_proposal(), accept_slots=["Amp"])


def test_same_slot_cannot_be_accepted_and_rejected() -> None:
    with pytest.raises(ValueError, match="both accepted and rejected"):
        build_review_decision(
            _proposal(),
            accept_slots=["Amp", "PostPedal1"],
            reject_slots=["Amp"],
        )


def test_unknown_decision_slot_is_rejected() -> None:
    with pytest.raises(ValueError, match="not present in proposal"):
        build_review_decision(
            _proposal(),
            accept_slots=["Amp", "Rack1"],
            reject_slots=["PostPedal1"],
        )


def test_decision_cannot_stage_against_different_bound_plan() -> None:
    proposal = _proposal()
    decision = build_review_decision(
        proposal,
        accept_slots=["Amp"],
        reject_slots=["PostPedal1"],
    )
    review = _review().model_copy(update={"bound_plan_sha256": "e" * 64})

    with pytest.raises(ValueError, match="different bound tone plan"):
        stage_accepted_components(review, proposal, decision)


def test_tampered_proposal_is_rejected_by_decision_digest() -> None:
    proposal = _proposal()
    decision = build_review_decision(
        proposal,
        accept_slots=["Amp"],
        reject_slots=["PostPedal1"],
    )
    tampered = proposal.model_copy(update={"candidate_tone_key": "different"})

    with pytest.raises(ValueError, match="different reviewer proposal"):
        stage_accepted_components(_review(), tampered, decision)
