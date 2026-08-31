from __future__ import annotations

from pathlib import Path
from typing import Any
import os
import xml.etree.ElementTree as ET

from .beats import TempoMap
from .click_track_render import count_in_offset_seconds, render_click_track_wav
from .hashing import sha256_file
from .models import AudioMetadata, ProjectManifest
from .official_tab_reference import (
    OfficialTabReferenceHit,
    manifest_path as reference_manifest_path,
    register_reference_page,
)
from .printed_notation_import import (
    PRINTED_NOTATION_ADAPTER_ID,
    PrintedNotationFixture,
    import_project_printed_notation,
    printed_notation_tempo_map,
)
from .printed_notation_validation import (
    check_click_track_measure_alignment,
    check_printed_notation_sustain_boundaries,
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
_PRACTICE_OUTPUT_DIRNAME = "printed_notation"


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


def register_printed_notation_page_image(
    project_dir: Path,
    fixture: PrintedNotationFixture,
    page_image: Path,
) -> OfficialTabReferenceHit:
    """Register a printed-notation source page as private reference evidence.

    Reuses official_tab_reference.py (built for issue #453's TAB viewer) rather than
    inventing a second private-image store: hashing, dedupe, and copy-into-project all
    come from that existing module. This slice supports only single-page fixtures; a
    multi-page fixture would need one registration call per page (doc phase N8's
    multi-page assembly, not yet built).
    """

    if len(fixture.pages) != 1:
        raise PrintedNotationAuthoringError(
            "page-image registration currently supports single-page fixtures only"
        )
    page = fixture.pages[0]
    measures = [event.measure for event in page.events]
    return register_reference_page(
        project_dir,
        page_image,
        arrangement=ArrangementRole.bass,
        measure_start=min(measures),
        measure_end=max(measures),
        printed_page=str(page.page_number),
    )


def _shift_tempo_map(tempo_map: TempoMap, offset_seconds: float) -> TempoMap:
    """Return a copy of ``tempo_map`` with every beat time shifted by ``offset_seconds``.

    Pairs with ``_shift_arrangement`` to align an XML chart with a click-track WAV
    whose count-in silence pushes chart beat 1 to ``offset_seconds`` in the audio (see
    ``count_in_offset_seconds``'s docstring): the WAV and an unshifted tempo map do not
    share a clock on their own.
    """

    return tempo_map.model_copy(
        update={
            "beats": [
                beat.model_copy(update={"time": beat.time + offset_seconds})
                for beat in tempo_map.beats
            ]
        }
    )


def _shift_arrangement(
    arrangement: ReviewedExportArrangement, offset_seconds: float
) -> ReviewedExportArrangement:
    """Return a copy of ``arrangement`` with every note's reviewed start time shifted.

    The canonical (unshifted) arrangement remains the one written to the project and
    used for sustain-boundary validation, which is unaffected by a constant shift; only
    the copy used to author the paired XML needs to move with the click track's offset.
    """

    return arrangement.model_copy(
        update={
            "notes": [
                note.model_copy(
                    update={"reviewed_start_seconds": note.reviewed_start_seconds + offset_seconds}
                )
                for note in arrangement.notes
            ]
        }
    )


def import_project_printed_notation_practice(
    project_dir: Path,
    fixture_path: Path,
    *,
    title: str,
    artist: str,
    project_name: str | None = None,
    page_image: Path | None = None,
    count_in_measures: int = 2,
    subdivision: str | None = None,
) -> dict[str, Path]:
    """End-to-end CLI entry point: fixture (+ optional page image) -> a validated Rocksmith
    Bass practice XML plus a paired count-in click-track WAV, written under
    PROJECT/printed_notation/.

    Fails closed: a sustain-boundary or click-alignment violation (see
    printed_notation_validation.py) raises rather than writing a possibly-broken
    practice package. This is the CLI orchestration the doc's plan calls for; it does
    not introduce any new musical/timing logic of its own.
    """

    project_dir = project_dir.resolve()
    fixture_path = fixture_path.resolve()
    fixture = PrintedNotationFixture.read_json(fixture_path)
    tempo_map = printed_notation_tempo_map(fixture)
    offset_seconds = count_in_offset_seconds(tempo_map, count_in_measures)

    destination = import_project_printed_notation(project_dir, fixture_path)
    imported = ImportedSource.read_json(destination)
    arrangement = reviewed_export_arrangement_from_printed_notation(
        imported,
        source_output_json=destination.relative_to(project_dir).as_posix(),
        source_output_sha256=sha256_file(destination),
    )

    sustain_report = check_printed_notation_sustain_boundaries(arrangement)
    if not sustain_report.boundaries_respected:
        raise PrintedNotationAuthoringError(
            f"printed-notation sustain validation failed: {sustain_report.reason}"
        )

    # The paired click-track WAV places chart beat 1 at `offset_seconds` (count-in
    # silence precedes it there); shift the XML's tempo map and note timing by the same
    # amount so the chart and audio share one clock instead of the chart leading the
    # audio by the count-in's length.
    xml_tempo_map = _shift_tempo_map(tempo_map, offset_seconds)
    xml_arrangement = _shift_arrangement(arrangement, offset_seconds)
    authoring = bass_authoring_input_from_reviewed_export(xml_arrangement)
    xml_input = rocksmith_xml_input_from_reviewed_bass(authoring)
    manifest = practice_manifest_for_printed_notation(
        fixture,
        xml_tempo_map,
        project_name=project_name or project_dir.name,
        title=title,
        artist=artist,
        source_path=fixture_path,
        source_sha256=sha256_file(fixture_path),
    )
    root = build_reviewed_rocksmith_xml(manifest, xml_tempo_map, xml_input)

    output_dir = project_dir / _PRACTICE_OUTPUT_DIRNAME
    output_dir.mkdir(parents=True, exist_ok=True)

    # Stage the click track under a temp name and validate it before touching any
    # existing output: a rerun that fails validation must leave the prior XML/click/
    # reports untouched rather than replacing some of them with a mismatched set.
    click_tmp_path = output_dir / ".click.wav.tmp"
    render_click_track_wav(
        tempo_map, click_tmp_path, count_in_measures=count_in_measures, subdivision=subdivision
    )
    alignment_report = check_click_track_measure_alignment(
        tempo_map, click_tmp_path, count_in_measures=count_in_measures
    )
    if not alignment_report.aligned:
        click_tmp_path.unlink(missing_ok=True)
        raise PrintedNotationAuthoringError(
            f"printed-notation click-alignment validation failed: {alignment_report.reason}"
        )

    xml_path = output_dir / "arr_bass_RS2.xml"
    ET.ElementTree(root).write(xml_path, encoding="UTF-8", xml_declaration=True)

    click_path = output_dir / "click.wav"
    os.replace(click_tmp_path, click_path)

    outputs: dict[str, Path] = {
        "xml": xml_path,
        "click_wav": click_path,
        "sustain_report": sustain_report.write_json(output_dir / "sustain_report.json"),
        "click_alignment_report": alignment_report.write_json(
            output_dir / "click_alignment_report.json"
        ),
    }
    if page_image is not None:
        register_printed_notation_page_image(project_dir, fixture, page_image)
        outputs["reference_manifest"] = reference_manifest_path(project_dir)
    return outputs
