import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PIL import Image

from rocksmith_cdlc_generator.click_track_render import count_in_offset_seconds
from rocksmith_cdlc_generator.printed_notation_authoring import (
    PrintedNotationAuthoringError,
    build_printed_notation_bass_xml,
    import_project_printed_notation_practice,
    practice_manifest_for_printed_notation,
    printed_notation_bass_authoring_input,
    printed_notation_bass_rocksmith_xml_input,
    register_printed_notation_page_image,
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


def _tiny_png(path: Path) -> Path:
    Image.new("RGB", (4, 4), color=(10, 20, 30)).save(path, format="PNG")
    return path


def test_import_project_printed_notation_practice_writes_xml_and_click(tmp_path: Path) -> None:
    project_dir = _project(tmp_path)
    fixture_path = tmp_path / "page1.json"
    _write_fixture(fixture_path, human_reviewed=True)

    outputs = import_project_printed_notation_practice(
        project_dir, fixture_path, title="Test Song", artist="Test Artist"
    )

    assert outputs["xml"].is_file()
    assert outputs["click_wav"].is_file()
    assert outputs["sustain_report"].is_file()
    assert outputs["click_alignment_report"].is_file()
    assert "reference_manifest" not in outputs

    sustain_payload = json.loads(outputs["sustain_report"].read_text(encoding="utf-8"))
    assert sustain_payload["boundaries_respected"] is True
    alignment_payload = json.loads(outputs["click_alignment_report"].read_text(encoding="utf-8"))
    assert alignment_payload["aligned"] is True


def test_import_project_printed_notation_practice_shifts_xml_to_match_click_track_count_in(
    tmp_path: Path,
) -> None:
    """Regression: the XML chart must share the click-track WAV's count-in offset.

    ``render_click_track_wav`` places chart beat 1 at ``count_in_offset_seconds()``
    seconds into the WAV, not at 0.0. A rendered XML that still started its notes and
    ebeats at 0.0 would lead the paired audio by the count-in's length even though
    both fail-closed checks reported success, since neither check compares the two
    against each other.
    """
    project_dir = _project(tmp_path)
    fixture_path = tmp_path / "page1.json"
    _write_fixture(fixture_path, human_reviewed=True)
    tempo_map = printed_notation_tempo_map(_fixture(human_reviewed=True))
    expected_offset = count_in_offset_seconds(tempo_map, count_in_measures=2)
    assert expected_offset > 0.0

    outputs = import_project_printed_notation_practice(
        project_dir, fixture_path, title="Test Song", artist="Test Artist"
    )

    root = ET.parse(outputs["xml"]).getroot()
    assert float(root.findtext("startBeat")) == pytest.approx(expected_offset, abs=1e-3)
    first_ebeat = root.find("ebeats/ebeat")
    assert first_ebeat is not None
    assert float(first_ebeat.get("time")) == pytest.approx(expected_offset, abs=1e-3)
    first_note = root.find("levels/level/notes/note")
    assert first_note is not None
    assert float(first_note.get("time")) == pytest.approx(expected_offset, abs=1e-3)
    assert float(root.findtext("songLength")) > expected_offset


def test_import_project_printed_notation_practice_rerun_failure_leaves_prior_outputs_untouched(
    tmp_path: Path,
) -> None:
    """Regression: a failing rerun must not touch a project's existing valid outputs.

    Previously the XML and click.wav were written eagerly before validation could
    fail, so a rerun that failed after that point (e.g. an invalid
    ``count_in_measures``) could leave a stale, mismatched output directory. Stage and
    validate the click track before committing: a failing rerun must change nothing on
    disk.
    """
    project_dir = _project(tmp_path)
    fixture_path = tmp_path / "page1.json"
    _write_fixture(fixture_path, human_reviewed=True)

    outputs = import_project_printed_notation_practice(
        project_dir, fixture_path, title="Test Song", artist="Test Artist"
    )
    xml_before = outputs["xml"].read_bytes()
    click_before = outputs["click_wav"].read_bytes()

    with pytest.raises(ValueError, match="count_in_measures"):
        import_project_printed_notation_practice(
            project_dir,
            fixture_path,
            title="Test Song",
            artist="Test Artist",
            count_in_measures=-1,
        )

    assert outputs["xml"].read_bytes() == xml_before
    assert outputs["click_wav"].read_bytes() == click_before
    assert not (project_dir / "printed_notation" / ".click.wav.tmp").exists()


def test_import_project_printed_notation_practice_fails_closed_on_unreviewed_events(
    tmp_path: Path,
) -> None:
    project_dir = _project(tmp_path)
    fixture_path = tmp_path / "page1.json"
    _write_fixture(fixture_path, human_reviewed=False)

    with pytest.raises(ValueError, match="accepted source trust"):
        import_project_printed_notation_practice(
            project_dir, fixture_path, title="Test Song", artist="Test Artist"
        )


def test_import_project_printed_notation_practice_registers_page_image(tmp_path: Path) -> None:
    project_dir = _project(tmp_path)
    fixture_path = tmp_path / "page1.json"
    _write_fixture(fixture_path, human_reviewed=True)
    image_path = _tiny_png(tmp_path / "page1.png")

    outputs = import_project_printed_notation_practice(
        project_dir,
        fixture_path,
        title="Test Song",
        artist="Test Artist",
        page_image=image_path,
    )

    assert outputs["reference_manifest"].is_file()


def test_register_printed_notation_page_image_maps_measure_range(tmp_path: Path) -> None:
    project_dir = _project(tmp_path)
    image_path = _tiny_png(tmp_path / "page1.png")

    hit = register_printed_notation_page_image(
        project_dir, _fixture(human_reviewed=True), image_path
    )

    assert hit.mapping.measure_start == 1
    assert hit.mapping.measure_end == 1
    assert hit.mapping.arrangement.value == "bass"


def test_register_printed_notation_page_image_rejects_multi_page_fixtures(tmp_path: Path) -> None:
    project_dir = _project(tmp_path)
    image_path = _tiny_png(tmp_path / "page1.png")
    fixture = _fixture(human_reviewed=True)
    fixture.pages.append(fixture.pages[0].model_copy(update={"page_number": 2}))

    with pytest.raises(PrintedNotationAuthoringError):
        register_printed_notation_page_image(project_dir, fixture, image_path)
