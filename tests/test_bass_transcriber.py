from __future__ import annotations

from statistics import median

from rocksmith_cdlc_generator.librosa_transcription import (
    LibrosaPyinBassTranscriber,
    _analysis_windows,
)
from tests.audio_factory import write_synthetic_bass_phrase


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
