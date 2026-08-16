from __future__ import annotations

from statistics import median

from rocksmith_cdlc_generator.librosa_transcription import (
    LibrosaPyinBassTranscriber,
    _analysis_windows,
    _append_chunk_observations,
)
from rocksmith_cdlc_generator.transcription import NoteEvent
from tests.audio_factory import write_synthetic_bass_phrase


def _note(
    start: float,
    duration: float,
    midi: int,
    *,
    confidence: float = 0.9,
    pitch_confidence: float = 0.9,
    timing_confidence: float = 0.9,
    review_required: bool = False,
) -> NoteEvent:
    return NoteEvent(
        start=start,
        duration=duration,
        midi=midi,
        confidence=confidence,
        pitch_confidence=pitch_confidence,
        timing_confidence=timing_confidence,
        review_required=review_required,
    )


def test_analysis_windows_partition_core_without_gaps_or_overlap() -> None:
    windows = _analysis_windows(
        10_000,
        1_000,
        chunk_seconds=3.0,
        overlap_seconds=0.5,
    )

    assert windows == [
        (0, 0, 3000, 3500),
        (2500, 3000, 6000, 6500),
        (5500, 6000, 9000, 9500),
        (8500, 9000, 10000, 10000),
    ]
    assert windows[0][1] == 0
    assert windows[-1][2] == 10_000
    assert all(previous[2] == current[1] for previous, current in zip(windows, windows[1:]))


def test_chunk_continuation_extends_owned_sustain_past_overlap() -> None:
    notes = [_note(44.0, 2.0, 40)]

    _append_chunk_observations(
        notes,
        [_note(0.0, 4.0, 40)],
        context_offset_seconds=44.0,
        core_start_seconds=45.0,
        core_end_seconds=90.0,
        is_last=False,
    )

    assert len(notes) == 1
    assert notes[0].start == 44.0
    assert notes[0].end == 48.0


def test_chunk_continuation_propagates_uncertainty_to_owned_sustain() -> None:
    notes = [_note(44.0, 2.0, 40)]

    _append_chunk_observations(
        notes,
        [
            _note(
                0.0,
                4.0,
                40,
                confidence=0.42,
                pitch_confidence=0.45,
                timing_confidence=0.50,
                review_required=True,
            )
        ],
        context_offset_seconds=44.0,
        core_start_seconds=45.0,
        core_end_seconds=90.0,
        is_last=False,
    )

    assert len(notes) == 1
    stitched = notes[0]
    assert stitched.end == 48.0
    assert stitched.confidence == 0.42
    assert stitched.pitch_confidence == 0.45
    assert stitched.timing_confidence == 0.50
    assert stitched.review_required is True


def test_chunk_continuation_never_improves_existing_uncertainty() -> None:
    notes = [
        _note(
            44.0,
            2.0,
            40,
            confidence=0.40,
            pitch_confidence=0.41,
            timing_confidence=0.42,
            review_required=True,
        )
    ]

    _append_chunk_observations(
        notes,
        [_note(0.0, 4.0, 40)],
        context_offset_seconds=44.0,
        core_start_seconds=45.0,
        core_end_seconds=90.0,
        is_last=False,
    )

    stitched = notes[0]
    assert stitched.confidence == 0.40
    assert stitched.pitch_confidence == 0.41
    assert stitched.timing_confidence == 0.42
    assert stitched.review_required is True


def test_chunk_continuation_does_not_merge_different_pitch() -> None:
    notes = [_note(44.0, 2.0, 40)]

    _append_chunk_observations(
        notes,
        [_note(0.0, 4.0, 41, review_required=True, confidence=0.2)],
        context_offset_seconds=44.0,
        core_start_seconds=45.0,
        core_end_seconds=90.0,
        is_last=False,
    )

    assert len(notes) == 1
    assert notes[0].end == 46.0
    assert notes[0].confidence == 0.9
    assert notes[0].review_required is False


def test_chunk_continuation_can_extend_across_multiple_boundaries() -> None:
    notes = [_note(44.0, 2.0, 40)]

    _append_chunk_observations(
        notes,
        [_note(0.0, 47.0, 40, confidence=0.8)],
        context_offset_seconds=44.0,
        core_start_seconds=45.0,
        core_end_seconds=90.0,
        is_last=False,
    )
    _append_chunk_observations(
        notes,
        [_note(0.0, 6.0, 40, confidence=0.6, review_required=True)],
        context_offset_seconds=89.0,
        core_start_seconds=90.0,
        core_end_seconds=135.0,
        is_last=False,
    )

    assert len(notes) == 1
    assert notes[0].start == 44.0
    assert notes[0].end == 95.0
    assert notes[0].confidence == 0.6
    assert notes[0].review_required is True


def test_librosa_pyin_tracks_synthetic_bass_pitch_and_timing(tmp_path) -> None:
    audio = tmp_path / "synthetic_bass.wav"
    expected = write_synthetic_bass_phrase(audio)

    transcription = LibrosaPyinBassTranscriber().transcribe(audio)
    assert len(transcription.notes) >= len(expected) - 1

    timing_errors: list[float] = []
    pitch_errors: list[int] = []
    for expected_start, _duration, expected_midi in expected:
        candidate = min(
            transcription.notes,
            key=lambda note: abs(note.start - expected_start),
        )
        timing_errors.append(abs(candidate.start - expected_start))
        pitch_errors.append(abs(candidate.midi - expected_midi))

    assert median(timing_errors) < 0.10
    assert max(timing_errors) < 0.18
    assert median(pitch_errors) <= 1
    assert sum(error <= 1 for error in pitch_errors) / len(pitch_errors) >= 0.75


def test_chunked_transcription_reports_progress_and_assigns_each_onset_once(tmp_path) -> None:
    audio = tmp_path / "chunked_bass.wav"
    write_synthetic_bass_phrase(audio)
    progress: list[tuple[float, str]] = []

    transcription = LibrosaPyinBassTranscriber(
        chunk_seconds=0.75,
        overlap_seconds=0.20,
    ).transcribe(audio, progress_callback=lambda percent, message: progress.append((percent, message)))

    starts = [round(note.start, 6) for note in transcription.notes]
    assert starts == sorted(starts)
    assert len(starts) == len(set(starts))
    chunk_messages = [message for _percent, message in progress if message.startswith("Pitch analysis chunk")]
    assert len(chunk_messages) > 1
    assert progress[0][1] == "Loading normalized audio"
    assert progress[-1][0] == 100.0
    assert "Bass transcription complete" in progress[-1][1]
