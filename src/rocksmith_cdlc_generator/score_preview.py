from __future__ import annotations

from pathlib import Path

from .alignment import AlignmentReport, map_source_time
from .reviewed_event_timing import timing_overrides_for_arrangement
from .reviewed_positions import apply_reviewed_positions, resolve_composed_review_entry
from .reviewed_techniques import apply_reviewed_techniques_to_source
from .score_fanout import ScoreFanoutManifest
from .score_mapping_review import load_score_for_mapping_review
from .shared_timeline import alignment_for_role
from .song_preview import PreviewArrangement, PreviewNoteEvent, SongPreviewSnapshot
from .source_import import ImportedSource
from .tie_continuation_analysis import exact_tie_review_exempt_event_indexes
from .track_trust_projection import apply_current_track_source_trust


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


def _mapped_note(
    report: AlignmentReport,
    note,
    *,
    event_index: int,
    timing_override: tuple[float, float] | None = None,
    review_required: bool | None = None,
) -> PreviewNoteEvent:
    if timing_override is None:
        start = map_source_time(report, note.start_seconds)
        end = map_source_time(report, note.start_seconds + note.duration_seconds)
    else:
        start, duration = timing_override
        end = start + duration
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
        review_required=note.review_required if review_required is None else review_required,
    )


def load_score_fanout_preview_snapshot(project_dir: Path) -> SongPreviewSnapshot:
    """Load current score fan-out onto the recording clock with current human overlays."""

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

    arrangements: list[PreviewArrangement] = []
    canonical: ImportedSource | None = None
    canonical_alignment: AlignmentReport | None = None

    for entry in manifest.arrangements:
        role = entry.role.value
        entry = resolve_composed_review_entry(project, role, score=score, entry=entry)
        output = _resolve_project_file(project, entry.output_json, label=f"{role.title()} fan-out output")
        imported = ImportedSource.read_json(output)
        if imported.provenance.source_sha256 != score.source_sha256:
            raise ValueError(f"{role} preview provenance does not match the registered score")
        if len(imported.tracks) != 1:
            raise ValueError(f"{role} preview output must contain exactly one track")
        original_track = imported.tracks[0]
        if original_track.source_track_index != entry.source_track_index or original_track.instrument != role:
            raise ValueError(f"{role} preview output does not match fan-out authority")
        if canonical is None:
            canonical = imported
        elif not _same_timebase(canonical, imported):
            raise ValueError("Score fan-out arrangements do not share one canonical preview timebase")

        # A provenance-bound whole-track source acceptance may upgrade only the copied
        # preview trust class. Persisted fan-out trust/review flags remain unchanged,
        # and independent tie/technique/timing review still fails closed below.
        imported, _track_trust_applied = apply_current_track_source_trust(
            project,
            imported,
            arrangement=role,
            source_track_index=entry.source_track_index,
        )

        # Exact Guitar Pro tie continuations are mechanically provable source facts.
        # Remove only that redundant human-review pressure in the preview read model;
        # source bytes and their persisted review_required flags remain untouched.
        tie_review_exemptions = exact_tie_review_exempt_event_indexes(imported)

        alignment = alignment_for_role(project, entry.role)
        if canonical_alignment is None:
            canonical_alignment = alignment

        reviewed_source, _reviewed_indices = apply_reviewed_positions(
            project,
            imported,
            arrangement=role,
            source_track_index=entry.source_track_index,
        )
        reviewed_source, _reviewed_technique_indices = apply_reviewed_techniques_to_source(
            project,
            reviewed_source,
            arrangement=role,
            source_track_index=entry.source_track_index,
            allow_stale_as_unreviewed=True,
        )
        timing_overrides = timing_overrides_for_arrangement(
            project,
            arrangement=role,
            source_track_index=entry.source_track_index,
        )
        track = reviewed_source.tracks[0]
        score_track = next(
            (candidate for candidate in score.tracks if candidate.source_track_index == entry.source_track_index),
            None,
        )
        part_name = track.name or (score_track.name if score_track is not None else None) or role.title()
        notes = [
            _mapped_note(
                alignment,
                note,
                event_index=index,
                timing_override=timing_overrides.get(index),
                review_required=(False if index in tie_review_exemptions else None),
            )
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
                warnings=list(reviewed_source.warnings),
            )
        )

    if canonical is None or canonical_alignment is None:
        raise ValueError("Score fan-out manifest contains no arrangements")

    mapped_beats = [map_source_time(canonical_alignment, when) for when in canonical.beat_times_seconds]
    mapped_tempos = [
        event.model_copy(update={"time_seconds": map_source_time(canonical_alignment, event.time_seconds)})
        for event in canonical.tempo_events
    ]
    mapped_signatures = [
        event.model_copy(update={"time_seconds": map_source_time(canonical_alignment, event.time_seconds)})
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
