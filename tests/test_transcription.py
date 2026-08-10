from pathlib import Path

import pytest

from rocksmith_cdlc_generator.transcription import (
    BassTranscription,
    NoteEvent,
    read_transcription,
    write_notes_csv,
    write_transcription,
)
from rocksmith_cdlc_generator.transcription_quality import review_bass_transcription


def _fixture() -> BassTranscription:
    return BassTranscription(
        engine="test",
        engine_version="1",
        source_path="bass.wav",
        sample_rate_hz=44100,
        notes=[
            NoteEvent(
                start=0.25,
                duration=0.5,
                midi=40,
                confidence=0.9,
                pitch_confidence=0.95,
                timing_confidence=0.8,
            ),
            NoteEvent(
                start=0.85,
                duration=0.5,
                midi=43,
                confidence=0.7,
                pitch_confidence=0.8,
                timing_confidence=0.6,
            ),
        ],
    )


def test_transcription_round_trip_and_csv(tmp_path: Path) -> None:
    transcription = _fixture()
    json_path = tmp_path / "bass.json"
    csv_path = tmp_path / "bass.csv"

    write_transcription(transcription, json_path)
    write_notes_csv(transcription, csv_path)

    loaded = read_transcription(json_path)
    assert [note.midi for note in loaded.notes] == [40, 43]
    assert "pitch_confidence" in csv_path.read_text(encoding="utf-8")


def test_transcription_rejects_out_of_order_notes() -> None:
    with pytest.raises(ValueError, match="ordered by start time"):
        BassTranscription(
            engine="test",
            source_path="bass.wav",
            sample_rate_hz=44100,
            notes=[
                NoteEvent(
                    start=1.0,
                    duration=0.2,
                    midi=40,
                    confidence=0.9,
                    pitch_confidence=0.9,
                    timing_confidence=0.9,
                ),
                NoteEvent(
                    start=0.5,
                    duration=0.2,
                    midi=41,
                    confidence=0.9,
                    pitch_confidence=0.9,
                    timing_confidence=0.9,
                ),
            ],
        )


def test_review_flags_low_confidence_notes() -> None:
    transcription = _fixture()
    transcription.notes[0].review_required = True
    review = review_bass_transcription(transcription)
    assert review.status == "WARNING"
    assert review.review_required_count == 1
