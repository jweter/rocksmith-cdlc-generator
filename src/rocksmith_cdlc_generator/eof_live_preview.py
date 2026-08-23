from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from .song_preview import PreviewArrangement, PreviewNoteEvent


@dataclass(frozen=True)
class LivePreviewWindow:
    start_seconds: float
    end_seconds: float
    playhead_seconds: float

    @property
    def span_seconds(self) -> float:
        return max(self.end_seconds - self.start_seconds, 0.001)


@dataclass(frozen=True)
class HighwayNote:
    note: PreviewNoteEvent
    progress: float
    x_fraction: float
    width_fraction: float


def string_count(arrangement: PreviewArrangement) -> int:
    if arrangement.tuning_midi:
        return len(arrangement.tuning_midi)
    positioned = [note.string_index for note in arrangement.notes if note.string_index is not None]
    if positioned:
        return max(positioned) + 1
    return 4 if arrangement.instrument == "bass" else 6


def live_window(
    *,
    playhead_seconds: float,
    duration_seconds: float,
    look_behind_seconds: float = 1.5,
    look_ahead_seconds: float = 6.0,
) -> LivePreviewWindow:
    duration = max(float(duration_seconds), 0.0)
    playhead = min(max(float(playhead_seconds), 0.0), duration)
    start = max(playhead - max(look_behind_seconds, 0.0), 0.0)
    end = min(playhead + max(look_ahead_seconds, 0.1), duration)
    if end <= start:
        end = min(start + 0.1, max(duration, start + 0.1))
    return LivePreviewWindow(start, end, playhead)


def notes_in_window(arrangement: PreviewArrangement, window: LivePreviewWindow) -> list[PreviewNoteEvent]:
    return [
        note
        for note in arrangement.notes
        if note.end_seconds >= window.start_seconds and note.start_seconds <= window.end_seconds
    ]


def time_fraction(when: float, window: LivePreviewWindow) -> float:
    return min(max((float(when) - window.start_seconds) / window.span_seconds, 0.0), 1.0)


def highway_notes(
    arrangement: PreviewArrangement,
    window: LivePreviewWindow,
) -> list[HighwayNote]:
    """Project upcoming notes into an EOF/Rocksmith-style perspective highway.

    `progress` is 0 at the play line and 1 at the horizon. The square-root easing
    deliberately gives near-future notes more visual separation without changing their
    authoritative timing. It is presentation only.
    """

    ahead_span = max(window.end_seconds - window.playhead_seconds, 0.001)
    result: list[HighwayNote] = []
    for note in arrangement.notes:
        if note.end_seconds < window.playhead_seconds or note.start_seconds > window.end_seconds:
            continue
        raw = min(max((note.start_seconds - window.playhead_seconds) / ahead_span, 0.0), 1.0)
        progress = sqrt(raw)
        x_fraction = (
            (note.string_index + 0.5) / max(string_count(arrangement), 1)
            if note.string_index is not None
            else 0.5
        )
        duration_fraction = min(max(note.duration_seconds / ahead_span, 0.008), 0.25)
        result.append(
            HighwayNote(
                note=note,
                progress=progress,
                x_fraction=x_fraction,
                width_fraction=duration_fraction,
            )
        )
    return result
