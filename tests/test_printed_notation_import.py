import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from rocksmith_cdlc_generator.printed_notation_import import (
    PRINTED_NOTATION_ADAPTER_ID,
    PrintedNotationEvent,
    PrintedNotationFixture,
    PrintedNotationImportError,
    PrintedNotationPage,
    PrintedNotationTimeSignature,
    convert_printed_notation_fixture,
    import_printed_notation,
    import_project_printed_notation,
    printed_notation_adapter_sha256,
)
from rocksmith_cdlc_generator.source_import import SourceEventOrigin, SourceNoteEvent

# Standard 4-string bass, low string first: E1 A1 D2 G2.
_BASS_TUNING = [28, 33, 38, 43]


def _two_measure_fixture() -> PrintedNotationFixture:
    return PrintedNotationFixture(
        instrument="bass",
        tuning_midi=_BASS_TUNING,
        bpm=120.0,
        time_signature=PrintedNotationTimeSignature(numerator=4, denominator=4),
        pages=[
            PrintedNotationPage(
                page_number=12,
                events=[
                    PrintedNotationEvent(
                        measure=1,
                        beat=1,
                        duration_beats=1.0,
                        string=0,
                        fret=3,
                        field_confidence={"fret": 0.997, "rhythm": 0.98},
                        region=(412, 1160, 498, 1240),
                    ),
                    PrintedNotationEvent(
                        measure=1,
                        beat=2,
                        duration_beats=2.0,
                        string=0,
                        fret=5,
                        techniques=["slide"],
                    ),
                    PrintedNotationEvent(
                        measure=1,
                        beat=4,
                        duration_beats=1.0,
                        string=1,
                        fret=0,
                    ),
                    PrintedNotationEvent(
                        measure=2,
                        beat=1,
                        duration_beats=4.0,
                        string=2,
                        fret=2,
                    ),
                ],
            )
        ],
    )


def test_converts_measure_beat_to_seconds_via_shared_tempo_arithmetic() -> None:
    imported = convert_printed_notation_fixture(
        _two_measure_fixture(), source_path=Path("page12.json"), source_sha256="abc123"
    )
    notes = imported.tracks[0].notes
    assert [round(note.start_seconds, 6) for note in notes] == [0.0, 0.5, 1.5, 2.0]
    assert notes[0].duration_seconds == pytest.approx(0.5)
    assert notes[3].duration_seconds == pytest.approx(2.0)


def test_string_and_fret_map_to_expected_midi() -> None:
    imported = convert_printed_notation_fixture(
        _two_measure_fixture(), source_path=Path("page12.json"), source_sha256="abc123"
    )
    first_note = imported.tracks[0].notes[0]
    assert first_note.midi == _BASS_TUNING[0] + 3
    assert first_note.string_index == 0
    assert first_note.fret == 3


def test_provenance_and_origin_are_recorded() -> None:
    imported = convert_printed_notation_fixture(
        _two_measure_fixture(), source_path=Path("page12.json"), source_sha256="abc123"
    )
    assert imported.provenance.importer == PRINTED_NOTATION_ADAPTER_ID
    assert imported.provenance.source_sha256 == "abc123"

    first_note = imported.tracks[0].notes[0]
    assert first_note.measure == 1
    assert first_note.beat == 1
    assert first_note.origin == SourceEventOrigin(
        kind="printed_tab_image", page=12, region=(412, 1160, 498, 1240)
    )
    assert first_note.import_confidence == pytest.approx(0.98)


def test_review_required_defaults_false_and_is_preserved() -> None:
    fixture = _two_measure_fixture()
    fixture.pages[0].events[0].review_required = True
    imported = convert_printed_notation_fixture(
        fixture, source_path=Path("page12.json"), source_sha256="abc123"
    )
    assert imported.tracks[0].notes[0].review_required is True
    assert imported.tracks[0].notes[1].review_required is False


