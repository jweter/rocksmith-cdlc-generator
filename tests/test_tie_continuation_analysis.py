from __future__ import annotations

from rocksmith_cdlc_generator.source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTrack,
)
from rocksmith_cdlc_generator.tie_continuation_analysis import analyze_imported_tie_continuations


def _note(
    start: float,
    duration: float,
    *,
    string_index: int | None = 0,
    fret: int | None = 3,
    midi: int = 43,
    tie: bool = False,
) -> SourceNoteEvent:
    return SourceNoteEvent(
        start_seconds=start,
        duration_seconds=duration,
        midi=midi,
        string_index=string_index,
        fret=fret,
        techniques=["tie"] if tie else [],
        import_confidence=1.0,
        review_required=tie,
    )


def _source(notes: list[SourceNoteEvent]) -> ImportedSource:
    return ImportedSource(
        provenance=SourceProvenance(
            source_type="gp5",
            source_filename="song.gp5",
            source_sha256="a" * 64,
            importer="test",
            importer_version="1",
        ),
        tracks=[
            SourceTrack(
                source_track_index=2,
                name="Lead",
                instrument="lead",
                tuning_midi=[40, 45, 50, 55, 59, 64],
                notes=notes,
            )
        ],
    )


def test_classifies_adjacent_same_physical_note_as_exact_continuation() -> None:
    source = _source([
        _note(0.0, 0.5),
        _note(0.5, 0.5, tie=True),
    ])

    analysis = analyze_imported_tie_continuations(source)

    assert analysis.tie_event_count == 1
    assert analysis.exact_continuation_count == 1
    assert analysis.ambiguous_or_orphan_count == 0
    candidate = analysis.candidates[0]
    assert candidate.event_index == 1
    assert candidate.predecessor_event_index == 0
    assert candidate.classification == "exact_continuation"


def test_non_adjacent_or_positionless_ties_remain_unresolved() -> None:
    source = _source([
        _note(0.0, 0.25),
        _note(0.5, 0.5, tie=True),
        _note(1.0, 0.5, string_index=None, fret=None, tie=True),
    ])

    analysis = analyze_imported_tie_continuations(source)

    assert analysis.tie_event_count == 2
    assert analysis.exact_continuation_count == 0
    assert analysis.ambiguous_or_orphan_count == 2
    assert all(item.predecessor_event_index is None for item in analysis.candidates)


def test_multiple_matching_predecessors_fail_closed_as_ambiguous() -> None:
    source = _source([
        _note(0.0, 0.5),
        _note(0.25, 0.25),
        _note(0.5, 0.5, tie=True),
    ])

    analysis = analyze_imported_tie_continuations(source)

    assert analysis.tie_event_count == 1
    assert analysis.exact_continuation_count == 0
    assert analysis.candidates[0].classification == "ambiguous_or_orphan"


def test_analysis_is_read_only_and_preserves_review_flags() -> None:
    source = _source([
        _note(0.0, 0.5),
        _note(0.5, 0.5, tie=True),
    ])
    before = source.model_dump_json()

    analyze_imported_tie_continuations(source)

    assert source.model_dump_json() == before
    assert source.tracks[0].notes[1].review_required is True
    assert source.tracks[0].notes[1].techniques == ["tie"]
