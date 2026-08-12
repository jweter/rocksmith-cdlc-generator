from __future__ import annotations

from pydantic import BaseModel, Field

from .song_preview import SongPreviewSnapshot
from .source_import import SourceTempoEvent, SourceTimeSignatureEvent


class PreviewMusicalContext(BaseModel):
    """Read-only musical ruler state at one playhead position."""

    schema_version: int = 1
    position_seconds: float = Field(ge=0)
    previous_beat_index: int | None = Field(default=None, ge=0)
    previous_beat_seconds: float | None = Field(default=None, ge=0)
    next_beat_index: int | None = Field(default=None, ge=0)
    next_beat_seconds: float | None = Field(default=None, ge=0)
    beat_phase: float | None = Field(default=None, ge=0, le=1)
    local_bpm: float | None = Field(default=None, gt=0)
    tempo_event: SourceTempoEvent | None = None
    time_signature: SourceTimeSignatureEvent | None = None


def _validate_monotonic(values: list[float], *, label: str) -> None:
    if any(right <= left for left, right in zip(values, values[1:])):
        raise ValueError(f"{label} must be strictly increasing")


def build_preview_musical_context(
    snapshot: SongPreviewSnapshot,
    position_seconds: float,
) -> PreviewMusicalContext:
    """Return beat/tempo/time-signature context without modifying trusted timing.

    The local BPM is derived from the bracketing canonical beats when both exist.
    Tempo and time-signature events are informational source metadata: the latest event
    at or before the playhead is returned, with copied values suitable for GUI display.
    """

    if position_seconds < 0:
        raise ValueError("Preview position must be non-negative")

    beats = list(snapshot.beat_times_seconds)
    _validate_monotonic(beats, label="Preview beat grid")

    tempo_times = [event.time_seconds for event in snapshot.tempo_events]
    signature_times = [event.time_seconds for event in snapshot.time_signatures]
    if tempo_times:
        _validate_monotonic(tempo_times, label="Preview tempo events")
    if signature_times:
        _validate_monotonic(signature_times, label="Preview time signatures")

    previous_index = next(
        (index for index in range(len(beats) - 1, -1, -1) if beats[index] <= position_seconds),
        None,
    )
    next_index = next(
        (index for index, beat in enumerate(beats) if beat > position_seconds),
        None,
    )

    previous_beat = beats[previous_index] if previous_index is not None else None
    next_beat = beats[next_index] if next_index is not None else None

    beat_phase: float | None = None
    local_bpm: float | None = None
    if previous_beat is not None and next_beat is not None:
        interval = next_beat - previous_beat
        beat_phase = (position_seconds - previous_beat) / interval
        local_bpm = 60.0 / interval

    tempo_event = next(
        (
            event.model_copy(deep=True)
            for event in reversed(snapshot.tempo_events)
            if event.time_seconds <= position_seconds
        ),
        None,
    )
    time_signature = next(
        (
            event.model_copy(deep=True)
            for event in reversed(snapshot.time_signatures)
            if event.time_seconds <= position_seconds
        ),
        None,
    )

    return PreviewMusicalContext(
        position_seconds=position_seconds,
        previous_beat_index=previous_index,
        previous_beat_seconds=previous_beat,
        next_beat_index=next_index,
        next_beat_seconds=next_beat,
        beat_phase=beat_phase,
        local_bpm=local_bpm,
        tempo_event=tempo_event,
        time_signature=time_signature,
    )
