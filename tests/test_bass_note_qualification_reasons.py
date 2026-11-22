"""Machine-readable reasons for every Bass reconciliation decision."""
from __future__ import annotations

import json
from pathlib import Path

from rocksmith_cdlc_generator.alignment import (
    AlignmentAnchor, AlignmentRegion, AlignmentReport,
)
from rocksmith_cdlc_generator.reconciliation import (
    _note_qualification, ReconciledBassChart, reconcile_bass_sources,
    reconciled_bass_chart_is_current, CURRENT_RECONCILIATION_ALGORITHM_VERSION,
)
from rocksmith_cdlc_generator.source_import import (
    ImportedSource, SourceNoteEvent, SourceProvenance, SourceTempoEvent,
    SourceTrack, SourceTrustClass,
)
from rocksmith_cdlc_generator.transcription import BassTranscription, NoteEvent


def _note(**overrides):
    args = dict(start=1.02, duration=.2, midi=40, confidence=.95,
                pitch_confidence=.95, timing_confidence=.95,
                review_required=False)
    args.update(overrides)
    return NoteEvent(**args)


def _details(audio=None, **overrides):
    args = {
        "verified_stem": True, "onset_delta": .02,
        "audio_note": audio or _note(), "region_confidence": .95,
        "verified_onset_tolerance_seconds": .08,
        "minimum_audio_confidence": .70,
        "minimum_pitch_confidence": .60,
        "minimum_timing_confidence": .75,
        "minimum_alignment_confidence": .70,
    }
    args.update(overrides)
    return _note_qualification(**args)


def test_all_gate_observations_and_thresholds_are_explicit():
    reasons, measured, threshold = _details()
    assert reasons == ["QUALIFIED"]
    assert measured["verified_stem_provenance"] is True
    assert measured["onset_delta_seconds"] == .02
    assert measured["audio_confidence"] == .95
    assert measured["pitch_confidence"] == .95
    assert threshold["minimum_audio_confidence"] == .70
    assert threshold["minimum_pitch_confidence"] == .60
    assert threshold["minimum_timing_confidence"] == .75
    assert threshold["minimum_alignment_confidence"] == .70
    assert threshold["maximum_verified_onset_delta_seconds"] == .08


def test_every_independent_reason_is_reported_in_stable_order():
    notes = _note(confidence=.3, pitch_confidence=.2,
                  timing_confidence=.2, review_required=True)
    reasons, measured, threshold = _details(
        notes, verified_stem=False, onset_delta=.14, region_confidence=.1,
    )
    assert reasons == [
        "UNVERIFIED_STEM", "ONSET_OUTSIDE_VERIFIED_TOLERANCE",
        "LOW_AUDIO_CONFIDENCE", "LOW_PITCH_CONFIDENCE",
        "LOW_TIMING_CONFIDENCE", "LOW_ALIGNMENT_CONFIDENCE",
        "AUDIO_REVIEW_REQUIRED",
    ]
    assert measured["audio_review_required"] is True


def test_threshold_equality_is_qualified_and_below_is_not():
    audio = _note(confidence=.7, pitch_confidence=.6, timing_confidence=.75)
    assert _details(audio, onset_delta=.08, region_confidence=.7)[0] == ["QUALIFIED"]
    assert _details(audio.model_copy(update={"pitch_confidence": .5999}))[0] == [
        "LOW_PITCH_CONFIDENCE"
    ]


def _source() -> ImportedSource:
    return ImportedSource(
        provenance=SourceProvenance(
            source_type="midi", source_filename="bass.mid",
            source_sha256="a" * 64, importer="test", importer_version="1",
        ),
        tempo_events=[SourceTempoEvent(tick=0, time_seconds=0, bpm=120)],
        tracks=[SourceTrack(
            source_track_index=0, name="Bass", instrument="bass",
            tuning_midi=[28, 33, 38, 43],
            notes=[
                SourceNoteEvent(start_seconds=1.0, duration_seconds=.2,
                                midi=40, string_index=0, fret=12, import_confidence=1.0),
                SourceNoteEvent(start_seconds=2.0, duration_seconds=.2,
                                midi=42, string_index=0, fret=14, import_confidence=1.0),
            ],
        )],
    )


