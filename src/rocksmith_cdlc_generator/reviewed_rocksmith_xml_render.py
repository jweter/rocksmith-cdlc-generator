from __future__ import annotations

from .beats import TempoMap
from .fret_mapping import BassMapping, MappedNote
from .fretboard import BassTuning
from .guitar_authoring import GuitarAuthoringChart, GuitarAuthoringNote, GuitarChordEvent
from .models import ProjectManifest
from .reviewed_rocksmith_xml import ReviewedRocksmithXmlInput, ReviewedRocksmithXmlNote
from .rocksmith_xml import build_rocksmith_bass_xml, build_rocksmith_guitar_xml
from .score_source import ArrangementRole


def _guitar_note(note: ReviewedRocksmithXmlNote) -> GuitarAuthoringNote:
    return GuitarAuthoringNote(
        start_seconds=note.time_seconds,
        duration_seconds=note.duration_seconds,
        midi=note.midi,
        string_index=note.string_index,
        fret=note.fret,
        techniques=list(note.techniques),
        bend_points=list(note.bend_points),
        slide_target_fret=note.slide_target_fret,
        link_next=note.link_next,
        trust_class=note.trust_class,
        review_required=False,
    )


def reviewed_bass_mapping(xml_input: ReviewedRocksmithXmlInput) -> BassMapping:
    """Adapt reviewed Bass XML facts to the existing in-memory Rocksmith builder.

    The adapter does not remap pitches or choose positions. Every emitted position is
    copied from the already reviewed handoff and marked symbolic/review-complete.
    """

    if xml_input.role is not ArrangementRole.bass:
        raise ValueError("reviewed Bass mapping requires the Bass arrangement role")

    tuning = BassTuning(name="Reviewed source tuning", open_midi=tuple(xml_input.tuning_midi))
    notes = [
        MappedNote(
            start=note.time_seconds,
            duration=note.duration_seconds,
            midi=note.midi,
            string=note.string_index,
            fret=note.fret,
            source_confidence=note.import_confidence,
            mapping_confidence=1.0,
            review_required=False,
            alternate_positions=[],
            position_source="symbolic",
            techniques=list(note.techniques),
            bend_points=list(note.bend_points),
            slide_target_fret=note.slide_target_fret,
            link_next=note.link_next,
            trust_class=note.trust_class,
        )
        for note in xml_input.notes
    ]
    return BassMapping(
        tuning=tuning,
        max_fret=max(note.fret for note in xml_input.notes),
        capo=xml_input.capo,
        notes=notes,
    )


def reviewed_guitar_chart(xml_input: ReviewedRocksmithXmlInput) -> GuitarAuthoringChart:
    """Adapt reviewed Lead/Rhythm facts without re-inferring chord membership."""

    if xml_input.role not in {ArrangementRole.lead, ArrangementRole.rhythm}:
        raise ValueError("reviewed guitar chart requires Lead or Rhythm arrangement role")

    by_source_index = {
        note.source_event_index: _guitar_note(note)
        for note in xml_input.notes
    }
    chord_members: set[int] = set()
    for chord in xml_input.chords:
        overlap = chord_members.intersection(chord.source_event_indices)
        if overlap:
            repeated = ", ".join(str(index) for index in sorted(overlap))
            raise ValueError(
                "reviewed guitar XML input assigns source event(s) to multiple chords: "
                f"{repeated}"
            )
        chord_members.update(chord.source_event_indices)

    missing = chord_members.difference(by_source_index)
    if missing:
        missing_text = ", ".join(str(index) for index in sorted(missing))
        raise ValueError(f"reviewed chord member(s) missing from note inventory: {missing_text}")

    shapes = sorted({chord.shape for chord in xml_input.chords})
    shape_ids = {shape: index for index, shape in enumerate(shapes)}
    chords = [
        GuitarChordEvent(
            start_seconds=chord.time_seconds,
            sustain_seconds=chord.sustain_seconds,
            chord_id=shape_ids[chord.shape],
            shape=chord.shape,
            notes=[by_source_index[index] for index in chord.source_event_indices],
            review_required=False,
        )
        for chord in xml_input.chords
    ]
    singles = [
        by_source_index[note.source_event_index]
        for note in xml_input.notes
        if note.source_event_index not in chord_members
    ]

    return GuitarAuthoringChart(
        arrangement=xml_input.role.value,
        source_sha256=xml_input.source_output_sha256,
        alignment_confidence=1.0,
        tuning_midi=tuple(xml_input.tuning_midi),
        capo=xml_input.capo,
        single_notes=sorted(singles, key=lambda note: (note.start_seconds, note.string_index)),
        chords=sorted(chords, key=lambda chord: (chord.start_seconds, chord.chord_id)),
        unresolved_notes=[],
        warnings=[],
    )


def build_reviewed_rocksmith_xml(
    manifest: ProjectManifest,
    tempo_map: TempoMap,
    xml_input: ReviewedRocksmithXmlInput,
):
    """Render reviewed handoff facts with the existing in-memory XML builders.

    This function returns an XML element only. It does not write files, mutate project
    state, package CDLC, install PSARCs, or interact with Rocksmith/NoCableLauncher.
    """

    if xml_input.role is ArrangementRole.bass:
        return build_rocksmith_bass_xml(manifest, tempo_map, reviewed_bass_mapping(xml_input))
    if xml_input.role in {ArrangementRole.lead, ArrangementRole.rhythm}:
        return build_rocksmith_guitar_xml(manifest, tempo_map, reviewed_guitar_chart(xml_input))
    raise ValueError(f"unsupported reviewed Rocksmith arrangement role: {xml_input.role}")
