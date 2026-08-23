from __future__ import annotations

from dataclasses import dataclass

from .song_preview import PreviewArrangement, SongPreviewSnapshot


@dataclass(frozen=True)
class MeasureWindow:
    number: int
    start_seconds: float
    end_seconds: float
    numerator: int
    denominator: int

    @property
    def duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds


@dataclass(frozen=True)
class MeasureFretSummary:
    measure_number: int
    event_count: int
    review_required_count: int
    unresolved_position_count: int
    open_string_count: int
    active_strings: tuple[int, ...]
    min_fret: int | None
    max_fret: int | None

    @property
    def fret_span_text(self) -> str:
        if self.min_fret is None or self.max_fret is None:
            return "no fretted positions"
        if self.min_fret == self.max_fret:
            return f"fret {self.min_fret}"
        return f"frets {self.min_fret}-{self.max_fret}"


def _last_preview_time(snapshot: SongPreviewSnapshot) -> float:
    values = [0.0]
    values.extend(snapshot.beat_times_seconds)
    values.extend(item.time_seconds for item in snapshot.time_signatures)
    for arrangement in snapshot.arrangements:
        values.extend(note.end_seconds for note in arrangement.notes)
    return max(values)


def _signature_at(snapshot: SongPreviewSnapshot, when: float):
    signatures = sorted(snapshot.time_signatures, key=lambda item: item.time_seconds)
    current = signatures[0] if signatures else None
    for signature in signatures:
        if signature.time_seconds > when + 1e-9:
            break
        current = signature
    return current


def build_measure_windows(snapshot: SongPreviewSnapshot) -> list[MeasureWindow]:
    """Build read-only musical measure windows from canonical preview timing evidence.

    Guitar Pro imports record every measure header as a time-signature event, so those
    event times are preferred as exact bar starts. For sources that expose only one
    signature event, an existing quarter-note beat grid may be used when the signature
    resolves to an integral number of quarter-note beats. No arbitrary fixed-duration
    bars are invented when neither authority is available.
    """

    signatures = sorted(snapshot.time_signatures, key=lambda item: item.time_seconds)
    if not signatures:
        return []

    starts: list[tuple[float, int, int]] = []
    distinct_times: list[float] = []
    for item in signatures:
        if not distinct_times or abs(item.time_seconds - distinct_times[-1]) > 1e-6:
            distinct_times.append(item.time_seconds)
            starts.append((item.time_seconds, item.numerator, item.denominator))

    # GP3/GP4/GP5 adapter semantics: every measure header is preserved in
    # time_signatures, even when the signature value itself is unchanged.
    if len(starts) < 2 and snapshot.beat_times_seconds:
        signature = signatures[0]
        quarter_beats = signature.numerator * 4 / signature.denominator
        rounded = round(quarter_beats)
        if abs(quarter_beats - rounded) <= 1e-9 and rounded > 0:
            beats = [beat for beat in snapshot.beat_times_seconds if beat >= signature.time_seconds - 1e-6]
            generated: list[tuple[float, int, int]] = []
            for index in range(0, len(beats), rounded):
                generated.append((beats[index], signature.numerator, signature.denominator))
            if generated:
                starts = generated

    if not starts:
        return []

    final_time = _last_preview_time(snapshot)
    windows: list[MeasureWindow] = []
    for index, (start, numerator, denominator) in enumerate(starts):
        if index + 1 < len(starts):
            end = starts[index + 1][0]
        else:
            end = final_time
            if end <= start + 1e-6 and windows:
                end = start + windows[-1].duration_seconds
        if end <= start + 1e-6:
            continue
        current_signature = _signature_at(snapshot, start)
        windows.append(
            MeasureWindow(
                number=index + 1,
                start_seconds=start,
                end_seconds=end,
                numerator=(current_signature.numerator if current_signature else numerator),
                denominator=(current_signature.denominator if current_signature else denominator),
            )
        )
    return windows


def measure_index_for_time(measures: list[MeasureWindow], when: float) -> int | None:
    if not measures:
        return None
    for index, measure in enumerate(measures):
        if measure.start_seconds <= when < measure.end_seconds:
            return index
    if when >= measures[-1].end_seconds:
        return len(measures) - 1
    if when < measures[0].start_seconds:
        return 0
    return None


def notes_for_measure(arrangement: PreviewArrangement, measure: MeasureWindow):
    """Return events whose onsets belong to one bar, preserving source event identity."""

    return [
        note
        for note in arrangement.notes
        if measure.start_seconds <= note.start_seconds < measure.end_seconds
    ]


def summarize_measure_fingering(
    arrangement: PreviewArrangement,
    measure: MeasureWindow,
) -> MeasureFretSummary:
    notes = notes_for_measure(arrangement, measure)
    positioned = [note for note in notes if note.string_index is not None and note.fret is not None]
    fretted = [int(note.fret) for note in positioned if int(note.fret) > 0]
    strings = tuple(sorted({int(note.string_index) + 1 for note in positioned}))
    return MeasureFretSummary(
        measure_number=measure.number,
        event_count=len(notes),
        review_required_count=sum(note.review_required for note in notes),
        unresolved_position_count=sum(
            note.string_index is None or note.fret is None for note in notes
        ),
        open_string_count=sum(note.fret == 0 for note in positioned),
        active_strings=strings,
        min_fret=min(fretted) if fretted else None,
        max_fret=max(fretted) if fretted else None,
    )
