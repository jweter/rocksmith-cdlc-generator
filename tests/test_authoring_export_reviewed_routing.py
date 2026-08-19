"""authoring_export.py should route through reviewed_rocksmith_xml_render.py once a
project has promoted reviewed score-anchor timing, and must fail closed rather than
silently falling back to the older charts/<role>_source.json path when that promoted
authority cannot currently be built (issue #241 remaining gap)."""

from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from rocksmith_cdlc_generator import authoring_export
from rocksmith_cdlc_generator.authoring_export import (
    export_project_bass_authoring,
    export_project_guitar_authoring,
)
from rocksmith_cdlc_generator.beats import BeatEvent, TempoMap, write_tempo_map
from rocksmith_cdlc_generator.fret_mapping import BassMapping, MappedNote, write_bass_mapping
from rocksmith_cdlc_generator.fretboard import E_STANDARD
from rocksmith_cdlc_generator.guitar_authoring import GuitarAuthoringChart, GuitarAuthoringNote
from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.reviewed_rocksmith_xml import (
    ReviewedRocksmithXmlInput,
    ReviewedRocksmithXmlNote,
)
from rocksmith_cdlc_generator.reviewed_score_timing_authority import REVIEWED_SCORE_TIMING_PATH
from rocksmith_cdlc_generator.score_source import ArrangementRole
from rocksmith_cdlc_generator.source_import import SourceTrustClass
from rocksmith_cdlc_generator.transcription import BassTranscription, NoteEvent, write_transcription


def _manifest(project: Path, *, instruments: list[str]) -> None:
    project.mkdir(parents=True, exist_ok=True)
    ProjectManifest(
        project_name="reviewed-routing-test",
        artist="Test Artist",
        title="Test Song",
        source_original_path="source.wav",
        source_project_path="source/source.wav",
        source_sha256="0" * 64,
        source_metadata=AudioMetadata(
            duration_seconds=8.0,
            sample_rate_hz=44100,
            channels=2,
            codec_name="pcm_s16le",
            format_name="wav",
        ),
        arrangement_instruments=instruments,
    ).save(project)


def _tempo(project: Path) -> None:
    write_tempo_map(
        TempoMap(
            engine="test",
            time_signature_numerator=4,
            time_signature_denominator=4,
            beats=[
                BeatEvent(time=0.5, beat=1, measure=1, bpm=120.0, confidence=0.9, is_downbeat=True),
                BeatEvent(time=1.0, beat=2, measure=1, bpm=120.0, confidence=0.9),
                BeatEvent(time=1.5, beat=3, measure=1, bpm=120.0, confidence=0.9),
                BeatEvent(time=2.0, beat=4, measure=1, bpm=120.0, confidence=0.9),
            ],
        ),
        project / "analysis" / "tempo_map.json",
    )


def _mark_reviewed_timing_promoted(project: Path) -> None:
    """Create only the promotion marker file authoring_export checks for.

    The real content shape is exercised by test_reviewed_score_timing_authority.py;
    here `reviewed_rocksmith_xml_input` itself is monkeypatched, so authoring_export's
    routing decision (does the marker file exist?) is the only thing under test.
    """

    path = project / REVIEWED_SCORE_TIMING_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")


def _legacy_bass_project(project: Path) -> None:
    _manifest(project, instruments=["bass"])
    _tempo(project)
    write_transcription(
        BassTranscription(
            engine="test",
            source_path="audio.wav",
            sample_rate_hz=44100,
            notes=[
                NoteEvent(
                    start=1.0,
                    duration=0.4,
                    midi=40,
                    confidence=0.9,
                    pitch_confidence=0.9,
                    timing_confidence=0.9,
                )
            ],
        ),
        project / "analysis" / "bass_raw.json",
    )
    write_bass_mapping(
        BassMapping(
            tuning=E_STANDARD,
            max_fret=24,
            notes=[
                MappedNote(
                    start=1.0,
                    duration=0.4,
                    midi=40,
                    string=0,
                    fret=12,
                    source_confidence=0.9,
                    mapping_confidence=0.9,
                )
            ],
        ),
        project / "charts" / "bass_mapped.json",
    )


def _legacy_lead_project(project: Path) -> None:
    _manifest(project, instruments=["lead"])
    _tempo(project)
    GuitarAuthoringChart(
        arrangement="lead",
        source_sha256="1" * 64,
        alignment_confidence=0.95,
        tuning_midi=(40, 45, 50, 55, 59, 64),
        single_notes=[
            GuitarAuthoringNote(
                start_seconds=1.0,
                duration_seconds=0.4,
                midi=45,
                string_index=0,
                fret=5,
                trust_class=SourceTrustClass.user_confirmed,
            )
        ],
    ).write_json(project / "charts" / "lead_source.json")


def _reviewed_bass_input() -> ReviewedRocksmithXmlInput:
    return ReviewedRocksmithXmlInput(
        role=ArrangementRole.bass,
        source_track_index=2,
        source_output_json="analysis/score_fanout/bass.json",
        source_output_sha256="a" * 64,
        recording_sha256="b" * 64,
        score_sha256="c" * 64,
        tuning_midi=(28, 33, 38, 43),
        notes=[
            ReviewedRocksmithXmlNote(
                source_event_index=0,
                time_seconds=3.5,
                duration_seconds=0.6,
                midi=31,
                string_index=1,
                fret=3,
                import_confidence=0.97,
                trust_class=SourceTrustClass.symbolic_verified,
            )
        ],
    )


