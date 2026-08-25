from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from rocksmith_cdlc_generator.authoring_export import export_project_guitar_authoring
from rocksmith_cdlc_generator.beats import BeatEvent, TempoMap, write_tempo_map
from rocksmith_cdlc_generator.cli import build_parser
from rocksmith_cdlc_generator.guitar_authoring import (
    GuitarAuthoringChart,
    GuitarAuthoringNote,
    GuitarChordEvent,
    UnresolvedGuitarNote,
)
from rocksmith_cdlc_generator.guitar_validation import validate_guitar_project, write_guitar_review_artifacts
from rocksmith_cdlc_generator.validation import ReviewItem, ValidationReport
from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.packaging_gate import PackagingBlockedError
from rocksmith_cdlc_generator.source_import import SourceTrustClass


def _manifest(project: Path) -> None:
    project.mkdir(parents=True, exist_ok=True)
    ProjectManifest(
        project_name="guitar-export-test",
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
        arrangement_instruments=["lead", "rhythm"],
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


def _note(start: float, string: int, fret: int, midi: int) -> GuitarAuthoringNote:
    return GuitarAuthoringNote(
        start_seconds=start,
        duration_seconds=0.4,
        midi=midi,
        string_index=string,
        fret=fret,
        trust_class=SourceTrustClass.user_confirmed,
    )


def _lead_chart() -> GuitarAuthoringChart:
    chord_notes = [
        _note(2.0, 0, 3, 43),
        _note(2.0, 1, 2, 47),
        _note(2.0, 2, 0, 50),
    ]
    return GuitarAuthoringChart(
        arrangement="lead",
        source_sha256="1" * 64,
        alignment_confidence=0.95,
        tuning_midi=(40, 45, 50, 55, 59, 64),
        single_notes=[_note(1.0, 0, 5, 45)],
        chords=[
            GuitarChordEvent(
                start_seconds=2.0,
                sustain_seconds=0.4,
                chord_id=0,
                shape=(3, 2, 0, -1, -1, -1),
                notes=chord_notes,
            )
        ],
    )


def _write_chart(project: Path, chart: GuitarAuthoringChart) -> Path:
    path = project / "charts" / f"{chart.arrangement}_source.json"
    return chart.write_json(path)


def test_lead_validation_surfaces_missing_rocksmith_authoring_structure(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _manifest(project)
    _tempo(project)
    _write_chart(project, _lead_chart())

    report = validate_guitar_project(project, arrangement="lead")

    assert report.status == "WARNING"
    assert report.can_package is True
    codes = {item.code for item in report.review_queue}
    assert "rocksmith_chord_fingering_missing" in codes
    assert "rocksmith_fhp_missing" in codes


def test_rocksmith_fret_limit_blocks_guitar_export(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _manifest(project)
    _tempo(project)
    chart = _lead_chart().model_copy(
        update={
            "single_notes": [_note(1.0, 0, 25, 65)],
            "chords": [],
        }
    )
    _write_chart(project, chart)

    report = validate_guitar_project(project, arrangement="lead")

    assert report.status == "FAIL"
    assert any(
        item.code == "rocksmith_fret_limit_exceeded"
        and item.severity == "FAIL"
        for item in report.review_queue
    )


def test_bend_and_slide_get_actionable_rocksmith_findings(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _manifest(project)
    _tempo(project)
    bend = _note(1.0, 0, 0, 40).model_copy(update={"techniques": ["bend"]})
    slide = _note(2.0, 0, 5, 45).model_copy(update={"techniques": ["slide"]})
    chart = _lead_chart().model_copy(
        update={
            "single_notes": [bend, slide],
            "chords": [],
        }
    )
    _write_chart(project, chart)

    report = validate_guitar_project(project, arrangement="lead")
    codes = {item.code for item in report.review_queue}

    assert "rocksmith_open_string_bend" in codes
    assert "rocksmith_bend_detail_missing" in codes
    assert "rocksmith_slide_detail_missing" in codes
    assert not any(
        item.code == "unsupported_imported_technique"
        and ("bend" in item.message or "slide" in item.message)
        for item in report.review_queue
    )


def test_unresolved_guitar_note_blocks_export(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _manifest(project)
    _tempo(project)
    chart = _lead_chart().model_copy(
        update={
            "unresolved_notes": [
                UnresolvedGuitarNote(
                    source_start_seconds=3.0,
                    midi=60,
                    reason="string_fret_unresolved",
                )
            ]
        }
    )
    _write_chart(project, chart)

    report = validate_guitar_project(project, arrangement="lead")
    assert report.status == "FAIL"
    assert any(item.code == "unresolved_guitar_position" for item in report.review_queue)

    with pytest.raises(PackagingBlockedError):
        export_project_guitar_authoring(project, arrangement="lead")


def test_project_lead_export_writes_xml_manifest_and_validation(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _manifest(project)
    _tempo(project)
    _write_chart(project, _lead_chart())

    outputs = export_project_guitar_authoring(project, arrangement="lead")

    assert outputs["xml"].is_file()
    assert outputs["manifest"].is_file()
    assert outputs["validation"].is_file()
    root = ET.parse(outputs["xml"]).getroot()
    assert root.findtext("arrangement") == "Lead"
    assert root.find("arrangementProperties").attrib["pathLead"] == "1"
    assert root.find("levels/level/chords").attrib["count"] == "1"


def test_guitar_summary_pairs_actionable_groups_with_raw_warning_total(tmp_path: Path) -> None:
    """#375: Lead/Rhythm validation summaries must show the same actionable/raw
    warning pairing as Bass, so all three arrangements use consistent terminology.
    """
    project = tmp_path / "project"
    warnings = [
        ReviewItem(
            code="guitar_note_requires_review",
            severity="WARNING",
            stage="guitar_authoring",
            message="Note remains review-required from source trust/alignment.",
            time_seconds=float(index),
            priority=68,
        )
        for index in range(2046)
    ]
    report = ValidationReport(
        status="WARNING",
        can_package=True,
        fail_count=0,
        warning_count=len(warnings),
        review_queue=warnings,
    )

    outputs = write_guitar_review_artifacts(report, project, arrangement="lead")
    summary = outputs["summary"].read_text(encoding="utf-8")

    assert "**Warnings:** 1 actionable warning group · 2046 underlying warning events" in summary
    assert outputs["flags"].is_file()


def test_cli_exposes_guitar_chart_validation_and_export() -> None:
    parser = build_parser()

    build_args = parser.parse_args(
        [
            "build-guitar-chart",
            "project",
            "--source",
            "source.json",
            "--instrument",
            "lead",
        ]
    )
    assert build_args.instrument == "lead"

    validate_args = parser.parse_args(["validate", "project", "--instrument", "rhythm"])
    assert validate_args.instrument == "rhythm"

    export_args = parser.parse_args(["export", "project", "--instrument", "lead"])
    assert export_args.instrument == "lead"
