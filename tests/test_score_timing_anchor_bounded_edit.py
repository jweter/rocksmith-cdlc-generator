from __future__ import annotations

from types import SimpleNamespace

from rocksmith_cdlc_generator.alignment import AlignmentAnchor
from rocksmith_cdlc_generator.score_source import ArrangementRole
from rocksmith_cdlc_generator.score_timing_anchors import (
    ScoreTimingAnchor,
    ScoreTimingAnchorReview,
    ScoreTimingRefitPreview,
    _bounded_refit_regions,
)
from rocksmith_cdlc_generator.score_timing_refit_review import (
    acceptance_for,
    require_current_acceptance,
)
from rocksmith_cdlc_generator.shared_timeline import SharedTimeline


_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64


def _candidate() -> SimpleNamespace:
    # A one-to-one source/audio mapping is enough to exercise the bounded-interval
    # invariant without depending on any real alignment math.
    return SimpleNamespace(
        anchors=[
            SimpleNamespace(source_time_seconds=0.0, audio_time_seconds=0.0),
            SimpleNamespace(source_time_seconds=9.0, audio_time_seconds=9.0),
        ]
    )


def _imported() -> SimpleNamespace:
    # Ten evenly spaced symbolic beats (indices 0-9), one second apart.
    return SimpleNamespace(beat_times_seconds=[float(index) for index in range(10)])


def _review(*, middle_time: float) -> ScoreTimingAnchorReview:
    """Four human anchors at source beats 0, 3, 6, 9 -- three bounded regions."""
    return ScoreTimingAnchorReview(
        recording_sha256=_SHA_A,
        score_sha256=_SHA_B,
        authority_track_index=0,
        authority_output_sha256=_SHA_C,
        anchors=[
            ScoreTimingAnchor(
                source_beat_index=0,
                recording_time_seconds=0.0,
                origin="confirmed_candidate",
                candidate_time_seconds=0.0,
            ),
            ScoreTimingAnchor(
                source_beat_index=3,
                recording_time_seconds=middle_time,
                origin="manual_cursor",
                candidate_time_seconds=3.0,
            ),
            ScoreTimingAnchor(
                source_beat_index=6,
                recording_time_seconds=6.0,
                origin="confirmed_candidate",
                candidate_time_seconds=6.0,
            ),
            ScoreTimingAnchor(
                source_beat_index=9,
                recording_time_seconds=9.0,
                origin="confirmed_candidate",
                candidate_time_seconds=9.0,
            ),
        ],
    )


def test_editing_interior_anchor_only_recomputes_its_bounded_regions() -> None:
    """Mirrors EOF's ``eof_recalculate_beats()`` bounded-recalculation semantics
    (docs/eof-timing-edit-anchor-audit.md): editing one interior human anchor must
    leave every anchor and region it does not touch exactly fixed, and re-derive
    only the interval(s) bounded by the edited anchor.
    """
    candidate = _candidate()
    imported = _imported()

    before = _bounded_refit_regions(candidate, imported, _review(middle_time=3.0))
    after = _bounded_refit_regions(candidate, imported, _review(middle_time=3.6))

    assert len(before) == len(after) == 3

    # The far region [beat 6, beat 9] never touches the edited anchor (beat 3) and
    # must remain byte-for-byte identical, including the note it contains (beat 8).
    assert after[2] == before[2]
    before_beat8 = next(p for p in before[2].points if p.source_beat_index == 8)
    after_beat8 = next(p for p in after[2].points if p.source_beat_index == 8)
    assert after_beat8 == before_beat8

    # The two regions bounded by the edited anchor are re-derived...
    assert after[0] != before[0]
    assert after[1] != before[1]
    assert after[0].end_recording_time_seconds == after[1].start_recording_time_seconds == 3.6
    assert before[0].end_recording_time_seconds == before[1].start_recording_time_seconds == 3.0

    # ...yet the anchors bounding the whole edit from the outside (beat 0 and beat 6)
    # keep their own reviewed recording times exactly, both before and after the edit.
    assert before[0].start_recording_time_seconds == after[0].start_recording_time_seconds == 0.0
    assert before[1].end_recording_time_seconds == after[1].end_recording_time_seconds == 6.0

    # A note inside the touched interval (beat 1, inside [0, 3]) moves with the edit.
    before_beat1 = next(p for p in before[0].points if p.source_beat_index == 1)
    after_beat1 = next(p for p in after[0].points if p.source_beat_index == 1)
    assert after_beat1.refit_time_seconds != before_beat1.refit_time_seconds


def _candidate_identity(*, authority_role: ArrangementRole = ArrangementRole.bass) -> SharedTimeline:
    return SharedTimeline(
        recording_sha256=_SHA_A,
        score_sha256=_SHA_B,
        authority_role=authority_role,
        authority_track_index=0,
        authority_output_json="sources/imported/bass.json",
        authority_output_sha256=_SHA_C,
        inherited_roles=[ArrangementRole.bass, ArrangementRole.lead, ArrangementRole.rhythm],
        audio_beat_start_index=0,
        global_offset_seconds=0.0,
        anchor_stride_beats=8,
        matched_beats=2,
        rms_residual_seconds=0.01,
        median_abs_residual_seconds=0.01,
        max_abs_residual_seconds=0.02,
        confidence=0.95,
        anchors=[
            AlignmentAnchor(
                source_time_seconds=0.0,
                audio_time_seconds=0.0,
                source_beat_index=0,
                audio_beat_index=0,
                confidence=0.95,
            ),
            AlignmentAnchor(
                source_time_seconds=9.0,
                audio_time_seconds=9.0,
                source_beat_index=9,
                audio_beat_index=9,
                confidence=0.95,
            ),
        ],
        regions=[],
    )


def _preview_from_regions(regions, *, human_anchor_count: int = 4) -> ScoreTimingRefitPreview:
    return ScoreTimingRefitPreview(
        recording_sha256=_SHA_A,
        score_sha256=_SHA_B,
        authority_track_index=0,
        authority_output_sha256=_SHA_C,
        human_anchor_count=human_anchor_count,
        max_abs_adjustment_seconds=max(region.max_abs_adjustment_seconds for region in regions),
        regions=list(regions),
    )


def test_editing_interior_anchor_invalidates_previously_accepted_refit() -> None:
    """The bounded edit above must invalidate any human acceptance recorded for the
    prior proposal rather than silently keeping it current: downstream timing
    derivatives are rebuilt, not mutated in place (docs/eof-timing-edit-anchor-audit.md
    provenance non-goal). This holds even though the far, untouched region is
    unchanged, because the overall preview -- and therefore its accepted evidence --
    is bound to the exact current human-anchor set.
    """
    candidate = _candidate_identity()
    before = _bounded_refit_regions(_candidate(), _imported(), _review(middle_time=3.0))
    after = _bounded_refit_regions(_candidate(), _imported(), _review(middle_time=3.6))

    accepted = acceptance_for(candidate, _preview_from_regions(before))
    assert require_current_acceptance(accepted, candidate, _preview_from_regions(before)) is accepted

    try:
        require_current_acceptance(accepted, candidate, _preview_from_regions(after))
    except ValueError as error:
        assert "stale" in str(error)
    else:
        raise AssertionError("editing an interior anchor must invalidate the prior acceptance")

    # Bass, Lead, and Rhythm all consume this one shared authority/review identity, so
    # the same invalidation and re-derivation applies to every inherited role at once
    # rather than only to the arrangement that happened to be reviewed.
    assert candidate.inherited_roles == [
        ArrangementRole.bass,
        ArrangementRole.lead,
        ArrangementRole.rhythm,
    ]
