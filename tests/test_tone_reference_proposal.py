from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.tone_reference_proposal import (
    build_reviewer_proposal,
    evidence_digest,
    write_reviewer_proposal,
)
from rocksmith_cdlc_generator.tone_reference_recommendations import (
    ArrangementReferenceEvidence,
    RecommendedReferenceComponent,
    ToneRecommendationEvidenceReport,
    ToneReferenceCandidate,
)


def _report() -> ToneRecommendationEvidenceReport:
    return ToneRecommendationEvidenceReport(
        artist="Example Artist",
        title="Example Song",
        bound_plan_sha256="a" * 64,
        library_scan_root="C:/private/rocksmith-tone-library",
        library_psarc_count=1,
        library_tone_count=1,
        arrangements=[
            ArrangementReferenceEvidence(
                arrangement="lead",
                label="Lead",
                query_device_keys=["amp_key"],
                candidates=[
                    ToneReferenceCandidate(
                        score=0.9,
                        authority_weight=1.0,
                        source_type="official_rocksmith",
                        source_path="C:/Rocksmith2014/dlc/example.psarc",
                        source_psarc_sha256="b" * 64,
                        tone_key="tone_a",
                        tone_name="Lead Tone",
                        fingerprint="c" * 64,
                        matched_device_keys=["amp_key"],
                        components=[
                            RecommendedReferenceComponent(
                                slot="Amp",
                                device_key="amp_key",
                                knob_values={"Gain": 0.7},
                            ),
                            RecommendedReferenceComponent(
                                slot="Cabinet",
                                device_key="cab_key",
                            ),
                        ],
                    )
                ],
            )
        ],
    )


def test_proposal_copies_only_selected_evidence_and_remains_unapproved() -> None:
    report = _report()
    proposal = build_reviewer_proposal(
        report,
        arrangement="lead",
        candidate_fingerprint="c" * 64,
        component_slots=["Amp"],
        reviewer_note="Compare this gain structure by ear.",
    )

    assert proposal.evidence_sha256 == evidence_digest(report)
    assert proposal.bound_plan_sha256 == "a" * 64
    assert [component.slot for component in proposal.selected_components] == ["Amp"]
    assert proposal.selected_components[0].observed_knob_values == {"Gain": 0.7}
    assert proposal.selected_components[0].approved is False
    assert proposal.approved is False
    assert proposal.can_auto_apply is False
    assert proposal.can_inject is False
    assert proposal.human_review_required is True


def test_proposal_rejects_candidate_not_in_evidence() -> None:
    with pytest.raises(ValueError, match="Candidate fingerprint"):
        build_reviewer_proposal(
            _report(),
            arrangement="lead",
            candidate_fingerprint="d" * 64,
        )


def test_proposal_rejects_unknown_component_slot() -> None:
    with pytest.raises(ValueError, match="Requested component slots"):
        build_reviewer_proposal(
            _report(),
            arrangement="lead",
            candidate_fingerprint="c" * 64,
            component_slots=["Rack1"],
        )


def test_proposal_writer_keeps_private_artifact_unapproved(tmp_path) -> None:
    proposal = build_reviewer_proposal(
        _report(),
        arrangement="lead",
        candidate_fingerprint="c" * 64,
    )
    path = write_reviewer_proposal(proposal, tmp_path / "proposal.json")
    text = path.read_text(encoding="utf-8")

    assert '"approved": false' in text
    assert '"can_auto_apply": false' in text
    assert '"can_inject": false' in text
    assert '"observed_knob_values"' in text
