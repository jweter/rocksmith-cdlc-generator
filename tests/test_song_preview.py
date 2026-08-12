from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator.musicxml_multi_import import (
    MusicXMLArrangementImportManifest,
    MusicXMLArrangementManifestEntry,
)
from rocksmith_cdlc_generator.song_preview import (
    build_preview_timeline_window,
    load_musicxml_preview_snapshot,
)
from rocksmith_cdlc_generator.source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTempoEvent,
    SourceTimeSignatureEvent,
    SourceTrack,
    SourceTrustClass,
)


SOURCE_SHA = "a" * 64


def _imported(
    *,
    instrument: str,
    part_index: int,
    name: str,
    tuning: list[int],
    midi: int,
    beat_times: list[float] | None = None,
    source_sha256: str = SOURCE_SHA,
) -> ImportedSource:
    return ImportedSource(
        provenance=SourceProvenance(
            source_type="musicxml",
            source_filename="song.musicxml",
            source_sha256=source_sha256,
            importer="test",
            importer_version="1",
        ),
        ticks_per_beat=480,
        tempo_events=[SourceTempoEvent(tick=0, time_seconds=0.0, bpm=120.0)],
        time_signatures=[
            SourceTimeSignatureEvent(
                tick=0,
                time_seconds=0.0,
                numerator=4,
                denominator=4,
            )
        ],
        beat_times_seconds=beat_times or [0.0, 0.5, 1.0],
        tracks=[
            SourceTrack(
                source_track_index=part_index,
                name=name,
                instrument=instrument,
                tuning_midi=tuning,
                notes=[
                    SourceNoteEvent(
                        start_seconds=0.5,
                        duration_seconds=0.25,
                        midi=midi,
                        note_name="E4" if midi == 64 else "E2",
                        string_index=0,
                        fret=0,
                        techniques=["accent"],
                        import_confidence=0.92,
                        trust_class=SourceTrustClass.symbolic_unverified,
                        review_required=True,
                    )
                ],
            )
        ],
        warnings=[f"review {instrument}"],
    )


