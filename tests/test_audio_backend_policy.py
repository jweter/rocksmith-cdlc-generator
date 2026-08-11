from rocksmith_cdlc_generator.audio_backend_policy import (
    LiveAuditionBackendEvidence,
    assess_live_audition_backend,
)


def test_backend_policy_fails_closed_when_vendor_state_is_not_preserved() -> None:
    evidence = LiveAuditionBackendEvidence(
        backend_name="PortAudio / Focusrite USB ASIO",
        functional_full_duplex_proven=True,
        low_latency_proven=True,
        vendor_state_preserved=False,
        reconnect_recovery_proven=True,
        requires_state_change_opt_in=True,
    )

    decision = assess_live_audition_backend(evidence)

    assert decision.production_eligible is False
    assert "preserve vendor driver state" in decision.blockers[0]
    assert any("explicit opt-in" in blocker for blocker in decision.blockers)


def test_backend_policy_requires_every_production_property() -> None:
    evidence = LiveAuditionBackendEvidence(
        backend_name="candidate",
        functional_full_duplex_proven=False,
        low_latency_proven=False,
        vendor_state_preserved=True,
        reconnect_recovery_proven=False,
    )

    decision = assess_live_audition_backend(evidence)

    assert decision.production_eligible is False
    assert len(decision.blockers) == 3


def test_backend_policy_accepts_only_fully_proven_non_mutating_backend() -> None:
    evidence = LiveAuditionBackendEvidence(
        backend_name="qualified native backend",
        functional_full_duplex_proven=True,
        low_latency_proven=True,
        vendor_state_preserved=True,
        reconnect_recovery_proven=True,
        requires_state_change_opt_in=False,
    )

    decision = assess_live_audition_backend(evidence)

    assert decision.production_eligible is True
    assert decision.blockers == []
