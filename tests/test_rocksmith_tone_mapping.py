from rocksmith_cdlc_generator.rocksmith_tone_mapping import map_tone_hypothesis
from rocksmith_cdlc_generator.tone_research import (
    EffectCandidate,
    SongIdentity,
    ToneRigHypothesis,
)


def _hypothesis():
    return ToneRigHypothesis(
        song=SongIdentity(artist="Example Band", title="Example Song", album="Example Album"),
        gear=[],
        effects=[
            EffectCandidate(
                family="overdrive",
                arrangement="lead",
                support_score=1.4,
                evidence_urls=["https://example.com/interview"],
            ),
            EffectCandidate(
                family="delay",
                arrangement="lead",
                support_score=0.9,
                evidence_urls=["https://example.com/interview"],
            ),
            EffectCandidate(
                family="reverb",
                arrangement=None,
                support_score=0.8,
                evidence_urls=["https://example.com/studio"],
            ),
        ],
        tone_families={"high_gain": 0.85, "crunch": 0.15},
        evidence_count=2,
        warnings=[],
    )


def test_maps_dominant_amp_family_and_role_effects():
    plan = map_tone_hypothesis(_hypothesis(), arrangements=["lead", "rhythm"])

    lead = plan.tones[0]
    rhythm = plan.tones[1]
    assert lead.arrangement == "lead"
    assert [item.family for item in lead.components] == [
        "amp_high_gain",
        "overdrive",
        "delay",
        "reverb",
    ]
    assert [item.family for item in rhythm.components] == ["amp_high_gain", "reverb"]
    assert plan.safe_for_automatic_injection is False
    assert all(tone.review_required for tone in plan.tones)


def test_ignores_weak_effect_evidence_below_threshold():
    hypothesis = _hypothesis()
    hypothesis.effects.append(
        EffectCandidate(
            family="chorus",
            arrangement="lead",
            support_score=0.1,
            evidence_urls=["https://example.com/forum"],
        )
    )

    plan = map_tone_hypothesis(hypothesis, arrangements=["lead"], minimum_effect_support=0.35)

    assert "chorus" not in [item.family for item in plan.tones[0].components]


def test_shared_effect_applies_to_each_arrangement():
    plan = map_tone_hypothesis(_hypothesis(), arrangements=["lead", "rhythm", "bass"])

    for tone in plan.tones:
        assert "reverb" in [item.family for item in tone.components]


def test_missing_evidence_stays_explicitly_unsafe_and_reviewable():
    hypothesis = ToneRigHypothesis(
        song=SongIdentity(artist="Unknown", title="Unknown"),
        gear=[],
        effects=[],
        tone_families={},
        evidence_count=0,
        warnings=["No tone evidence has been collected yet."],
    )

    plan = map_tone_hypothesis(hypothesis, arrangements=["lead"])

    tone = plan.tones[0]
    assert tone.tone_family == "unknown"
    assert tone.components[0].family == "amp_clean"
    assert tone.review_required is True
    assert plan.safe_for_automatic_injection is False
    assert any("no external research evidence" in warning.lower() for warning in tone.warnings)


def test_requires_arrangement():
    hypothesis = _hypothesis()
    try:
        map_tone_hypothesis(hypothesis, arrangements=[])
    except ValueError as exc:
        assert "at least one arrangement" in str(exc)
    else:
        raise AssertionError("expected ValueError")
