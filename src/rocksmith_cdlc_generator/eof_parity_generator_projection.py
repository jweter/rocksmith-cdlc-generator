from __future__ import annotations

from .beats import TempoMap
from .eof_parity_fixture import EofParityFixture, parse_eof_parity_fixture
from .reviewed_rocksmith_xml import ReviewedRocksmithXmlInput
from .score_source import ArrangementRole

_ARRANGEMENT_NAMES = {
    ArrangementRole.bass: "bass",
    ArrangementRole.lead: "lead",
    ArrangementRole.rhythm: "rhythm",
}


def eof_parity_fixture_from_generator_output(
    *,
    fixture_id: str,
    source_kind: str,
    reviewed_input: ReviewedRocksmithXmlInput,
    tempo_map: TempoMap,
) -> EofParityFixture:
    """Project real generator output into the media-safe #414 EOF parity fixture contract.

    ``reviewed_input`` is the same authoritative pre-XML Rocksmith authoring boundary
    object that ``rocksmith_xml.py`` consumes to write note/chord elements
    (``rocksmith_xml_input_from_reviewed_bass``/``..._guitar``); ``tempo_map`` is the
    generator's own deterministic beat/measure authority
    (``build_deterministic_tempo_map`` or an equivalent authoritative TempoMap). Only
    fields already covered by the fixture contract are projected. This makes no
    independent claim of EOF parity or human musical acceptance on its own; it exists
    so a committed expected fixture can be compared against real generator output via
    ``compare_eof_parity_fixtures``.
    """

    payload = {
        "schema_version": 1,
        "fixture_id": fixture_id,
        "source_kind": source_kind,
        "arrangement": _ARRANGEMENT_NAMES[reviewed_input.role],
        "beat_times_seconds": [beat.time for beat in tempo_map.beats],
        "notes": [
            {
                "onset_seconds": note.time_seconds,
                "duration_seconds": note.duration_seconds,
                "string": note.string_index,
                "fret": note.fret,
                "techniques": list(note.techniques),
            }
            for note in reviewed_input.notes
        ],
    }
    return parse_eof_parity_fixture(payload)
