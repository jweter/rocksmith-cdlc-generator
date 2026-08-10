from __future__ import annotations

import json
from pathlib import Path

from rocksmith_cdlc_generator.authoring_export import (
    export_project_bass_authoring,
    export_project_guitar_authoring,
)
from rocksmith_cdlc_generator.beats import BeatEvent, TempoMap, write_tempo_map
from rocksmith_cdlc_generator.build_staging import stage_build
from rocksmith_cdlc_generator.dlcbuilder import prepare_dlcbuilder_project
from rocksmith_cdlc_generator.fret_mapping import BassMapping, MappedNote, write_bass_mapping
from rocksmith_cdlc_generator.fretboard import E_STANDARD
from rocksmith_cdlc_generator.guitar_authoring import GuitarAuthoringChart, GuitarAuthoringNote
from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.source_import import SourceTrustClass
from rocksmith_cdlc_generator.transcription import BassTranscription, NoteEvent, write_transcription


def _tempo() -> TempoMap:
    return TempoMap(
        engine="fixture",
        time_signature_numerator=4,
        time_signature_denominator=4,
        beats=[
            BeatEvent(time=0.5, beat=1, measure=1, bpm=120.0, confidence=0.99, is_downbeat=True),
            BeatEvent(time=1.0, beat=2, measure=1, bpm=120.0, confidence=0.99),
            BeatEvent(time=1.5, beat=3, measure=1, bpm=120.0, confidence=0.99),
            BeatEvent(time=2.0, beat=4, measure=1, bpm=120.0, confidence=0.99),
        ],
    )


def _guitar_note(start: float, string_index: int, fret: int, midi: int) -> GuitarAuthoringNote:
    return GuitarAuthoringNote(
        start_seconds=start,
        duration_seconds=0.35,
        midi=midi,
        string_index=string_index,
        fret=fret,
        trust_class=SourceTrustClass.user_confirmed,
    )


def _write_project_fixture(project: Path) -> None:
    project.mkdir(parents=True)
    ProjectManifest(
        project_name="three-arrangement-fixture",
        artist="Fixture Artist",
        title="Fixture Song",
        arrangement_instruments=["bass", "lead", "rhythm"],
        source_original_path="fixture.wav",
        source_project_path="source/fixture.wav",
        source_sha256="a" * 64,
        source_metadata=AudioMetadata(
            duration_seconds=8.0,
            sample_rate_hz=44100,
            channels=2,
            codec_name="pcm_s16le",
            format_name="wav",
        ),
    ).save(project)

    write_tempo_map(_tempo(), project / "analysis" / "tempo_map.json")
    write_transcription(
        BassTranscription(
            engine="fixture",
            source_path="audio/normalized.wav",
            sample_rate_hz=44100,
            notes=[
                NoteEvent(
                    start=1.0,
                    duration=0.35,
                    midi=40,
                    confidence=0.99,
                    pitch_confidence=0.99,
                    timing_confidence=0.99,
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
                    duration=0.35,
                    midi=40,
                    string=0,
                    fret=12,
                    source_confidence=0.99,
                    mapping_confidence=1.0,
                    position_source="symbolic",
                )
            ],
        ),
        project / "charts" / "bass_mapped.json",
    )

    GuitarAuthoringChart(
        arrangement="lead",
        source_sha256="b" * 64,
        alignment_confidence=1.0,
        tuning_midi=(40, 45, 50, 55, 59, 64),
        single_notes=[_guitar_note(1.0, 0, 5, 45)],
    ).write_json(project / "charts" / "lead_source.json")

    GuitarAuthoringChart(
        arrangement="rhythm",
        source_sha256="c" * 64,
        alignment_confidence=1.0,
        tuning_midi=(38, 45, 50, 55, 59, 64),
        single_notes=[_guitar_note(1.5, 0, 5, 43)],
    ).write_json(project / "charts" / "rhythm_source.json")

    audio_dir = project / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    (audio_dir / "normalized.wav").write_bytes(b"fixture-audio")
    (project / "preview.wav").write_bytes(b"fixture-preview")
    (project / "cover.png").write_bytes(b"fixture-cover")


def test_three_arrangement_export_prepare_and_stage(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_project_fixture(project)

    bass = export_project_bass_authoring(project)
    lead = export_project_guitar_authoring(project, arrangement="lead")
    rhythm = export_project_guitar_authoring(project, arrangement="rhythm")

    assert bass["xml"].name == "arr_bass_RS2.xml"
    assert lead["xml"].name == "arr_lead_RS2.xml"
    assert rhythm["xml"].name == "arr_rhythm_RS2.xml"

    rs2dlc = prepare_dlcbuilder_project(
        project,
        album_name="Fixture Album",
        year=2026,
        cover=project / "cover.png",
        preview=project / "preview.wav",
        preview_start_seconds=1.0,
    )

    payload = json.loads(rs2dlc.read_text(encoding="utf-8"))
    instrumentals = [item["Fields"][0] for item in payload["Arrangements"] if item["Case"] == "Instrumental"]
    assert [(item["Name"], item["RouteMask"]) for item in instrumentals] == [(0, 1), (2, 2), (3, 4)]
    assert [item["Tuning"] for item in instrumentals] == [
        [0, 0, 0, 0, 0, 0],
        [-2, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0],
    ]

    stage_manifest_path = stage_build(project, dlcbuilder_project=rs2dlc)
    stage_payload = json.loads(stage_manifest_path.read_text(encoding="utf-8"))
    roles = {asset["role"] for asset in stage_payload["assets"]}
    assert roles == {
        "song_audio",
        "preview_audio",
        "album_art",
        "lead_xml",
        "rhythm_xml",
        "bass_xml",
    }
    assert stage_payload["validation_status"] == "PASS"
    assert stage_payload["safe_for_manual_packaging"] is True
    assert stage_payload["writes_to_live_rocksmith_install"] is False
