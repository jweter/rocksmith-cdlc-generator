from __future__ import annotations

from pathlib import Path

import mido

from .transcription import BassTranscription

DEFAULT_TICKS_PER_BEAT = 480
DEFAULT_TEMPO_US_PER_BEAT = 500_000  # 120 BPM
BASS_MIDI_CHANNEL = 0
BASS_PROGRAM = 33  # General MIDI Electric Bass (finger), zero-based program number.


def _seconds_to_ticks(seconds: float, *, tempo: int, ticks_per_beat: int) -> int:
    return max(0, round(mido.second2tick(seconds, ticks_per_beat, tempo)))


def write_bass_midi(
    transcription: BassTranscription,
    destination: Path,
    *,
    tempo_us_per_beat: int = DEFAULT_TEMPO_US_PER_BEAT,
    ticks_per_beat: int = DEFAULT_TICKS_PER_BEAT,
) -> None:
    """Write a standard MIDI file preserving transcription note times and durations.

    This MIDI is an intermediate symbolic artifact, not the final Rocksmith chart.  Absolute
    note times from the transcription are converted into MIDI delta ticks at a fixed tempo.
    A later beat-aware export can replace the fixed tempo with the project's actual tempo map.
    """
    if tempo_us_per_beat <= 0:
        raise ValueError("tempo_us_per_beat must be positive")
    if ticks_per_beat <= 0:
        raise ValueError("ticks_per_beat must be positive")

    destination.parent.mkdir(parents=True, exist_ok=True)

    midi_file = mido.MidiFile(type=0, ticks_per_beat=ticks_per_beat)
    track = mido.MidiTrack()
    midi_file.tracks.append(track)
    track.append(mido.MetaMessage("track_name", name="Bass Transcription", time=0))
    track.append(mido.MetaMessage("set_tempo", tempo=tempo_us_per_beat, time=0))
    track.append(
        mido.Message(
            "program_change",
            channel=BASS_MIDI_CHANNEL,
            program=BASS_PROGRAM,
            time=0,
        )
    )

    events: list[tuple[int, int, mido.Message]] = []
    for note in transcription.notes:
        start_tick = _seconds_to_ticks(
            note.start, tempo=tempo_us_per_beat, ticks_per_beat=ticks_per_beat
        )
        end_tick = _seconds_to_ticks(
            note.end, tempo=tempo_us_per_beat, ticks_per_beat=ticks_per_beat
        )
        end_tick = max(start_tick + 1, end_tick)
        velocity = max(1, min(127, round(45 + 82 * note.confidence)))

        # Sort priority keeps note_off before note_on when two events share a tick.
        events.append(
            (
                start_tick,
                1,
                mido.Message(
                    "note_on",
                    note=note.midi,
                    velocity=velocity,
                    channel=BASS_MIDI_CHANNEL,
                    time=0,
                ),
            )
        )
        events.append(
            (
                end_tick,
                0,
                mido.Message(
                    "note_off",
                    note=note.midi,
                    velocity=0,
                    channel=BASS_MIDI_CHANNEL,
                    time=0,
                ),
            )
        )

    previous_tick = 0
    for absolute_tick, _, message in sorted(events, key=lambda item: (item[0], item[1])):
        message.time = absolute_tick - previous_tick
        track.append(message)
        previous_tick = absolute_tick

    track.append(mido.MetaMessage("end_of_track", time=0))
    midi_file.save(destination)
