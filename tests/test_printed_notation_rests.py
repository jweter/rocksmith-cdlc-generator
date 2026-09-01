from pathlib import Path

import pytest
from pydantic import ValidationError

from rocksmith_cdlc_generator.printed_notation_import import (
    PrintedNotationEvent,
    PrintedNotationFixture,
    PrintedNotationPage,
    PrintedNotationRestEvent,
    PrintedNotationTimeSignature,
    convert_printed_notation_fixture,
    printed_notation_tempo_map,
)


_DROP_D_BASS = [38, 45, 50, 55]


def _fixture_with_rest() -> PrintedNotationFixture:
    return PrintedNotationFixture(
        instrument="bass",
        tuning_midi=_DROP_D_BASS,
        bpm=120.0,
        time_signature=PrintedNotationTimeSignature(numerator=4, denominator=4),
        pages=[
            PrintedNotationPage(
                page_number=2,
                events=[
                    PrintedNotationEvent(
                        measure=1,
                        beat=1,
                        duration_beats=1.0,
                        string=0,
                        fret=5,
                        field_confidence={"fret": 0.99, "rhythm": 0.98},
                    ),
                    PrintedNotationEvent(
                        measure=1,
                        beat=3,
                        duration_beats=2.0,
                        string=1,
                        fret=0,
                    ),
                ],
                rests=[
                    PrintedNotationRestEvent(
                        measure=1,
                        beat=2,
                        duration_beats=1.0,
                        field_confidence={"rest": 0.96, "rhythm": 0.94},
                        region=(100, 200, 160, 250),
                    )
                ],
            )
        ],
    )


def test_explicit_rest_is_preserved_with_timing_and_provenance() -> None:
    imported = convert_printed_notation_fixture(
        _fixture_with_rest(),
        source_path=Path("recognized-page2.json"),
        source_sha256="abc123",
    )

    track = imported.tracks[0]
    assert len(track.notes) == 2
    assert len(track.rests) == 1
    rest = track.rests[0]
    assert rest.start_seconds == pytest.approx(0.5)
    assert rest.duration_seconds == pytest.approx(0.5)
    assert rest.measure == 1
    assert rest.beat == 2
    assert rest.import_confidence == pytest.approx(0.94)
    assert rest.origin is not None
    assert rest.origin.kind == "printed_notation_image"
    assert rest.origin.page == 2
    assert rest.origin.region == (100, 200, 160, 250)
    assert imported.warnings == []


def test_rest_counts_as_measure_coverage_not_missing_recognition() -> None:
    fixture = _fixture_with_rest()
    imported = convert_printed_notation_fixture(
        fixture,
        source_path=Path("recognized-page2.json"),
        source_sha256="abc123",
    )

    assert not any("coverage" in warning for warning in imported.warnings)


def test_note_overlapping_explicit_rest_is_flagged_for_review() -> None:
    fixture = _fixture_with_rest()
    fixture.pages[0].events[0].duration_beats = 2.0

    imported = convert_printed_notation_fixture(
        fixture,
        source_path=Path("recognized-page2.json"),
        source_sha256="abc123",
    )

    assert any("overlapping an explicit rest" in warning for warning in imported.warnings)


def test_rest_only_page_is_valid_and_sets_tempo_map_extent() -> None:
    fixture = PrintedNotationFixture(
        instrument="bass",
        tuning_midi=_DROP_D_BASS,
        bpm=90.0,
        time_signature=PrintedNotationTimeSignature(numerator=4, denominator=4),
        pages=[
            PrintedNotationPage(
                page_number=2,
                rests=[
                    PrintedNotationRestEvent(
                        measure=3,
                        beat=1,
                        duration_beats=4.0,
                    )
                ],
            )
        ],
    )

    tempo_map = printed_notation_tempo_map(fixture)
    assert max(beat.measure for beat in tempo_map.beats) == 3


def test_rest_confidence_must_be_normalized() -> None:
    with pytest.raises(ValidationError):
        PrintedNotationRestEvent(
            measure=1,
            beat=1,
            duration_beats=1.0,
            field_confidence={"rest": 1.2},
        )


def test_page_with_neither_notes_nor_rests_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PrintedNotationPage(page_number=2)