def _reviewed_lead_input() -> ReviewedRocksmithXmlInput:
    return ReviewedRocksmithXmlInput(
        role=ArrangementRole.lead,
        source_track_index=4,
        source_output_json="analysis/score_fanout/lead.json",
        source_output_sha256="d" * 64,
        recording_sha256="e" * 64,
        score_sha256="f" * 64,
        tuning_midi=(40, 45, 50, 55, 59, 64),
        notes=[
            ReviewedRocksmithXmlNote(
                source_event_index=0,
                time_seconds=3.5,
                duration_seconds=0.6,
                midi=47,
                string_index=1,
                fret=2,
                import_confidence=0.97,
                trust_class=SourceTrustClass.symbolic_verified,
            )
        ],
    )


def test_bass_export_uses_legacy_mapping_when_no_reviewed_timing_promoted(tmp_path, monkeypatch) -> None:
    project = tmp_path / "project"
    _legacy_bass_project(project)

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("reviewed_rocksmith_xml_input must not be consulted without promotion")

    monkeypatch.setattr(authoring_export, "reviewed_rocksmith_xml_input", fail_if_called)

    outputs = export_project_bass_authoring(project)

    root = ET.parse(outputs["xml"]).getroot()
    notes = root.findall("levels/level/notes/note")
    assert [note.attrib["fret"] for note in notes] == ["12"]
    manifest = outputs["manifest"].read_text(encoding="utf-8")
    assert "charts/bass_mapped.json" in manifest
    assert "promoted, human-reviewed" not in manifest


def test_bass_export_routes_through_reviewed_render_once_promoted(tmp_path, monkeypatch) -> None:
    project = tmp_path / "project"
    _legacy_bass_project(project)
    _mark_reviewed_timing_promoted(project)
    reviewed_input = _reviewed_bass_input()
    monkeypatch.setattr(
        authoring_export,
        "reviewed_rocksmith_xml_input",
        lambda _project, role: reviewed_input if role is ArrangementRole.bass else pytest.fail("wrong role"),
    )

    outputs = export_project_bass_authoring(project)

    root = ET.parse(outputs["xml"]).getroot()
    notes = root.findall("levels/level/notes/note")
    # Reviewed note (fret 3 at 3.5s) is used, not the legacy chart's fret-12 note at 1.0s.
    assert [note.attrib["fret"] for note in notes] == ["3"]
    assert notes[0].attrib["time"] == "3.500"
    manifest = outputs["manifest"].read_text(encoding="utf-8")
    assert "analysis/score_fanout/bass.json" in manifest
    assert "promoted, human-reviewed" in manifest


def test_bass_export_fails_closed_when_promoted_but_not_buildable(tmp_path, monkeypatch) -> None:
    project = tmp_path / "project"
    _legacy_bass_project(project)
    _mark_reviewed_timing_promoted(project)

    def broken(_project, _role):
        raise ValueError("bass score mapping is not human-confirmed")

    monkeypatch.setattr(authoring_export, "reviewed_rocksmith_xml_input", broken)

    with pytest.raises(ValueError, match="not human-confirmed"):
        export_project_bass_authoring(project)

    # No partial/legacy fallback XML should have been written.
    assert not (project / "eof" / "arr_bass_RS2.xml").exists()


def test_lead_export_routes_through_reviewed_render_once_promoted(tmp_path, monkeypatch) -> None:
    project = tmp_path / "project"
    _legacy_lead_project(project)
    _mark_reviewed_timing_promoted(project)
    reviewed_input = _reviewed_lead_input()
    monkeypatch.setattr(
        authoring_export,
        "reviewed_rocksmith_xml_input",
        lambda _project, role: reviewed_input if role is ArrangementRole.lead else pytest.fail("wrong role"),
    )

    outputs = export_project_guitar_authoring(project, arrangement="lead")

    root = ET.parse(outputs["xml"]).getroot()
    notes = root.findall("levels/level/notes/note")
    assert [note.attrib["fret"] for note in notes] == ["2"]
    manifest = outputs["manifest"].read_text(encoding="utf-8")
    assert "analysis/score_fanout/lead.json" in manifest
    assert "promoted, human-reviewed" in manifest


def test_lead_export_uses_legacy_chart_when_no_reviewed_timing_promoted(tmp_path, monkeypatch) -> None:
    project = tmp_path / "project"
    _legacy_lead_project(project)

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("reviewed_rocksmith_xml_input must not be consulted without promotion")

    monkeypatch.setattr(authoring_export, "reviewed_rocksmith_xml_input", fail_if_called)

    outputs = export_project_guitar_authoring(project, arrangement="lead")

    root = ET.parse(outputs["xml"]).getroot()
    notes = root.findall("levels/level/notes/note")
    assert [note.attrib["fret"] for note in notes] == ["5"]
