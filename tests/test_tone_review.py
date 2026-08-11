from rocksmith_cdlc_generator.rocksmith_tone_mapping import RocksmithTonePlan, RocksmithToneSuggestion, ToneComponentSuggestion
from rocksmith_cdlc_generator.tone_catalog import BoundRocksmithTonePlan, BoundRocksmithTone, BoundToneComponent
from rocksmith_cdlc_generator.tone_review import (
    approve_component,
    approve_tone,
    create_tone_review,
    verify_review_matches_plan,
)


def _plan() -> BoundRocksmithTonePlan:
    return BoundRocksmithTonePlan(
        artist="Example Artist",
        title="Example Song",
        catalog_sha256="a" * 64,
        tones=[
            BoundRocksmithTone(
                arrangement="lead",
                label="Lead Base",
                components=[
                    BoundToneComponent(
                        family="amp_high_gain",
                        device_key="amp_key",
                        device_name="Example Amp",
                        device_type="Amp",
                        slot="Amp",
                        knob_values={"Gain": 0.5},
                        confidence=0.8,
                        reason="test",
                    ),
                    BoundToneComponent(
                        family="delay",
                        device_key="delay_key",
                        device_name="Example Delay",
                        device_type="Rack",
                        slot="Rack1",
                        knob_values={"Mix": 0.25},
                        confidence=0.7,
                        reason="test",
                    ),
                ],
            )
        ],
    )


def test_review_starts_pending_and_not_injectable():
    review = create_tone_review(_plan())
    assert review.ready_for_injection is False
    assert review.tones[0].decision == "pending"
    assert all(item.decision == "pending" for item in review.tones[0].components)


def test_full_approval_is_required_for_injection():
    review = create_tone_review(_plan())
    review = approve_component(review, arrangement="lead", family="amp_high_gain")
    review = approve_component(
        review,
        arrangement="lead",
        family="delay",
        knob_values={"Mix": 0.4},
        reviewer_note="Auditioned closer to source.",
    )
    assert review.ready_for_injection is False
    review = approve_tone(review, arrangement="lead")
    assert review.ready_for_injection is True
    assert review.tones[0].components[1].knob_values == {"Mix": 0.4}


def test_unresolved_component_cannot_be_approved():
    plan = _plan()
    plan.tones[0].components[1].device_key = None
    plan.tones[0].components[1].slot = None
    review = create_tone_review(plan)
    try:
        approve_component(review, arrangement="lead", family="delay")
    except ValueError as exc:
        assert "unresolved" in str(exc)
    else:
        raise AssertionError("expected unresolved component approval to fail")


def test_review_is_bound_to_exact_plan_and_catalog():
    plan = _plan()
    review = create_tone_review(plan)
    verify_review_matches_plan(review, plan)

    changed = plan.model_copy(deep=True)
    changed.tones[0].components[0].knob_values["Gain"] = 0.9
    try:
        verify_review_matches_plan(review, changed)
    except ValueError as exc:
        assert "different bound tone plan" in str(exc)
    else:
        raise AssertionError("expected changed plan to invalidate review")

    changed_catalog = plan.model_copy(deep=True)
    changed_catalog.catalog_sha256 = "b" * 64
    try:
        verify_review_matches_plan(review, changed_catalog)
    except ValueError as exc:
        assert "catalog SHA-256" in str(exc)
    else:
        raise AssertionError("expected catalog mismatch to invalidate review")
