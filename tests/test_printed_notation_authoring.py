import json
from pathlib import Path

import pytest

from rocksmith_cdlc_generator.printed_notation_authoring import (
    PrintedNotationAuthoringError,
    build_printed_notation_bass_xml,
    practice_manifest_for_printed_notation,
    printed_notation_bass_authoring_input,
    printed_notation_bass_rocksmith_xml_input,
    reviewed_export_arrangement_from_printed_notation,
)
from rocksmith_cdlc_generator.printed_notation_import import (
    PrintedNotationEvent,
    PrintedNotationFixture,
    PrintedNotationPage,
    PrintedNotationTimeSignature,
    convert_printed_notation_fixture,
    printed_notation_tempo_map,
)
from rocksmith_cdlc_generator.score_source import ArrangementRole

_BASS_TUNING = [28, 33, 38, 43]


def _fixture(*, human_reviewed: bool) -> PrintedNotationFixture:
    return PrintedNotationFixture(
        instrument="bass",
        tuning_midi=_BASS_TUNING,
        bpm=120.0,
        time_signature=PrintedNotationTimeSignature(numerator=4, denominator=4),
        pages=[
            PrintedNotationPage(
                page_number=1,
                events=[
                    PrintedNotationEvent(
                        measure=1, beat=1, duration_beats=1.0, string=0, fret=3,
                        human_reviewed=human_reviewed,
                    ),
                    PrintedNotationEvent(
                        measure=1, beat=2, duration_beats=1.0, string=0, fret=5,
                        human_reviewed=human_reviewed,
                    ),
                    PrintedNotationEvent(
                        measure=1, beat=3, duration_beats=2.0, string=1, fret=0,
                        human_reviewed=human_reviewed,
                    ),
                ],
            )
        ],
    )


def _write_fixture(destination: Path, *, human_reviewed: bool) -> None:
    destination.write_text(
        _fixture(human_reviewed=human_reviewed).model_dump_json(indent=2), encoding="utf-8"
    )


def _project(tmp_path: Path) -> Path:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "project.json").write_text("{}", encoding="utf-8")
    return project_dir


def test_reviewed_export_arrangement_copies_source_timing_as_reviewed_timing() -> None:
    imported = convert_printed_notation_fixture(
        _fixture(human_reviewed=True), source_path=Path("page1.json"), source_sha256="ab" * 32
    )
    arrangement = reviewed_export_arrangement_from_printed_notation(
        imported, source_output_json="sources/imported/page1.json", source_output_sha256="cd" * 32
    )
    assert arrangement.role is ArrangementRole.bass
    assert arrangement.recording_sha256 == "cd" * 32
    assert arrangement.score_sha256 == "cd" * 32
    for note in arrangement.notes:
        assert note.reviewed_start_seconds == note.source_start_seconds
        assert note.reviewed_duration_seconds == note.source_duration_seconds
        assert note.position_ready is True


def test_rejects_source_from_a_different_adapter() -> None:
    imported = convert_printed_notation_fixture(
        _fixture(human_reviewed=True), source_path=Path("page1.json"), source_sha256="ab" * 32
    )
    tampered = imported.model_copy(
        update={
            "provenance": imported.provenance.model_copy(update={"importer": "pyguitarpro-adapter"})
        }
    )
    with pytest.raises(PrintedNotationAuthoringError):
        reviewed_export_arrangement_from_printed_notation(
            tampered, source_output_json="x.json", source_output_sha256="cd" * 32
        )


def test_rejects_non_bass_instrument() -> None:
    fixture = _fixture(human_reviewed=True)
    fixture.instrument = "lead"
    imported = convert_printed_notation_fixture(
        fixture, source_path=Path("page1.json"), source_sha256="ab" * 32
    )
    with pytest.raises(PrintedNotationAuthoringError):
        reviewed_export_arrangement_from_printed_notation(
            imported, source_output_json="x.json", source_output_sha256="cd" * 32
        )


def test_authoring_input_requires_human_review_promotion(tmp_path: Path) -> None:
    project_dir = _project(tmp_path)
    fixture_path = tmp_path / "page1.json"
    _write_fixture(fixture_path, human_reviewed=False)

    with pytest.raises(ValueError, match="accepted source trust"):
        printed_notation_bass_authoring_input(project_dir, fixture_path)


def test_authoring_input_succeeds_once_reviewed(tmp_path: Path) -> None:
    project_dir = _project(tmp_path)
    fixture_path = tmp_path / "page1.json"
    _write_fixture(fixture_path, human_reviewed=True)

    authoring = printed_notation_bass_authoring_input(project_dir, fixture_path)

    assert len(authoring.notes) == 3
    assert authoring.tuning_midi == tuple(_BASS_TUNING)
    assert [note.fret for note in authoring.notes] == [3, 5, 0]


def test_xml_input_round_trips_from_authoring_input(tmp_path: Path) -> None:
    project_dir = _project(tmp_path)
    fixture_path = tmp_path / "page1.json"
    _write_fixture(fixture_path, human_reviewed=True)

    xml_input = printed_notation_bass_rocksmith_xml_input(project_dir, fixture_path)

    assert xml_input.role is ArrangementRole.bass
    assert len(xml_input.notes) == 3


def test_practice_manifest_duration_covers_full_arrangement() -> None:
    fixture = _fixture(human_reviewed=True)
    tempo_map = printed_notation_tempo_map(fixture)

    manifest = practice_manifest_for_printed_notation(
        fixture,
        tempo_map,
        project_name="test-project",
        title="Test Song",
        artist="Test Artist",
        source_path=Path("page1.json"),
        source_sha256="ab" * 32,
    )

    # 1 measure of 4/4 at 120 BPM = 2.0s; manifest duration must cover at least that.
    assert manifest.source_metadata.duration_seconds > 2.0
    assert manifest.artist == "Test Artist"


def test_build_printed_notation_bass_xml_end_to_end(tmp_path: Path) -> None:
    project_dir = _project(tmp_path)
    fixture_path = tmp_path / "page1.json"
    _write_fixture(fixture_path, human_reviewed=True)

    root = build_printed_notation_bass_xml(
        project_dir,
        fixture_path,
        project_name="test-project",
        title="Test Song",
        artist="Test Artist",
    )

    assert root.tag == "song"
    assert root.find("title").text == "Test Song"
    assert root.find("arrangement").text == "Bass"
    notes = root.find("levels/level/notes")
    assert notes.get("count") == "3"
    fret_values = [note.get("fret") for note in notes]
    assert fret_values == ["3", "5", "0"]


def test_build_printed_notation_bass_xml_requires_artist(tmp_path: Path) -> None:
    project_dir = _project(tmp_path)
    fixture_path = tmp_path / "page1.json"
    _write_fixture(fixture_path, human_reviewed=True)

    with pytest.raises(ValueError, match="artist"):
        build_printed_notation_bass_xml(
            project_dir, fixture_path, project_name="test-project", title="Test Song"
        )
