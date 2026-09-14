from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from rocksmith_cdlc_generator import accepted_score_timing
from rocksmith_cdlc_generator.accepted_score_timing import (
    AcceptedScoreTimingMap,
    build_accepted_score_timing_map,
)
from rocksmith_cdlc_generator.alignment import AlignmentAnchor
from rocksmith_cdlc_generator.score_source import ArrangementRole
from rocksmith_cdlc_generator.score_timing_anchors import (
    ScoreTimingAnchor,
    ScoreTimingAnchorReview,
    ScoreTimingRefitPreview,
    _bounded_refit_regions,
)
from rocksmith_cdlc_generator.score_timing_refit_review import acceptance_for
from rocksmith_cdlc_generator.shared_timeline import SharedTimeline


_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64


def _candidate() -> SharedTimeline:
    """One shared-authority identity, reused untouched by every inherited role.

    A one-to-one source/audio mapping is enough to exercise the bounded-interval
    invariant without depending on any real alignment math.
    """
    return SharedTimeline(
        recording_sha256=_SHA_A,
        score_sha256=_SHA_B,
        authority_role=ArrangementRole.bass,
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


def _imported() -> SimpleNamespace:
    # Ten evenly spaced symbolic beats (indices 0-9), one second apart. Beat 1 sits
    # inside the edited region [0, 3]; beat 8 sits inside the untouched far region
    # [6, 9] -- these stand in for notes before/after the edited middle region, and
    # beats 3/6 stand in for the human-anchored notes bounding it.
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


def _preview_from_regions(regions) -> ScoreTimingRefitPreview:
    return ScoreTimingRefitPreview(
        recording_sha256=_SHA_A,
        score_sha256=_SHA_B,
        authority_track_index=0,
        authority_output_sha256=_SHA_C,
        human_anchor_count=4,
        max_abs_adjustment_seconds=max(region.max_abs_adjustment_seconds for region in regions),
        regions=list(regions),
    )


def _materialize(monkeypatch: pytest.MonkeyPatch, tmp_path, *, middle_time: float) -> AcceptedScoreTimingMap:
    """Exercise the real accepted-timing consumer (accepted_score_timing.py), the
    path every Bass/Lead/Rhythm arrangement builder reads score-beat timing from,
    rather than re-deriving regions and asserting on the test's own objects.
    """
    candidate = _candidate()
    regions = _bounded_refit_regions(candidate, _imported(), _review(middle_time=middle_time))
    acceptance = acceptance_for(candidate, _preview_from_regions(regions))

    monkeypatch.setattr(accepted_score_timing, "score_mapping_transaction", lambda _project: nullcontext())
    monkeypatch.setattr(accepted_score_timing, "load_current_score_timing_refit_acceptance", lambda _project: acceptance)
    monkeypatch.setattr(accepted_score_timing, "_authority_source", lambda _project, _candidate: _imported())

    return build_accepted_score_timing_map(tmp_path)


def test_editing_interior_anchor_is_isolated_through_the_real_accepted_timing_consumer(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Same edit as above, but proven through ``build_accepted_score_timing_map()`` --
    the actual note-timing consumer every arrangement builder reads -- rather than the
    test's own recomputed region objects, closing the P2 gap that the bounded-region
    fixture alone did not exercise a real note/arrangement consumer.
    """
    before = _materialize(monkeypatch, tmp_path, middle_time=3.0)
    after = _materialize(monkeypatch, tmp_path, middle_time=3.6)

    def point(map_: AcceptedScoreTimingMap, beat_index: int):
        return next(p for p in map_.points if p.source_beat_index == beat_index)

    # The note inside the edited region (beat 1) moves to a materialized reviewed time.
    assert point(after, 1).reviewed_time_seconds != point(before, 1).reviewed_time_seconds
    assert point(after, 1).review_origin == "bounded_refit"

    # The note in the untouched far region (beat 8) is materialized identically either
    # way -- the bounded-recalculation invariant survives the real consumer path, not
    # just the test's own region objects.
    assert point(after, 8) == point(before, 8)
    assert point(before, 8).review_origin == "bounded_refit"

    # The edited human anchor itself (beat 3) materializes the new reviewed time.
    assert point(before, 3).reviewed_time_seconds == 3.0
    assert point(after, 3).reviewed_time_seconds == 3.6
    assert point(after, 3).review_origin == "human_anchor"

    # AcceptedScoreTimingMap carries no per-role field: it is one identity-keyed map
    # (recording/score/authority hashes only), so every one of the candidate's
    # inherited roles -- Bass, Lead, and Rhythm -- reads this same materialized clock
    # rather than a role-specific variant that could silently diverge.
    assert "role" not in AcceptedScoreTimingMap.model_fields
    assert "arrangement" not in AcceptedScoreTimingMap.model_fields
    assert _candidate().inherited_roles == [
        ArrangementRole.bass,
        ArrangementRole.lead,
        ArrangementRole.rhythm,
    ]