def test_incomplete_measure_produces_warning_not_error() -> None:
    fixture = _two_measure_fixture()
    # Drop the last measure-1 event so measure 1 only totals 3 beats out of 4.
    fixture.pages[0].events.pop(2)
    imported = convert_printed_notation_fixture(
        fixture, source_path=Path("page12.json"), source_sha256="abc123"
    )
    assert any("Measure 1" in warning for warning in imported.warnings)


def test_full_measure_produces_no_warning() -> None:
    imported = convert_printed_notation_fixture(
        _two_measure_fixture(), source_path=Path("page12.json"), source_sha256="abc123"
    )
    assert imported.warnings == []


def test_string_outside_declared_tuning_is_rejected() -> None:
    fixture = _two_measure_fixture()
    fixture.pages[0].events[0].string = 7
    with pytest.raises(PrintedNotationImportError):
        convert_printed_notation_fixture(
            fixture, source_path=Path("page12.json"), source_sha256="abc123"
        )


def test_field_confidence_out_of_range_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PrintedNotationEvent(
            measure=1,
            beat=1,
            duration_beats=1.0,
            string=0,
            fret=0,
            field_confidence={"fret": 1.5},
        )


def test_source_note_event_field_confidence_out_of_range_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SourceNoteEvent(
            start_seconds=0.0,
            duration_seconds=1.0,
            midi=40,
            import_confidence=1.0,
            field_confidence={"fret": -0.1},
        )


def test_page_requires_at_least_one_event() -> None:
    with pytest.raises(ValidationError):
        PrintedNotationPage(page_number=1, events=[])


def test_fixture_requires_at_least_one_page() -> None:
    with pytest.raises(ValidationError):
        PrintedNotationFixture(
            instrument="bass", tuning_midi=_BASS_TUNING, bpm=120.0, pages=[]
        )


def _write_fixture_json(destination: Path) -> None:
    fixture = _two_measure_fixture()
    destination.write_text(fixture.model_dump_json(indent=2), encoding="utf-8")


def test_import_printed_notation_round_trips_through_a_file(tmp_path: Path) -> None:
    fixture_path = tmp_path / "page12.json"
    _write_fixture_json(fixture_path)

    imported = import_printed_notation(fixture_path)

    assert imported.provenance.source_filename == "page12.json"
    assert len(imported.provenance.source_sha256) == 64
    assert len(imported.tracks[0].notes) == 4


def test_import_printed_notation_rejects_non_json_suffix(tmp_path: Path) -> None:
    fixture_path = tmp_path / "page12.txt"
    _write_fixture_json(fixture_path)
    with pytest.raises(PrintedNotationImportError):
        import_printed_notation(fixture_path)


def test_import_printed_notation_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        import_printed_notation(tmp_path / "missing.json")


def test_import_printed_notation_malformed_json_raises(tmp_path: Path) -> None:
    fixture_path = tmp_path / "page12.json"
    fixture_path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(PrintedNotationImportError):
        import_printed_notation(fixture_path)


def test_import_project_printed_notation_writes_into_project_sources(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "project.json").write_text("{}", encoding="utf-8")
    fixture_path = tmp_path / "page12.json"
    _write_fixture_json(fixture_path)

    destination = import_project_printed_notation(project_dir, fixture_path)

    assert destination.is_file()
    assert destination.parent == project_dir / "sources" / "imported"
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["provenance"]["importer"] == PRINTED_NOTATION_ADAPTER_ID


def test_import_project_printed_notation_requires_existing_project(tmp_path: Path) -> None:
    fixture_path = tmp_path / "page12.json"
    _write_fixture_json(fixture_path)
    with pytest.raises(FileNotFoundError):
        import_project_printed_notation(tmp_path / "no-such-project", fixture_path)


def test_adapter_sha256_is_stable_and_nonempty() -> None:
    assert len(printed_notation_adapter_sha256()) == 64
    assert printed_notation_adapter_sha256() == printed_notation_adapter_sha256()
