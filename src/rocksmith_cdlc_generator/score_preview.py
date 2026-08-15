from __future__ import annotations

from pathlib import Path

from .alignment import AlignmentReport, map_source_time
from .score_fanout import ScoreFanoutManifest
from .score_mapping_review import load_score_for_mapping_review
from .shared_timeline import alignment_for_role
from .song_preview import PreviewArrangement, PreviewNoteEvent, SongPreviewSnapshot
from .source_import import ImportedSource


def _resolve_project_file(project: Path, relative: str, *, label: str) -> Path:
    candidate = (project / relative).resolve()
    if not candidate.is_relative_to(project):
        raise ValueError(f"{label} escaped project directory: {candidate}")
    if not candidate.is_file():
        raise FileNotFoundError(f"{label} not found: {candidate}")
    return candidate


def _same_timebase(left: ImportedSource, right: ImportedSource) -> bool:
    return (
        left.beat_times_seconds == right.beat_times_seconds
        and left.tempo_events == right.tempo_events
        and left.time_signatures == right.time_signatures
    )


def _mapped_note(report: AlignmentReport, note, *, event_index: int) -> PreviewNoteEvent:
    start = map_source_time(report, note.start_seconds)
    end = map_source_time(report, note.start_seconds + note.duration_seconds)
    if end <= start:
        raise ValueError("Shared timeline produced a non-positive preview note duration")
    return PreviewNoteEvent(
        event_index=event_index,
        start_seconds=start,
        duration_seconds=end - start,
        midi=note.midi,
        note_name=note.note_name,
        string_index=note.string_index,
        fret=note.fret,
        techniques=list(note.techniques),
        import_confidence=note.import_confidence,
        trust_class=note.trust_class,
        review_required=note.review_required,
    )


def load_score_fanout_preview_snapshot(project_dir: Path) -> SongPreviewSnapshot:
    """Load the current authoritative score fan-out onto the recording-audio clock.

    This accepts both Guitar Pro and MusicXML fan-out outputs. It requires the fan-out
    manifest to match the currently registered score snapshot and every imported track
    to match its human-confirmed role/track mapping. Synchronized preview also requires
    the current human-promoted shared score-to-recording timeline; score-clock note and
    beat positions are mapped through that authority before they reach the desktop UI.
    Nothing here accepts or mutates musical decisions; it is a read-only projection.
    """

    project = project_dir.expanduser().resolve()
    score = load_score_for_mapping_review(project)
    manifest_path = project / "sources" / "imported" / f"score-fanout-{score.source_sha256[:12]}.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("Current score fan-out manifest is not available yet")
    manifest = ScoreFanoutManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    if manifest.score_source_sha256 != score.source_sha256:
        raise ValueError("Score fan-out manifest does not match the registered score snapshot")
    if manifest.score_source_format != score.source_format:
        raise ValueError("Score fan-out format does not match the registered score source")

    arrangements: list[PreviewArrangement] = []
    canonical: ImportedSource | None = None
    canonical_alignment: AlignmentReport | None = None
    seen_roles: set[str] = set()

    for entry in manifest.arrangements:
        role = entry.role.value
        if role in seen_roles:
            raise ValueError(f"Score fan-out contains duplicate {role} arrangement")
        seen_roles.add(role)
        mapping = score.mapping_for(entry.role)
        if mapping is None or not mapping.human_confirmed:
            raise ValueError(f"{role} fan-out no longer has a human-confirmed score mapping")
        if mapping.source_track_index != entry.source_track_index:
            raise ValueError(f"{role} fan-out no longer matches the human-confirmed score track")

        output = _resolve_project_file(project, entry.output_json, label=f"{role.title()} fan-out output")
        imported = ImportedSource.read_json(output)
        if imported.provenance.source_sha256 != score.source_sha256:
            raise ValueError(f"{role} preview provenance does not match the registered score")
        if len(imported.tracks) != 1:
            raise ValueError(f"{role} preview output must contain exactly one track")
        track = imported.tracks[0]
        if track.source_track_index != entry.source_track_index or track.instrument != role:
            raise ValueError(f"{role} preview output does not match fan-out authority")
        if canonical is None:
            canonical = imported
        elif not _same_timebase(canonical, imported):
            raise ValueError("Score fan-out arrangements do not share one canonical preview timebase")

        # alignment_for_role validates that the current promoted shared timeline still
        # matches recording identity, registered score, mapping, and fan-out authority.
        # Refuse synchronized preview if that authority is unavailable or stale.
        alignment = alignment_for_role(project, entry.role)
        if canonical_alignment is None:
            canonical_alignment = alignment

        score_track = next(
            (candidate for candidate in score.tracks if candidate.source_track_index == entry.source_track_index),
            None,
        )
        part_name = track.name or (score_track.name if score_track is not None else None) or role.title()
        notes = [
            _mapped_note(alignment, note, event_index=index)
            for index, note in enumerate(track.notes)
        ]
        arrangements.append(
            PreviewArrangement(
                instrument=role,
                part_index=entry.source_track_index,
                part_id=f"track-{entry.source_track_index}",
                part_name=part_name,
                source_track_name=track.name,
                tuning_midi=(list(track.tuning_midi) if track.tuning_midi is not None else None),
                output_json=entry.output_json,
                note_count=len(notes),
                notes=notes,
                warnings=list(imported.warnings),
            )
        )

    if canonical is None or canonical_alignment is None:
        raise ValueError("Score fan-out manifest contains no arrangements")

    mapped_beats = [
        map_source_time(canonical_alignment, when)
        for when in canonical.beat_times_seconds
    ]
    mapped_tempos = [
        event.model_copy(
            update={"time_seconds": map_source_time(canonical_alignment, event.time_seconds)}
        )
        for event in canonical.tempo_events
    ]
    mapped_signatures = [
        event.model_copy(
            update={"time_seconds": map_source_time(canonical_alignment, event.time_seconds)}
        )
        for event in canonical.time_signatures
    ]
    return SongPreviewSnapshot(
        source_filename=score.source_filename,
        source_sha256=score.source_sha256,
        beat_times_seconds=mapped_beats,
        tempo_events=mapped_tempos,
        time_signatures=mapped_signatures,
        arrangements=arrangements,
    )
