from pathlib import Path
import json
import wave

from rocksmith_cdlc_generator.alignment import AlignmentAnchor, AlignmentRegion, AlignmentReport
from rocksmith_cdlc_generator.reconciliation import (
    CURRENT_RECONCILIATION_ALGORITHM_VERSION,
    ReconciledBassChart,
    reconcile_bass_sources,
    reconciled_bass_chart_is_current,
    is_verified_bass_stem_transcription,
)
from rocksmith_cdlc_generator.source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTempoEvent,
    SourceTrack,
    SourceTrustClass,
)
from rocksmith_cdlc_generator.transcription import BassTranscription, NoteEvent
from rocksmith_cdlc_generator.hashing import sha256_file


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
    chart, review = reconcile_bass_sources(_source(), _alignment(), _audio(), verified_stem_provenance=True)
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


def test_recording_boundary_omits_trailing_score_notes_and_audio_evidence() -> None:
    chart, review = reconcile_bass_sources(
        _source(),
        _alignment(),
        _audio(),
        recording_duration_seconds=1.80,
    )

    assert chart.notes
    assert all(note.start_seconds < 1.80 for note in chart.notes)
    assert all(note.start_seconds + note.duration_seconds <= 1.80 + 1e-9 for note in chart.notes)
    assert review.omitted_trailing_symbolic_count == 1
    assert review.first_omitted_projected_time_seconds == 2.0
    assert all(item.audio_start_seconds != 2.50 for item in review.disagreements)


def _identity_alignment(confidence: float = 0.95) -> AlignmentReport:
    return AlignmentReport(
        source_path=str(Path("bass.json").resolve()),
        source_sha256="a" * 64,
        track_index=2,
        audio_beat_start_index=0,
        global_offset_seconds=0.0,
        anchor_stride_beats=2,
        matched_beats=2,
        rms_residual_seconds=0.0,
        median_abs_residual_seconds=0.0,
        max_abs_residual_seconds=0.0,
        confidence=confidence,
        anchors=[
            AlignmentAnchor(source_time_seconds=0.0, audio_time_seconds=0.0, source_beat_index=0, audio_beat_index=0, confidence=confidence),
            AlignmentAnchor(source_time_seconds=10.0, audio_time_seconds=10.0, source_beat_index=2, audio_beat_index=2, confidence=confidence),
        ],
        regions=[AlignmentRegion(
            source_start_seconds=0.0,
            source_end_seconds=10.0,
            audio_start_seconds=0.0,
            audio_end_seconds=10.0,
            rms_residual_seconds=0.0,
            max_abs_residual_seconds=0.0,
            confidence=confidence,
        )],
    )


def _single_note_source(start: float, duration: float, midi: int = 40) -> ImportedSource:
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
                SourceNoteEvent(start_seconds=start, duration_seconds=duration, midi=midi, string_index=0, fret=12, import_confidence=1.0),
            ],
        )],
    )


def test_recording_boundary_rejects_audio_evidence_outside_boundary() -> None:
    audio = BassTranscription(
        engine="test",
        source_path="bass.wav",
        sample_rate_hz=44100,
        notes=[
            NoteEvent(start=1.52, duration=0.05, midi=40, confidence=0.95, pitch_confidence=0.95, timing_confidence=0.95),
        ],
    )
    chart, review = reconcile_bass_sources(
        _single_note_source(start=1.50, duration=0.01, midi=40),
        _identity_alignment(),
        audio,
        recording_duration_seconds=1.51,
    )

    assert len(chart.notes) == 1
    note = chart.notes[0]
    assert note.status == "symbolic_only"
    assert note.trust_class == SourceTrustClass.symbolic_unverified
    assert note.review_required is True
    assert all(item.status == "symbolic_only" for item in review.disagreements)


def test_recording_boundary_clip_is_not_reexpanded_past_boundary() -> None:
    audio = BassTranscription(engine="test", source_path="bass.wav", sample_rate_hz=44100, notes=[])
    chart, _ = reconcile_bass_sources(
        _single_note_source(start=1.50, duration=0.01, midi=40),
        _identity_alignment(),
        audio,
        recording_duration_seconds=1.5005,
    )

    assert len(chart.notes) == 1
    note = chart.notes[0]
    assert note.start_seconds + note.duration_seconds <= 1.5005 + 1e-9


