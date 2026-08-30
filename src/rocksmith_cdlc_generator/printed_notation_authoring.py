from __future__ import annotations

from pathlib import Path
from typing import Any

from .beats import TempoMap
from .hashing import sha256_file
from .models import AudioMetadata, ProjectManifest
from .printed_notation_import import (
    PRINTED_NOTATION_ADAPTER_ID,
    PrintedNotationFixture,
    import_project_printed_notation,
    printed_notation_tempo_map,
)
from .reviewed_bass_authoring import (
    ReviewedBassAuthoringInput,
    bass_authoring_input_from_reviewed_export,
)
from .reviewed_export_events import ReviewedExportArrangement, ReviewedExportNote
from .reviewed_rocksmith_xml import (
    ReviewedRocksmithXmlInput,
    rocksmith_xml_input_from_reviewed_bass,
)
from .reviewed_rocksmith_xml_render import build_reviewed_rocksmith_xml
from .score_source import ArrangementRole
from .source_import import ImportedSource

_TRAILING_SECONDS = 2.0


class PrintedNotationAuthoringError(ValueError):
    pass


def reviewed_export_arrangement_from_printed_notation(
    imported: ImportedSource,
    *,
    source_output_json: str,
    source_output_sha256: str,
) -> ReviewedExportArrangement:
    """Bridge a printed-notation ``ImportedSource`` into the existing reviewed-export model.

    Printed-notation practice mode has no separate commercial recording to align
    against (see docs/printed-notation-tab-practice-mode.md): a recognized event's
    own timestamp, derived from deterministic_tempo_map.py, is already the
    authoritative chart timing. There is therefore no separate source-vs-reviewed
    timing projection to perform here -- ``reviewed_start/duration`` equal
    ``source_start/duration`` exactly. ``recording_sha256``/``score_sha256`` both
    point at the printed-notation source-output JSON itself: it is the one artifact
    that supplies both timing and notes in this mode, unlike the recording+score
    path this model was originally built for, which hashes two independent files.
    """

    if imported.provenance.importer != PRINTED_NOTATION_ADAPTER_ID:
        raise PrintedNotationAuthoringError(
            "reviewed export bridge requires a printed_notation_import.py-produced source"
        )
    if len(imported.tracks) != 1:
        raise PrintedNotationAuthoringError("printed notation source must contain exactly one track")

    track = imported.tracks[0]
    if track.instrument != "bass":
        raise PrintedNotationAuthoringError(
            "this slice supports only the printed-notation Bass authoring bridge"
        )

    notes = [
        ReviewedExportNote(
            source_event_index=index,
            source_start_seconds=note.start_seconds,
            source_duration_seconds=note.duration_seconds,
            reviewed_start_seconds=note.start_seconds,
            reviewed_duration_seconds=note.duration_seconds,
            midi=note.midi,
            note_name=note.note_name,
            string_index=note.string_index,
            fret=note.fret,
            techniques=list(note.techniques),
            import_confidence=note.import_confidence,
            trust_class=note.trust_class,
            review_required=note.review_required,
            position_ready=note.string_index is not None and note.fret is not None,
        )
        for index, note in enumerate(track.notes)
    ]

    return ReviewedExportArrangement(
        role=ArrangementRole.bass,
        source_track_index=track.source_track_index,
        source_output_json=source_output_json,
        source_output_sha256=source_output_sha256,
        recording_sha256=source_output_sha256,
        score_sha256=source_output_sha256,
        tuning_midi=tuple(track.tuning_midi) if track.tuning_midi else None,
        notes=notes,
        chord_groups=[],
        human_confirmed_timing=True,
    )


def printed_notation_bass_authoring_input(
    project_dir: Path, fixture_path: Path
) -> ReviewedBassAuthoringInput:
    """Import, project, and validate one printed-notation fixture for Bass authoring.

    Writes the canonical ``ImportedSource`` JSON into the project (reusing
    ``import_project_printed_notation``, the same durable-artifact convention every
    other importer follows) and validates it exactly as ``reviewed_bass_authoring.py``
    validates a recording+score project: unreviewed/unconfirmed events (source trust
    class other than ``symbolic_verified``/``user_confirmed``) are refused, not
    silently promoted. Mark a fixture event ``human_reviewed: true`` to promote it.
    """

    project_dir = project_dir.resolve()
    destination = import_project_printed_notation(project_dir, fixture_path)
    imported = ImportedSource.read_json(destination)
    arrangement = reviewed_export_arrangement_from_printed_notation(
        imported,
        source_output_json=destination.relative_to(project_dir).as_posix(),
        source_output_sha256=sha256_file(destination),
    )
    return bass_authoring_input_from_reviewed_export(arrangement)


def printed_notation_bass_rocksmith_xml_input(
    project_dir: Path, fixture_path: Path
) -> ReviewedRocksmithXmlInput:
    authoring = printed_notation_bass_authoring_input(project_dir, fixture_path)
    return rocksmith_xml_input_from_reviewed_bass(authoring)


def practice_manifest_for_printed_notation(
    fixture: PrintedNotationFixture,
    tempo_map: TempoMap,
    *,
    project_name: str,
    title: str,
    artist: str | None,
    source_path: Path,
    source_sha256: str,
) -> ProjectManifest:
    """Build the minimal ``ProjectManifest`` printed-notation XML rendering needs.

    Printed-notation practice mode (path B in the doc: "photo/scan/score only") has
    no separate commercial recording, so there is no independent audio file to
    describe in ``source_metadata``/``source_original_path``. Both instead describe
    the printed-notation source itself; the practice click track this doc calls for
    (``click_track_render.py``) becomes the project's actual audio reference, not an
    aligned commercial recording.
    """

    last_beat = tempo_map.beats[-1]
    seconds_per_beat = 60.0 / last_beat.bpm * (4.0 / tempo_map.time_signature_denominator)
    duration_seconds = last_beat.time + seconds_per_beat + _TRAILING_SECONDS

    return ProjectManifest(
        project_name=project_name,
        artist=artist,
        title=title,
        arrangement_instruments=["bass"],
        source_original_path=str(source_path),
        source_project_path=str(source_path),
        source_sha256=source_sha256,
        source_metadata=AudioMetadata(
            duration_seconds=duration_seconds,
            sample_rate_hz=tempo_map.sample_rate_hz,
            channels=1,
            codec_name="printed-notation-practice-click",
            format_name="synthesized",
        ),
    )


def build_printed_notation_bass_xml(
    project_dir: Path,
    fixture_path: Path,
    *,
    project_name: str,
    title: str,
    artist: str | None = None,
) -> Any:
    """End-to-end: fixture -> canonical import -> reviewed authoring -> Rocksmith Bass XML.

    Returns an ``xml.etree.ElementTree.Element`` only; writes no PSARC/CDLC package.
    """

    project_dir = project_dir.resolve()
    fixture = PrintedNotationFixture.read_json(fixture_path)
    tempo_map = printed_notation_tempo_map(fixture)
    xml_input = printed_notation_bass_rocksmith_xml_input(project_dir, fixture_path)
    manifest = practice_manifest_for_printed_notation(
        fixture,
        tempo_map,
        project_name=project_name,
        title=title,
        artist=artist,
        source_path=fixture_path,
        source_sha256=sha256_file(fixture_path),
    )
    return build_reviewed_rocksmith_xml(manifest, tempo_map, xml_input)
