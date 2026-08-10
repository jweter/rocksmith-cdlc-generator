from pathlib import Path

from rocksmith_cdlc_generator.alignment import AlignmentAnchor, AlignmentRegion, AlignmentReport
from rocksmith_cdlc_generator.reconciliation import reconcile_bass_sources
from rocksmith_cdlc_generator.source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTempoEvent,
    SourceTrack,
    SourceTrustClass,
)
from rocksmith_cdlc_generator.transcription import BassTranscription, NoteEvent


def _source() -> ImportedSource:
    return ImportedSource(
        provenance=SourceProvenance(
            source_type="midi",
            source_filename="bass.mid",
            source_sha256="a" * 64,
            importer="test",
            importer_version="1",
        ),
        tempo_events=[SourceTempoEvent(tick=0, time_seconds=0.0, bpm=120.0)],
        tracks=[SourceTrack(
            source_track_index=2,
            name="Bass",
            instrument="bass",
            tuning_midi=[28, 33, 38, 43],
            notes=[
                SourceNoteEvent(start_seconds=0.0, duration_seconds=0.25, midi=40, string_index=0, fret=12, import_confidence=1.0),
                SourceNoteEvent(start_seconds=0.5, duration_seconds=0.25, midi=41, string_index=0, fret=13, import_confidence=1.0),
                SourceNoteEvent(start_seconds=1.0, duration_seconds=0.25, midi=43, string_index=0, fret=15, import_confidence=1.0),
            ],
        )],
    )


def _alignment(confidence: float = 0.95) -> AlignmentReport:
    return AlignmentReport(
        source_path=str(Path("bass.json").resolve()),
        source_sha256="a" * 64,
        track_index=2,
        audio_beat_start_index=0,
        global_offset_seconds=1.0,
        anchor_stride_beats=2,
        matched_beats=3,
        rms_residual_seconds=0.0,
        median_abs_residual_seconds=0.0,
        max_abs_residual_seconds=0.0,
        confidence=confidence,
        anchors=[
            AlignmentAnchor(source_time_seconds=0.0, audio_time_seconds=1.0, source_beat_index=0, audio_beat_index=0, confidence=confidence),
            AlignmentAnchor(source_time_seconds=1.0, audio_time_seconds=2.0, source_beat_index=2, audio_beat_index=2, confidence=confidence),
        ],
        regions=[AlignmentRegion(
            source_start_seconds=0.0,
            source_end_seconds=1.0,
            audio_start_seconds=1.0,
            audio_end_seconds=2.0,
            rms_residual_seconds=0.0,
            max_abs_residual_seconds=0.0,
            confidence=confidence,
        )],
    )


def _audio() -> BassTranscription:
    return BassTranscription(
        engine="test",
        source_path="bass.wav",
        sample_rate_hz=44100,
        notes=[
            NoteEvent(start=1.02, duration=0.25, midi=40, confidence=0.95, pitch_confidence=0.95, timing_confidence=0.95),
            NoteEvent(start=1.51, duration=0.25, midi=42, confidence=0.90, pitch_confidence=0.90, timing_confidence=0.90),
            NoteEvent(start=2.50, duration=0.25, midi=45, confidence=0.85, pitch_confidence=0.85, timing_confidence=0.85),
        ],
    )


def test_reconciliation_verifies_only_strong_pitch_and_onset_matches() -> None:
    chart, review = reconcile_bass_sources(_source(), _alignment(), _audio())
    verified = next(note for note in chart.notes if note.symbolic_midi == 40)
    assert verified.status == "verified_match"
    assert verified.trust_class == SourceTrustClass.symbolic_verified
    assert verified.review_required is False
    assert verified.string_index == 0
    assert verified.fret == 12
    assert all(item.status != "verified_match" for item in review.disagreements)


def test_pitch_conflict_is_not_promoted() -> None:
    chart, review = reconcile_bass_sources(_source(), _alignment(), _audio())
    conflict = next(note for note in chart.notes if note.symbolic_midi == 41)
    assert conflict.status == "pitch_conflict"
    assert conflict.trust_class == SourceTrustClass.symbolic_unverified
    assert conflict.review_required is True
    assert conflict.audio_midi == 42
    assert any(item.status == "pitch_conflict" for item in review.disagreements)


def test_symbolic_only_and_audio_only_are_reviewed() -> None:
    chart, review = reconcile_bass_sources(_source(), _alignment(), _audio())
    symbolic_only = next(note for note in chart.notes if note.status == "symbolic_only")
    audio_only = next(note for note in chart.notes if note.status == "audio_only")
    assert symbolic_only.symbolic_midi == 43
    assert audio_only.audio_midi == 45
    assert symbolic_only.review_required is True
    assert audio_only.review_required is True
    assert {item.status for item in review.disagreements} >= {"symbolic_only", "audio_only"}


def test_low_alignment_confidence_blocks_verification() -> None:
    chart, _ = reconcile_bass_sources(_source(), _alignment(confidence=0.5), _audio())
    match = next(note for note in chart.notes if note.symbolic_midi == 40)
    assert match.status == "verified_match"
    assert match.trust_class == SourceTrustClass.symbolic_unverified
    assert match.review_required is True


def test_source_sha_must_match_alignment() -> None:
    bad = _alignment().model_copy(update={"source_sha256": "b" * 64})
    try:
        reconcile_bass_sources(_source(), bad, _audio())
    except ValueError as exc:
        assert "SHA-256" in str(exc)
    else:
        raise AssertionError("expected reconciliation to reject mismatched source provenance")