def _project(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "project"
    imported_dir = project / "sources" / "imported"
    imported_dir.mkdir(parents=True)

    lead_path = imported_dir / "lead.json"
    bass_path = imported_dir / "bass.json"
    _imported(
        instrument="lead",
        part_index=0,
        name="Lead Guitar",
        tuning=[40, 45, 50, 55, 59, 64],
        midi=64,
    ).write_json(lead_path)
    _imported(
        instrument="bass",
        part_index=2,
        name="Electric Bass",
        tuning=[28, 33, 38, 43],
        midi=40,
    ).write_json(bass_path)

    manifest = MusicXMLArrangementImportManifest(
        source_filename="song.musicxml",
        source_sha256=SOURCE_SHA,
        arrangements=[
            MusicXMLArrangementManifestEntry(
                instrument="lead",
                part_index=0,
                part_id="P1",
                part_name="Lead Guitar",
                tuning_midi=[40, 45, 50, 55, 59, 64],
                pitched_note_count=1,
                output_json="sources/imported/lead.json",
            ),
            MusicXMLArrangementManifestEntry(
                instrument="bass",
                part_index=2,
                part_id="P3",
                part_name="Electric Bass",
                tuning_midi=[28, 33, 38, 43],
                pitched_note_count=1,
                output_json="sources/imported/bass.json",
            ),
        ],
    )
    manifest_path = imported_dir / "musicxml-arrangements-test.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return project, manifest_path


def test_loads_gui_friendly_preview_snapshot(tmp_path: Path) -> None:
    project, manifest_path = _project(tmp_path)

    snapshot = load_musicxml_preview_snapshot(project, manifest_path)

    assert snapshot.source_filename == "song.musicxml"
    assert snapshot.source_sha256 == SOURCE_SHA
    assert snapshot.beat_times_seconds == [0.0, 0.5, 1.0]
    assert [item.instrument for item in snapshot.arrangements] == ["lead", "bass"]

    lead = snapshot.arrangements[0]
    assert lead.part_name == "Lead Guitar"
    assert lead.note_count == 1
    assert lead.notes[0].event_index == 0
    assert lead.notes[0].start_seconds == 0.5
    assert lead.notes[0].midi == 64
    assert lead.notes[0].string_index == 0
    assert lead.notes[0].fret == 0
    assert lead.notes[0].techniques == ["accent"]
    assert lead.notes[0].import_confidence == 0.92
    assert lead.notes[0].review_required is True


def test_builds_read_only_timeline_window(tmp_path: Path) -> None:
    project, manifest_path = _project(tmp_path)
    snapshot = load_musicxml_preview_snapshot(project, manifest_path)

    window = build_preview_timeline_window(snapshot, 0.4, 0.6)

    assert window.start_seconds == 0.4
    assert window.end_seconds == 0.6
    assert window.beat_times_seconds == [0.5]
    assert [lane.instrument for lane in window.lanes] == ["lead", "bass"]
    assert window.lanes[0].tuning_midi == [40, 45, 50, 55, 59, 64]
    assert window.lanes[0].review_required_count == 1
    assert window.lanes[0].notes[0].event_index == 0
    assert window.lanes[0].notes[0].end_seconds == 0.75

    window.lanes[0].notes[0].techniques.append("preview-only")
    assert snapshot.arrangements[0].notes[0].techniques == ["accent"]


def test_timeline_window_keeps_notes_that_overlap_left_edge(tmp_path: Path) -> None:
    project, manifest_path = _project(tmp_path)
    snapshot = load_musicxml_preview_snapshot(project, manifest_path)

    window = build_preview_timeline_window(snapshot, 0.6, 0.7)

    assert [note.event_index for note in window.lanes[0].notes] == [0]


def test_rejects_invalid_timeline_window(tmp_path: Path) -> None:
    project, manifest_path = _project(tmp_path)
    snapshot = load_musicxml_preview_snapshot(project, manifest_path)

    with pytest.raises(ValueError, match="non-negative"):
        build_preview_timeline_window(snapshot, -0.1, 1.0)
    with pytest.raises(ValueError, match="greater than or equal"):
        build_preview_timeline_window(snapshot, 1.0, 0.5)


def test_rejects_arrangement_path_escape(tmp_path: Path) -> None:
    project, manifest_path = _project(tmp_path)
    payload = MusicXMLArrangementImportManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    payload.arrangements[0].output_json = "../outside.json"
    manifest_path.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
    (tmp_path / "outside.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="escaped project directory"):
        load_musicxml_preview_snapshot(project, manifest_path)


def test_rejects_provenance_mismatch(tmp_path: Path) -> None:
    project, manifest_path = _project(tmp_path)
    lead_path = project / "sources" / "imported" / "lead.json"
    _imported(
        instrument="lead",
        part_index=0,
        name="Lead Guitar",
        tuning=[40, 45, 50, 55, 59, 64],
        midi=64,
        source_sha256="b" * 64,
    ).write_json(lead_path)

    with pytest.raises(ValueError, match="provenance does not match"):
        load_musicxml_preview_snapshot(project, manifest_path)


def test_rejects_mixed_arrangement_timebases(tmp_path: Path) -> None:
    project, manifest_path = _project(tmp_path)
    bass_path = project / "sources" / "imported" / "bass.json"
    _imported(
        instrument="bass",
        part_index=2,
        name="Electric Bass",
        tuning=[28, 33, 38, 43],
        midi=40,
        beat_times=[0.0, 0.51, 1.02],
    ).write_json(bass_path)

    with pytest.raises(ValueError, match="canonical preview timebase"):
        load_musicxml_preview_snapshot(project, manifest_path)


def test_rejects_manifest_note_count_drift(tmp_path: Path) -> None:
    project, manifest_path = _project(tmp_path)
    payload = MusicXMLArrangementImportManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    payload.arrangements[0].pitched_note_count = 2
    manifest_path.write_text(payload.model_dump_json(indent=2), encoding="utf-8")

    with pytest.raises(ValueError, match="note count does not match"):
        load_musicxml_preview_snapshot(project, manifest_path)
