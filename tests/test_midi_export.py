from __future__ import annotations

import mido

from rocksmith_cdlc_generator.midi_export import write_bass_midi
from rocksmith_cdlc_generator.transcription import BassTranscription, NoteEvent


def _fixture_transcription() -> BassTranscription:
    return BassTranscription(
        engine="test",
        engine_version="1",
        source_path="fixture.wav",
        sample_rate_hz=44100,
        notes=[
            NoteEvent(
                start=0.25,
                duration=0.5,
                midi=40,
                confidence=0.9,
                pitch_confidence=0.95,
                timing_confidence=0.85,
            ),
            NoteEvent(
                start=1.0,
                duration=0.25,
                midi=43,
                confidence=0.8,
                pitch_confidence=0.85,
                timing_confidence=0.75,
            ),
        ],
    )


def test_write_bass_midi_round_trip(tmp_path) -> None:
    destination = tmp_path / "bass.mid"
    write_bass_midi(_fixture_transcription(), destination)

    assert destination.read_bytes().startswith(b"MThd")

    midi_file = mido.MidiFile(destination)
    messages = [message for track in midi_file.tracks for message in track]
    note_ons = [message for message in messages if message.type == "note_on" and message.velocity > 0]
    note_offs = [message for message in messages if message.type == "note_off"]

    assert [message.note for message in note_ons] == [40, 43]
    assert [message.note for message in note_offs] == [40, 43]
    assert midi_file.ticks_per_beat == 480


def test_midi_preserves_approximate_absolute_timing(tmp_path) -> None:
    destination = tmp_path / "bass.mid"
    write_bass_midi(_fixture_transcription(), destination)
    midi_file = mido.MidiFile(destination)

    absolute_seconds = 0.0
    note_on_times: list[float] = []
    tempo = 500_000
    for message in midi_file.tracks[0]:
        absolute_seconds += mido.tick2second(message.time, midi_file.ticks_per_beat, tempo)
        if message.type == "set_tempo":
            tempo = message.tempo
        if message.type == "note_on" and message.velocity > 0:
            note_on_times.append(absolute_seconds)

    assert note_on_times[0] == 0.25
    assert note_on_times[1] == 1.0
