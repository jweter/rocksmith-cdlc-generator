from datetime import datetime, timedelta, timezone

from rocksmith_cdlc_generator.product_reality import (
    ProductRealityObservation,
    ProductRealitySession,
    ProductRealityStageRecord,
)
from rocksmith_cdlc_generator.product_reality_ui import ProductRealityRecorderWindow


def _ready_session(*, score_sha256: str | None) -> ProductRealitySession:
    started = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
    return ProductRealitySession(
        session_id="session-1",
        project_source_sha256="a" * 64,
        recording_duration_seconds=300.0,
        score_sha256=score_sha256,
        score_format="gp5" if score_sha256 else None,
        packaged_build_id="windows-build-123",
        started_at=started,
        stages=[
            ProductRealityStageRecord(
                name="arrangement review / correction",
                counts_as_editing=True,
                started_at=started,
                completed_at=started + timedelta(seconds=60),
                elapsed_seconds=60.0,
            )
        ],
        observations=[
            ProductRealityObservation(
                area="playback responsiveness",
                severity="note",
                text="Playback remained responsive during repeated edits.",
                recorded_at=started + timedelta(seconds=61),
            )
        ],
    )


def test_pass_readiness_uses_current_score_identity_not_session_snapshot() -> None:
    session = _ready_session(score_sha256=None)

    gaps = ProductRealityRecorderWindow.pass_readiness_gaps(
        session,
        current_score_sha256="b" * 64,
        active_stage_running=False,
    )

    assert "registered complete score identity" not in gaps
    assert gaps == ()


def test_pass_readiness_detects_removed_score_even_if_snapshot_was_present() -> None:
    session = _ready_session(score_sha256="b" * 64)

    gaps = ProductRealityRecorderWindow.pass_readiness_gaps(
        session,
        current_score_sha256=None,
        active_stage_running=False,
    )

    assert "registered complete score identity" in gaps


def test_pass_readiness_requires_active_timer_to_stop_before_pass() -> None:
    session = _ready_session(score_sha256="b" * 64)

    gaps = ProductRealityRecorderWindow.pass_readiness_gaps(
        session,
        current_score_sha256="b" * 64,
        active_stage_running=True,
    )

    assert gaps == ("stop the active workflow stage timer",)
