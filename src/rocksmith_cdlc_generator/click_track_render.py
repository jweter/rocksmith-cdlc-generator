from __future__ import annotations

from array import array
from pathlib import Path
import math
import wave

from .beats import TempoMap

# Synthesis parameters mirror the live-playback click in audio_playback.py's
# ProjectAudioTransport._mix_click, so the rendered practice-audio click sounds the
# same as the desktop app's in-session metronome preview.
_CLICK_DURATION_SECONDS = 0.025
_BEAT_FREQUENCY_HZ = 1200.0
_DOWNBEAT_FREQUENCY_HZ = 1800.0
_BEAT_AMPLITUDE = 9000
_DOWNBEAT_AMPLITUDE = 14000
_SUBDIVISION_AMPLITUDE = 5000

_SUBDIVISIONS_PER_BEAT = {
    None: 1,
    "eighth": 2,
    "sixteenth": 4,
}


def count_in_offset_seconds(tempo_map: TempoMap, count_in_measures: int) -> float:
    """Seconds of count-in rendered before ``tempo_map.beats[0].time`` (which is 0.0).

    ``render_click_track_wav`` shifts its whole output buffer forward by this amount
    so the count-in has room before the chart's own beat 1. That shift is local to the
    rendered WAV: ``tempo_map`` itself (and anything generated from it, such as a
    Rocksmith XML chart) is unaffected and still starts at time 0.0. A caller that
    pairs this WAV with chart output generated from the same ``tempo_map`` — so the
    chart's note/beat timestamps line up with what's actually playing at that point in
    the audio — must add this same offset to the chart's timestamps before pairing
    them; the tempo map and the rendered WAV do not share a clock on their own.
    """

    if count_in_measures < 0:
        raise ValueError("count_in_measures must not be negative")
    if not tempo_map.beats:
        raise ValueError("Tempo map has no beats to render")

    first_beat = tempo_map.beats[0]
    seconds_per_beat = 60.0 / first_beat.bpm * (4.0 / tempo_map.time_signature_denominator)
    count_in_beats = count_in_measures * tempo_map.time_signature_numerator
    return count_in_beats * seconds_per_beat


def _synthesize_click(sample_rate_hz: int, frequency_hz: float, amplitude: int) -> array:
    length = max(1, int(sample_rate_hz * _CLICK_DURATION_SECONDS))
    samples = array("h", [0] * length)
    for frame in range(length):
        phase = frame / sample_rate_hz
        envelope = 1.0 - (frame / length)
        samples[frame] = int(amplitude * envelope * math.sin(2.0 * math.pi * frequency_hz * phase))
    return samples


def _mix_click_at(buffer: array, start_frame: int, click: array) -> None:
    total_frames = len(buffer)
    for offset, sample in enumerate(click):
        frame = start_frame + offset
        if frame < 0 or frame >= total_frames:
            continue
        value = buffer[frame] + sample
        buffer[frame] = max(-32768, min(32767, value))


def render_click_track_wav(
    tempo_map: TempoMap,
    destination: Path,
    *,
    count_in_measures: int = 2,
    subdivision: str | None = None,
    trailing_seconds: float = 1.0,
) -> None:
    """Render a mono 16-bit PCM WAV click track from a deterministic tempo map.

    Every click in this WAV — count-in and chart beats alike — is positioned from
    the same beat-interval arithmetic, so the clicks cannot drift relative to *each
    other* within the file. That guarantee does not extend to an externally
    generated chart: ``tempo_map.beats[0].time`` is always ``0.0`` (see
    deterministic_tempo_map.py), but this render shifts its whole buffer forward so
    the count-in has room before that origin, landing chart beat 1 at
    ``count_in_offset_seconds()`` seconds into the file rather than at 0.0. A caller
    that pairs this WAV with a chart generated from the same ``tempo_map`` must add
    ``count_in_offset_seconds(tempo_map, count_in_measures)`` to the chart's own
    timestamps first, or the two will be offset by exactly that amount.
    """

    if subdivision not in _SUBDIVISIONS_PER_BEAT:
        raise ValueError(f"Unsupported subdivision: {subdivision!r}")

    sample_rate_hz = tempo_map.sample_rate_hz
    beats_per_measure = tempo_map.time_signature_numerator
    subdivisions_per_beat = _SUBDIVISIONS_PER_BEAT[subdivision]

    count_in_seconds = count_in_offset_seconds(tempo_map, count_in_measures)
    first_beat = tempo_map.beats[0]
    seconds_per_beat = 60.0 / first_beat.bpm * (4.0 / tempo_map.time_signature_denominator)
    count_in_beats = count_in_measures * beats_per_measure

    last_beat = tempo_map.beats[-1]
    last_beat_bpm = last_beat.bpm
    last_seconds_per_beat = 60.0 / last_beat_bpm * (4.0 / tempo_map.time_signature_denominator)
    end_seconds = last_beat.time + last_seconds_per_beat + trailing_seconds

    total_seconds = count_in_seconds + end_seconds
    total_frames = int(math.ceil(total_seconds * sample_rate_hz)) + 1
    buffer = array("h", [0] * total_frames)

    beat_click = _synthesize_click(sample_rate_hz, _BEAT_FREQUENCY_HZ, _BEAT_AMPLITUDE)
    downbeat_click = _synthesize_click(sample_rate_hz, _DOWNBEAT_FREQUENCY_HZ, _DOWNBEAT_AMPLITUDE)
    subdivision_click = _synthesize_click(sample_rate_hz, _BEAT_FREQUENCY_HZ, _SUBDIVISION_AMPLITUDE)

    def frame_for(time_seconds: float) -> int:
        return int(round((count_in_seconds + time_seconds) * sample_rate_hz))

    for beat_index in range(count_in_beats, 0, -1):
        time_seconds = -beat_index * seconds_per_beat
        is_downbeat = ((count_in_beats - beat_index) % beats_per_measure) == 0
        click = downbeat_click if is_downbeat else beat_click
        _mix_click_at(buffer, frame_for(time_seconds), click)

    for index, beat in enumerate(tempo_map.beats):
        click = downbeat_click if beat.is_downbeat else beat_click
        _mix_click_at(buffer, frame_for(beat.time), click)

        if subdivisions_per_beat > 1:
            if index + 1 < len(tempo_map.beats):
                next_time = tempo_map.beats[index + 1].time
            else:
                next_time = beat.time + last_seconds_per_beat
            interval = (next_time - beat.time) / subdivisions_per_beat
            for subdivision_index in range(1, subdivisions_per_beat):
                subdivision_time = beat.time + interval * subdivision_index
                _mix_click_at(buffer, frame_for(subdivision_time), subdivision_click)

    destination.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destination), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate_hz)
        handle.writeframes(buffer.tobytes())