def _alignment() -> AlignmentReport:
    anchors = [
        AlignmentAnchor(
            source_time_seconds=t, audio_time_seconds=t,
            source_beat_index=i, audio_beat_index=i, confidence=.96,
        )
        for i, t in enumerate((0., 3.))
    ]
    return AlignmentReport(
        source_path="bass.mid", source_sha256="a" * 64, track_index=0,
        audio_beat_start_index=0, global_offset_seconds=0,
        anchor_stride_beats=1, matched_beats=2,
        rms_residual_seconds=0, median_abs_residual_seconds=0,
        max_abs_residual_seconds=0, confidence=.96,
        anchors=anchors,
        regions=[AlignmentRegion(
            source_start_seconds=0, source_end_seconds=3,
            audio_start_seconds=0, audio_end_seconds=3,
            rms_residual_seconds=0, max_abs_residual_seconds=0,
            confidence=.96,
        )],
    )


def _audio() -> BassTranscription:
    return BassTranscription(
        engine="synthetic-test", source_path="bass.wav", sample_rate_hz=44100,
        notes=[_note(), _note(start=2.02, midi=43),
               _note(start=2.72, midi=45)],
    )


def test_note_review_reasons_cover_pitch_conflict_unmatched_and_unverified():
    chart, _review = reconcile_bass_sources(
        _source(), _alignment(), _audio(), verified_stem_provenance=False
    )
    matched = next(n for n in chart.notes if n.status == "verified_match")
    conflict = next(n for n in chart.notes if n.status == "pitch_conflict")
    extra = next(n for n in chart.notes if n.status == "audio_only")
    assert matched.qualification_reasons == ["UNVERIFIED_STEM"]
    assert matched.trust_class == SourceTrustClass.symbolic_unverified
    assert matched.review_required
    assert conflict.qualification_reasons == ["PITCH_CONFLICT"]
    assert conflict.qualification_observations["expected_symbolic_midi"] == 42
    assert conflict.qualification_observations["observed_audio_midi"] == 43
    assert extra.qualification_reasons == ["NO_SYMBOLIC_MATCH"]
    assert extra.review_required


def test_verified_match_has_explicit_acceptance_proof_not_only_a_label():
    chart, _review = reconcile_bass_sources(
        _source(), _alignment(), _audio(), verified_stem_provenance=True
    )
    matched = next(n for n in chart.notes if n.status == "verified_match")
    assert matched.qualification_reasons == ["QUALIFIED"]
    assert matched.qualification_thresholds["minimum_pitch_confidence"] == .6
    assert matched.trust_class == SourceTrustClass.symbolic_verified
    assert matched.review_required is False


def test_unmatched_symbolic_event_carries_no_audio_reason():
    audio = _audio().model_copy(update={"notes": []})
    chart, _review = reconcile_bass_sources(_source(), _alignment(), audio)
    assert all(n.qualification_reasons == ["NO_AUDIO_ONSET"] for n in chart.notes)
    assert all(n.review_required for n in chart.notes)


def test_stored_v5_reconciliation_is_stale_without_per_event_proof(tmp_path: Path):
    chart, _review = reconcile_bass_sources(_source(), _alignment(), _audio())
    current = tmp_path / "new.json"
    current.write_text(chart.model_dump_json(indent=2), encoding="utf-8")
    assert reconciled_bass_chart_is_current(current)
    old = chart.model_dump(mode="json")
    old["reconciliation_algorithm_version"] = 5
    path = tmp_path / "old.json"
    path.write_text(json.dumps(old), encoding="utf-8")
    assert not reconciled_bass_chart_is_current(path)


def test_version_bump_without_explicit_per_note_evidence_is_not_current(tmp_path: Path):
    chart, _review = reconcile_bass_sources(_source(), _alignment(), _audio())
    payload = chart.model_dump(mode="json")
    assert CURRENT_RECONCILIATION_ALGORITHM_VERSION == 7
    assert payload["reconciliation_algorithm_version"] == CURRENT_RECONCILIATION_ALGORITHM_VERSION
    payload["notes"][0].pop("qualification_reasons")
    path = tmp_path / "missing-evidence.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert not reconciled_bass_chart_is_current(path)
    payload["notes"][0]["qualification_reasons"] = ["UNVERIFIED_STEM"]
    payload["notes"][0].pop("qualification_thresholds")
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert not reconciled_bass_chart_is_current(path)
