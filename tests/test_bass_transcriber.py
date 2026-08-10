from __future__ import annotations

from statistics import median

from rocksmith_cdlc_generator.librosa_transcription import LibrosaPyinBassTranscriber
from tests.audio_factory import write_synthetic_bass_phrase


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
