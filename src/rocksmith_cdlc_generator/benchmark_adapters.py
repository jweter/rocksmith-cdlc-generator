from __future__ import annotations

from .benchmark import BenchmarkChart, BenchmarkNote
from .fret_mapping import BassMapping
from .guitar_authoring import GuitarAuthoringChart
from .transcription import BassTranscription


def from_bass_transcription(
    transcription: BassTranscription,
    *,
    case_id: str,
    audio_duration_seconds: float,
    human_edit_seconds: float | None = None,
) -> BenchmarkChart:
    return BenchmarkChart(
        case_id=case_id,
        arrangement="bass",
        audio_duration_seconds=audio_duration_seconds,
        human_edit_seconds=human_edit_seconds,
        notes=[
            BenchmarkNote(
                start_seconds=note.start,
                duration_seconds=note.duration,
                midi=note.midi,
                review_required=note.review_required,
            )
            for note in transcription.notes
        ],
    )


def from_bass_mapping(
    mapping: BassMapping,
    *,
    case_id: str,
    audio_duration_seconds: float,
    human_edit_seconds: float | None = None,
) -> BenchmarkChart:
    return BenchmarkChart(
        case_id=case_id,
        arrangement="bass",
        audio_duration_seconds=audio_duration_seconds,
        human_edit_seconds=human_edit_seconds,
        notes=[
            BenchmarkNote(
                start_seconds=note.start,
                duration_seconds=note.duration,
                midi=note.midi,
                string_index=note.string,
                fret=note.fret,
                techniques=list(note.techniques),
                review_required=note.review_required,
                unresolved=not note.mapped,
            )
            for note in mapping.notes
        ],
    )


def from_guitar_authoring(
    chart: GuitarAuthoringChart,
    *,
    case_id: str,
    audio_duration_seconds: float,
    human_edit_seconds: float | None = None,
) -> BenchmarkChart:
    notes: list[BenchmarkNote] = []
    for note in chart.single_notes:
        notes.append(
            BenchmarkNote(
                start_seconds=note.start_seconds,
                duration_seconds=note.duration_seconds,
                midi=note.midi,
                string_index=note.string_index,
                fret=note.fret,
                techniques=list(note.techniques),
                review_required=note.review_required,
            )
        )
    for chord in chart.chords:
        for note in chord.notes:
            notes.append(
                BenchmarkNote(
                    start_seconds=note.start_seconds,
                    duration_seconds=note.duration_seconds,
                    midi=note.midi,
                    string_index=note.string_index,
                    fret=note.fret,
                    techniques=list(note.techniques),
                    review_required=chord.review_required or note.review_required,
                )
            )
    for note in chart.unresolved_notes:
        notes.append(
            BenchmarkNote(
                start_seconds=note.source_start_seconds,
                duration_seconds=0.001,
                midi=note.midi,
                review_required=True,
                unresolved=True,
            )
        )
    notes.sort(key=lambda item: (item.start_seconds, item.midi, item.string_index or -1))
    return BenchmarkChart(
        case_id=case_id,
        arrangement=chart.arrangement,
        audio_duration_seconds=audio_duration_seconds,
        human_edit_seconds=human_edit_seconds,
        notes=notes,
    )