def test_reconciliation_currentness_rejects_pre_version_artifacts(tmp_path: Path) -> None:
    chart, _ = reconcile_bass_sources(_source(), _alignment(), _audio())
    current_path = tmp_path / "current.json"
    current_path.write_text(chart.model_dump_json(indent=2), encoding="utf-8")
    assert reconciled_bass_chart_is_current(current_path)
    assert chart.reconciliation_algorithm_version == CURRENT_RECONCILIATION_ALGORITHM_VERSION

    legacy_payload = chart.model_dump(mode="json")
    legacy_payload.pop("reconciliation_algorithm_version")
    legacy_path = tmp_path / "legacy.json"
    import json

    legacy_path.write_text(json.dumps(legacy_payload, indent=2), encoding="utf-8")
    assert not reconciled_bass_chart_is_current(legacy_path)


def test_full_mix_cannot_promote_even_perfect_agreement() -> None:
    chart, _ = reconcile_bass_sources(_source(), _alignment(), _audio())
    matched = next(item for item in chart.notes if item.symbolic_midi == 40)
    assert matched.status == "verified_match"  # observation, not trusted promotion
    assert matched.trust_class == SourceTrustClass.symbolic_unverified
    assert matched.review_required
    assert chart.audio_evidence_provenance == "unqualified"


def test_independent_pitch_and_timing_confidence_are_required() -> None:
    for damaged_field in ("pitch_confidence", "timing_confidence"):
        audio = _audio()
        audio.notes[0] = audio.notes[0].model_copy(update={damaged_field: 0.15})
        chart, _ = reconcile_bass_sources(
            _source(), _alignment(), audio, verified_stem_provenance=True
        )
        matched = next(item for item in chart.notes if item.symbolic_midi == 40)
        assert matched.status == "verified_match"
        assert matched.trust_class == SourceTrustClass.symbolic_unverified
        assert matched.review_required


def test_stem_provenance_must_match_transcription_source_and_original(tmp_path: Path) -> None:
    project = tmp_path / "song"
    (project / "audio").mkdir(parents=True)
    (project / "stems").mkdir()
    original = project / "audio" / "normalized.wav"
    stem = project / "stems" / "bass.wav"
    for path, values in ((original, bytes((0, 0)) * 256), (stem, bytes((1, 0)) * 256)):
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(44100)
            output.writeframes(values)
    receipt = project / "stems" / "bass.json"
    receipt.write_text(json.dumps({
        "schema_version": 1,
        "instrument": "bass",
        "source_sha256": sha256_file(original),
        "output_sha256": sha256_file(stem),
        "engine": "fixture",
        "model": "fixture",
    }), encoding="utf-8")
    good = _audio().model_copy(update={"source_path": "stems/bass.wav", "source_sha256": sha256_file(stem)})
    assert is_verified_bass_stem_transcription(project, good)
    assert not is_verified_bass_stem_transcription(
        project, good.model_copy(update={"source_sha256": None})
    )
    assert not is_verified_bass_stem_transcription(
        project, good.model_copy(update={"source_path": "audio/normalized.wav"})
    )
    with wave.open(str(stem), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(44100)
        output.writeframes(bytes((0, 0)) * 257)
    assert not is_verified_bass_stem_transcription(project, good)
    # Replacing a stem and its receipt must not silently authenticate notes
    # that were transcribed from the old bytes at the same filename.
    receipt_data = json.loads(receipt.read_text(encoding="utf-8"))
    receipt_data["output_sha256"] = sha256_file(stem)
    receipt.write_text(json.dumps(receipt_data), encoding="utf-8")
    assert not is_verified_bass_stem_transcription(project, good)


def test_reconciled_v2_artifact_stale_after_stronger_evidence_gates(tmp_path: Path) -> None:
    chart, _ = reconcile_bass_sources(_source(), _alignment(), _audio())
    legacy = chart.model_dump(mode="json")
    legacy["reconciliation_algorithm_version"] = 2
    path = tmp_path / "v2.json"
    path.write_text(json.dumps(legacy), encoding="utf-8")
    assert not reconciled_bass_chart_is_current(path)


def test_matching_hash_is_not_enough_if_stem_pcm_clock_differs(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "audio").mkdir(parents=True)
    (project / "stems").mkdir()
    master = project / "audio" / "normalized.wav"
    stem = project / "stems" / "bass.wav"
    for path, rate in ((master, 44100), (stem, 48000)):
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(rate)
            output.writeframes(bytes((0, 0)) * 256)
    (project / "stems" / "bass.json").write_text(json.dumps({
        "schema_version": 1, "instrument": "bass",
        "source_sha256": sha256_file(master),
        "output_sha256": sha256_file(stem),
    }), encoding="utf-8")
    audio = _audio().model_copy(update={"source_path": str(stem), "source_sha256": sha256_file(stem)})
    assert not is_verified_bass_stem_transcription(project, audio)
