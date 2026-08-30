from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .eof_rest_boundary_check import (
    EOF_UPSTREAM_COMMIT,
    EOF_UPSTREAM_FUNCTION,
    EOF_UPSTREAM_PATH,
    EOF_UPSTREAM_REPOSITORY,
    extract_explicit_rest_intervals,
)
from .eof_short_note_truncation_check import (
    EOF_DEFAULT_TRUNCATE_SHORT_CHORDS,
    EOF_DEFAULT_TRUNCATE_SHORT_NOTES,
    EOF_TRUNCATED_SUSTAIN_SECONDS,
    EOF_UPSTREAM_PREFERENCE_PATH,
    NOTE_IS_SHORT_DURATION_THRESHOLD_TICKS,
    _note_effect_has_nonzero_bend,
    _note_effect_has_slide,
    _note_effect_is_palm_mute,
    _note_effect_is_staccato,
    _note_effect_is_tremolo_picking,
    _note_effect_is_vibrato,
    _note_type_name,
    eof_truncation_decision,
)
from .guitarpro_import import (
    GuitarProImportError,
    _collect_tempo_points,
    _load_guitarpro,
    _normalized_tick,
    _string_map,
    _ticks_to_seconds,
)
from .hashing import sha256_file
from .reviewed_arrangement_timing import reviewed_arrangement_timing
from .reviewed_export_events import ReviewedExportArrangement, ReviewedExportNote, reviewed_export_arrangement
from .reviewed_timing_transform import map_reviewed_source_time
from .score_mapping_review import load_score_for_mapping_review
from .score_source import ArrangementRole

# This module is the third slice of docs/integrations/EOF_PARITY_ROADMAP.md item B: the first
# two slices (eof_rest_boundary_check.py, eof_short_note_truncation_check.py) both compare
# EOF-derived rules against the notes the generator's *importer* would directly extract from
# the registered Guitar Pro score. Neither evaluates what actually reaches the Rocksmith XML
# boundary after Bass reconciliation (reconciliation.py, audio-vs-symbolic evidence) or Lead/
# Rhythm shared-score arrangement materialization (score_role_composition.py,
# reviewed_export_events.reviewed_export_arrangement) project each source note onto promoted
# human-reviewed timing (reviewed_timing_transform.map_reviewed_source_time). A reconciliation
# or timing-projection step could in principle stretch a materialized sustain across a rest
# that was respected at import time, or fail to preserve EOF's short-note/staccato/mute
# truncation preference once the note's timing is re-expressed in reviewed/recording time.
#
# The upstream EOF behavior audited here is identical to the first two slices' own citations
# (raynebc/editor-on-fire, EOF_UPSTREAM_COMMIT, src/gp_import.c's eof_load_gp / src/main.c's
# import-preference defaults); this module does not re-audit EOF, it re-applies those same
# already-audited decisions -- reusing extract_explicit_rest_intervals and
# eof_truncation_decision directly rather than re-deriving them -- against a different,
# later stage of this project's own pipeline: the post-reconciliation/post-materialization
# ``ReviewedExportArrangement`` produced by ``reviewed_export_events.reviewed_export_arrangement``,
# the same read model every Bass/Lead/Rhythm authoring path (reviewed_bass_authoring.py,
# reviewed_guitar_authoring.py) and, downstream of that, reviewed_rocksmith_xml.py consume to
# build the note facts that are actually written into Rocksmith XML.
#
# Matching an exported/materialized note back to the specific registered-score beat/note EOF's
# rules were evaluated against uses (source_start_seconds, midi) rather than (string_index,
# fret): Bass reconciliation can choose a different physical string/fret for the same pitch
# (fret_mapping.py), so string/fret is not a stable join key across reconciliation, but pitch
# and source-relative onset time are. When a truncatable source note cannot be matched to
# exactly one exported note within tolerance, this check reports it as undeterminable rather
# than silently skipping it or guessing which candidate applies (fail-closed, per this
# project's advisory-check convention).
MATCH_TIME_TOLERANCE_SECONDS = 1e-4

NAVIGATION_NOTE = (
    "This check evaluates EOF-derived explicit-rest boundaries and short-note/staccato/mute "
    "truncation preferences (the same rules eof_rest_boundary_check.py and "
    "eof_short_note_truncation_check.py already apply to directly-imported note data) against "
    "the post-reconciliation/post-materialization notes reviewed_export_events."
    "reviewed_export_arrangement() produces for one role -- the same read model every Bass/"
    "Lead/Rhythm authoring path consumes on the way to the Rocksmith XML boundary. It closes "
    "the remaining scope docs/integrations/EOF_PARITY_ROADMAP.md item B named: whether "
    "generated/exported arrangement output, not just imported data, still respects these "
    "boundaries. A Lead/Rhythm arrangement composed from more than one contributing registered-"
    "score track is supported: each contributing track's own explicit rests and truncation-"
    "eligible notes are evaluated only against the materialized notes this check can resolve "
    "back to that same literal track (composition_source_track_index), never against another "
    "contributing track's unrelated passage. Section-boundary parity (the remaining phrase "
    "named in the roadmap acceptance target) is not evaluated here either: this project's "
    "Rocksmith authoring pipeline does not yet carry an EOF-comparable section/phrase model to "
    "check against (see roadmap item F)."
)

EVIDENCE_NOTE = (
    "EOF-derived generated/exported-arrangement-output boundary evidence. Advisory and "
    "source-bound only: it may reveal a reconciliation or timing-projection defect but never "
    "silently rewrites canonical chart, timing, or export authority."
)


class EOFExportBoundaryCheckError(ValueError):
    pass


class ExportedSourceNote(BaseModel):
    """One post-reconciliation/post-materialization note, decoupled from richer project models.

    Fields mirror the subset of ``reviewed_export_events.ReviewedExportNote`` this check
    needs. ``source_track_index`` must be the literal registered-score track index that
    produced this note (resolve composed multi-track provenance before constructing this).
    """

    model_config = ConfigDict(frozen=True)

    source_event_index: int = Field(ge=0)
    source_track_index: int = Field(ge=0)
    source_start_seconds: float = Field(ge=0)
    source_duration_seconds: float = Field(gt=0)
    reviewed_start_seconds: float = Field(ge=0)
    reviewed_duration_seconds: float = Field(gt=0)
    midi: int = Field(ge=0, le=127)
    string_index: int | None = Field(default=None, ge=0)
    fret: int | None = Field(default=None, ge=0)


class ExportRestBoundaryViolation(BaseModel):
    model_config = ConfigDict(frozen=True)

    note: ExportedSourceNote
    rest_reviewed_start_seconds: float = Field(ge=0)
    rest_reviewed_end_seconds: float = Field(ge=0)
    rest_source_measure_index: int = Field(ge=0)
    overlap_seconds: float = Field(gt=0)


class ExportTruncationMismatch(BaseModel):
    model_config = ConfigDict(frozen=True)

    note: ExportedSourceNote
    expected_reviewed_sustain_seconds: float = Field(ge=0)
    actual_reviewed_sustain_seconds: float = Field(gt=0)
    sustain_delta_seconds: float = Field(gt=0)


class EOFExportBoundaryReport(BaseModel):
    """Advisory comparison of materialized/exported note data against EOF-derived boundaries.

    Never rewrites canonical chart, timing, or export authority; see EVIDENCE_NOTE. Matches
    the remaining generated/exported-output scope of ``docs/integrations/EOF_PARITY_ROADMAP.md``
    item B.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    upstream_repository: str = EOF_UPSTREAM_REPOSITORY
    upstream_commit: str = EOF_UPSTREAM_COMMIT
    upstream_path: str = EOF_UPSTREAM_PATH
    upstream_function: str = EOF_UPSTREAM_FUNCTION
    upstream_preference_path: str = EOF_UPSTREAM_PREFERENCE_PATH
    source_sha256: str
    role: ArrangementRole
    track_indices: tuple[int, ...] = Field(min_length=1)
    truncate_short_notes: bool
    truncate_short_chords: bool
    explicit_rest_count: int = Field(ge=0)
    exported_note_count: int = Field(ge=0)
    eof_truncatable_source_event_count: int = Field(ge=0)
    rest_violations: list[ExportRestBoundaryViolation] = Field(default_factory=list)
    truncation_mismatches: list[ExportTruncationMismatch] = Field(default_factory=list)
    unmatched_truncatable_source_event_count: int = Field(ge=0)
    boundaries_respected: bool
    truncation_matches_eof_preferences: bool
    fully_determinable: bool
    reason: str
    navigation_note: str = NAVIGATION_NOTE
    evidence_note: str = EVIDENCE_NOTE

    @model_validator(mode="after")
    def track_indices_are_sorted_and_unique(self) -> "EOFExportBoundaryReport":
        if any(index < 0 for index in self.track_indices):
            raise ValueError("track indices must be non-negative")
        if list(self.track_indices) != sorted(set(self.track_indices)):
            raise ValueError("track indices must be sorted and unique")
        return self

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path


class _SourceTruncationFact(BaseModel):
    """One registered-score note's EOF truncation-relevant facts, from a raw beat/note walk."""

    model_config = ConfigDict(frozen=True)

    start_seconds: float = Field(ge=0)
    midi: int = Field(ge=0, le=127)
    eof_would_truncate: bool
    predicted_source_sustain_seconds: float = Field(gt=0)


def _extract_source_truncation_facts(
    track: Any,
    tempo_points: list[tuple[int, float]],
    *,
    truncate_short_notes: bool,
    truncate_short_chords: bool,
) -> list[_SourceTruncationFact]:
    """Walk one registered-score track and apply EOF's truncation decision to every note.

    Mirrors the beat/note walk ``guitarpro_import.convert_guitarpro_song`` and
    ``eof_short_note_truncation_check.compute_eof_short_note_truncation_check`` both use, but
    keeps pitch (``midi``) rather than string/fret so facts can be matched to a materialized
    note across a fret-mapping reconciliation that may have re-voiced its physical position.
    """

    _, _, open_pitch_by_number = _string_map(track)
    facts: list[_SourceTruncationFact] = []
    for measure in getattr(track, "measures", []) or []:
        for voice in getattr(measure, "voices", []) or []:
            for beat in getattr(voice, "beats", []) or []:
                beat_notes = list(getattr(beat, "notes", None) or [])
                if not beat_notes:
                    continue
                start_tick = _normalized_tick(getattr(beat, "start", 0))
                duration_obj = getattr(beat, "duration", None)
                duration_ticks = int(getattr(duration_obj, "time", 0) or 0)
                if duration_ticks <= 0:
                    continue
                start_seconds = _ticks_to_seconds(start_tick, tempo_points)
                end_seconds = _ticks_to_seconds(start_tick + duration_ticks, tempo_points)
                generator_sustain_seconds = end_seconds - start_seconds

                is_chord = len(beat_notes) > 1
                is_short_duration = duration_ticks < NOTE_IS_SHORT_DURATION_THRESHOLD_TICKS

                for source_note in beat_notes:
                    string_number = int(getattr(source_note, "string"))
                    if string_number not in open_pitch_by_number:
                        continue
                    fret = int(getattr(source_note, "value"))
                    midi = open_pitch_by_number[string_number] + fret

                    effect = getattr(source_note, "effect", None)
                    is_staccato = _note_effect_is_staccato(effect)
                    is_dead = _note_type_name(source_note) == "dead"
                    is_palm_mute = _note_effect_is_palm_mute(effect)
                    is_tremolo_picking = _note_effect_is_tremolo_picking(effect)
                    is_technique_exempt = (
                        _note_effect_has_nonzero_bend(effect)
                        or _note_effect_is_vibrato(effect)
                        or _note_effect_has_slide(effect)
                    )
                    is_fully_muted_or_palm_muted = (not is_chord) and (is_dead or is_palm_mute)

                    truncate = eof_truncation_decision(
                        is_chord=is_chord,
                        is_short_duration=is_short_duration,
                        is_staccato=is_staccato,
                        is_fully_muted_or_palm_muted=is_fully_muted_or_palm_muted,
                        is_tremolo_picking=is_tremolo_picking,
                        is_technique_exempt=is_technique_exempt,
                        truncate_short_notes=truncate_short_notes,
                        truncate_short_chords=truncate_short_chords,
                    )
                    predicted_source_sustain_seconds = (
                        EOF_TRUNCATED_SUSTAIN_SECONDS if truncate else generator_sustain_seconds
                    )
                    facts.append(
                        _SourceTruncationFact(
                            start_seconds=start_seconds,
                            midi=midi,
                            eof_would_truncate=truncate,
                            predicted_source_sustain_seconds=predicted_source_sustain_seconds,
                        )
                    )
    return facts


def _map_source_time(timing_points: list[tuple[float, float]], source_time_seconds: float) -> float:
    """Project one source-relative timestamp through reviewed timing.

    Reuses ``reviewed_timing_transform.map_reviewed_source_time``'s exact piecewise-linear
    interpolation via a lightweight duck-typed wrapper instead of re-deriving the projection,
    so this check always agrees with the same shared-timeline transform the real pipeline uses.
    """

    points = [
        SimpleNamespace(source_time_seconds=source, reviewed_time_seconds=reviewed)
        for source, reviewed in timing_points
    ]
    return map_reviewed_source_time(SimpleNamespace(points=points), source_time_seconds)


def compute_eof_export_boundary_check(
    song: Any,
    *,
    track_indices: Sequence[int],
    role: ArrangementRole,
    exported_notes: list[ExportedSourceNote],
    timing_points: list[tuple[float, float]],
    source_sha256: str,
    overlap_tolerance_seconds: float = 1e-6,
    sustain_delta_tolerance_seconds: float = 1e-6,
    match_time_tolerance_seconds: float = MATCH_TIME_TOLERANCE_SECONDS,
    truncate_short_notes: bool = EOF_DEFAULT_TRUNCATE_SHORT_NOTES,
    truncate_short_chords: bool = EOF_DEFAULT_TRUNCATE_SHORT_CHORDS,
) -> EOFExportBoundaryReport:
    """Compare materialized/exported note data against EOF-derived rest/truncation boundaries.

    ``song`` is the already-parsed registered Guitar Pro structure (``guitarpro.parse()``
    output); it is not re-parsed here. ``track_indices`` lists every literal registered-score
    track contributing to the arrangement -- more than one only for a composed multi-track
    Lead/Rhythm arrangement (``score_role_composition.py``); every ``exported_notes`` entry's
    ``source_track_index`` must be one of them. Each contributing track's own explicit rests
    and truncation-eligible notes are evaluated only against the materialized notes that
    resolve back to that same literal track, never against another contributing track's
    unrelated passage. ``timing_points`` is the promoted reviewed score-timing map as
    ``(source_time_seconds, reviewed_time_seconds)`` pairs, at least two, strictly increasing
    in both columns -- the same shared timeline ``exported_notes`` were themselves projected
    through.

    Pure function: deterministic, no I/O, no network, no dependency on a live EOF process or
    a live project.
    """

    if overlap_tolerance_seconds < 0:
        raise EOFExportBoundaryCheckError("overlap tolerance must be non-negative")
    if sustain_delta_tolerance_seconds < 0:
        raise EOFExportBoundaryCheckError("sustain delta tolerance must be non-negative")
    if match_time_tolerance_seconds < 0:
        raise EOFExportBoundaryCheckError("match time tolerance must be non-negative")
    if len(timing_points) < 2:
        raise EOFExportBoundaryCheckError("reviewed timing needs at least two score beats")
    source_times = [point[0] for point in timing_points]
    reviewed_times = [point[1] for point in timing_points]
    if source_times != sorted(source_times) or len(set(source_times)) != len(source_times):
        raise EOFExportBoundaryCheckError("reviewed timing source beats must be strictly increasing")
    if reviewed_times != sorted(reviewed_times) or len(set(reviewed_times)) != len(reviewed_times):
        raise EOFExportBoundaryCheckError("reviewed timing recording beats must be strictly increasing")

    resolved_track_indices = tuple(sorted(set(track_indices)))
    if not resolved_track_indices:
        raise EOFExportBoundaryCheckError("at least one contributing track index is required")
    known_track_indices = set(resolved_track_indices)
    if any(note.source_track_index not in known_track_indices for note in exported_notes):
        raise EOFExportBoundaryCheckError(
            "exported notes must all originate from one of this check's declared contributing "
            "tracks"
        )

    tracks = list(getattr(song, "tracks", []) or [])
    for track_index in resolved_track_indices:
        if track_index < 0 or track_index >= len(tracks):
            raise EOFExportBoundaryCheckError(f"track index {track_index} is outside 0..{len(tracks) - 1}")

    rests: list[Any] = []
    rest_violations: list[ExportRestBoundaryViolation] = []
    truncatable_facts: list[_SourceTruncationFact] = []
    truncation_mismatches: list[ExportTruncationMismatch] = []
    unmatched_count = 0

    # Each contributing track is evaluated independently -- its own explicit rests and
    # truncation-eligible notes are only ever compared against the materialized notes that
    # resolve back to that same literal track -- then results across all contributing tracks
    # are pooled into one report. A composed multi-track arrangement's tracks typically cover
    # disjoint passages of the same shared timeline, so cross-track comparison would be
    # meaningless at best and a false positive at worst.
    for track_index in resolved_track_indices:
        track = tracks[track_index]
        measures = list(getattr(track, "measures", []) or [])
        if not measures:
            raise EOFExportBoundaryCheckError(f"track index {track_index} has no measures")

        tempo_points = _collect_tempo_points(song, track)
        track_notes = [note for note in exported_notes if note.source_track_index == track_index]

        # --- Explicit rest boundary side: project every source rest into reviewed time and
        # check every exported/materialized note from this same track (already living in
        # reviewed time) for overlap.
        track_rests = extract_explicit_rest_intervals(track, tempo_points)
        rests.extend(track_rests)
        for rest in track_rests:
            rest_reviewed_start = _map_source_time(timing_points, rest.start_seconds)
            rest_reviewed_end = _map_source_time(timing_points, rest.end_seconds)
            for note in track_notes:
                note_end = note.reviewed_start_seconds + note.reviewed_duration_seconds
                overlap = min(note_end, rest_reviewed_end) - max(note.reviewed_start_seconds, rest_reviewed_start)
                if overlap > overlap_tolerance_seconds:
                    rest_violations.append(
                        ExportRestBoundaryViolation(
                            note=note,
                            rest_reviewed_start_seconds=rest_reviewed_start,
                            rest_reviewed_end_seconds=rest_reviewed_end,
                            rest_source_measure_index=rest.measure_index,
                            overlap_seconds=overlap,
                        )
                    )

        # --- Truncation preference side: apply EOF's decision to every note on this track, then
        # match each truncatable one to its materialized counterpart on the same track by
        # (source time, pitch) -- never string/fret, which Bass reconciliation may have
        # re-voiced -- and compare the materialized reviewed sustain against the reviewed-time
        # projection of EOF's predicted post-truncation source sustain.
        track_facts = _extract_source_truncation_facts(
            track,
            tempo_points,
            truncate_short_notes=truncate_short_notes,
            truncate_short_chords=truncate_short_chords,
        )
        track_truncatable_facts = [fact for fact in track_facts if fact.eof_would_truncate]
        truncatable_facts.extend(track_truncatable_facts)

        for fact in track_truncatable_facts:
            candidates = [
                note
                for note in track_notes
                if note.midi == fact.midi
                and abs(note.source_start_seconds - fact.start_seconds) <= match_time_tolerance_seconds
            ]
            if len(candidates) != 1:
                unmatched_count += 1
                continue
            note = candidates[0]
            expected_reviewed_start = _map_source_time(timing_points, fact.start_seconds)
            expected_reviewed_end = _map_source_time(
                timing_points, fact.start_seconds + fact.predicted_source_sustain_seconds
            )
            expected_reviewed_sustain = expected_reviewed_end - expected_reviewed_start
            delta = note.reviewed_duration_seconds - expected_reviewed_sustain
            if delta > sustain_delta_tolerance_seconds:
                truncation_mismatches.append(
                    ExportTruncationMismatch(
                        note=note,
                        expected_reviewed_sustain_seconds=expected_reviewed_sustain,
                        actual_reviewed_sustain_seconds=note.reviewed_duration_seconds,
                        sustain_delta_seconds=delta,
                    )
                )

    boundaries_respected = not rest_violations
    truncation_matches_eof_preferences = not truncation_mismatches
    fully_determinable = unmatched_count == 0
    composed = len(resolved_track_indices) > 1
    track_phrase = (
        f"{len(resolved_track_indices)} contributing tracks" if composed else "the selected track"
    )

    reason_parts: list[str] = []
    if not rests:
        reason_parts.append(f"No explicit rest beats were present in {track_phrase}.")
    elif boundaries_respected:
        reason_parts.append(
            f"{len(rests)} explicit rest beat(s) across {track_phrase} checked against "
            f"{len(exported_notes)} materialized note(s); no materialized sustain overlaps a "
            "projected rest boundary."
        )
    else:
        first = rest_violations[0]
        reason_parts.append(
            f"{len(rest_violations)} materialized-note/explicit-rest overlap(s) found: a "
            f"materialized note starting at {first.note.reviewed_start_seconds:.3f}s overlaps a "
            f"projected rest at {first.rest_reviewed_start_seconds:.3f}s-"
            f"{first.rest_reviewed_end_seconds:.3f}s by {first.overlap_seconds:.3f}s."
        )

    if not truncatable_facts:
        reason_parts.append(
            "No registered-score note meets EOF's configured short-note/staccato/mute "
            "truncation preferences, so no truncation evidence applies."
        )
    elif truncation_matches_eof_preferences and fully_determinable:
        reason_parts.append(
            f"{len(truncatable_facts)} EOF-truncatable registered-score note(s) matched a "
            "materialized note; every materialized sustain already collapses to EOF's "
            "predicted post-truncation result once reviewed timing is applied."
        )
    else:
        if truncation_mismatches:
            first_mismatch = truncation_mismatches[0]
            reason_parts.append(
                f"{len(truncation_mismatches)} of {len(truncatable_facts)} EOF-truncatable "
                "registered-score note(s) keep a longer materialized sustain than EOF's "
                f"preferences predict: a materialized note at "
                f"{first_mismatch.note.reviewed_start_seconds:.3f}s keeps "
                f"{first_mismatch.actual_reviewed_sustain_seconds:.3f}s instead of the "
                f"predicted {first_mismatch.expected_reviewed_sustain_seconds:.3f}s."
            )
        if unmatched_count:
            reason_parts.append(
                f"{unmatched_count} EOF-truncatable registered-score note(s) could not be "
                "matched to exactly one materialized note by (source time, pitch) on its own "
                "contributing track; this is expected for Bass notes that Bass reconciliation "
                "replaced or dropped based on audio evidence, but is reported rather than "
                "silently skipped because it may also mean the materialized note set has "
                "drifted from the registered score."
            )

    return EOFExportBoundaryReport(
        source_sha256=source_sha256,
        role=role,
        track_indices=resolved_track_indices,
        truncate_short_notes=truncate_short_notes,
        truncate_short_chords=truncate_short_chords,
        explicit_rest_count=len(rests),
        exported_note_count=len(exported_notes),
        eof_truncatable_source_event_count=len(truncatable_facts),
        rest_violations=rest_violations,
        truncation_mismatches=truncation_mismatches,
        unmatched_truncatable_source_event_count=unmatched_count,
        boundaries_respected=boundaries_respected,
        truncation_matches_eof_preferences=truncation_matches_eof_preferences,
        fully_determinable=fully_determinable,
        reason=" ".join(reason_parts),
    )


def _resolve_source_track_indices(arrangement: ReviewedExportArrangement) -> tuple[int, ...]:
    """Resolve every distinct literal registered-score track ``arrangement`` draws notes from.

    Returns more than one index exactly when ``arrangement`` is a composed multi-track Lead/
    Rhythm arrangement (``score_role_composition.py``); each returned index is independently
    checked against only the materialized notes that resolve back to it -- see NAVIGATION_NOTE
    and ``compute_eof_export_boundary_check``.
    """

    literal_indexes = {
        note.composition_source_track_index
        if note.composition_source_track_index is not None
        else arrangement.source_track_index
        for note in arrangement.notes
    }
    return tuple(sorted(literal_indexes))


def _exported_source_notes(arrangement: ReviewedExportArrangement) -> list[ExportedSourceNote]:
    def _resolved_event_index(note: ReviewedExportNote) -> int:
        return note.composition_source_event_index if note.composition_source_event_index is not None else note.source_event_index

    def _resolved_track_index(note: ReviewedExportNote) -> int:
        return (
            note.composition_source_track_index
            if note.composition_source_track_index is not None
            else arrangement.source_track_index
        )

    return [
        ExportedSourceNote(
            source_event_index=_resolved_event_index(note),
            source_track_index=_resolved_track_index(note),
            source_start_seconds=note.source_start_seconds,
            source_duration_seconds=note.source_duration_seconds,
            reviewed_start_seconds=note.reviewed_start_seconds,
            reviewed_duration_seconds=note.reviewed_duration_seconds,
            midi=note.midi,
            string_index=note.string_index,
            fret=note.fret,
        )
        for note in arrangement.notes
    ]


def analyze_reviewed_export_boundaries(
    project_dir: Path,
    role: ArrangementRole,
    *,
    truncate_short_notes: bool = EOF_DEFAULT_TRUNCATE_SHORT_NOTES,
    truncate_short_chords: bool = EOF_DEFAULT_TRUNCATE_SHORT_CHORDS,
    overlap_tolerance_seconds: float = 1e-6,
    sustain_delta_tolerance_seconds: float = 1e-6,
    match_time_tolerance_seconds: float = MATCH_TIME_TOLERANCE_SECONDS,
) -> EOFExportBoundaryReport:
    """Convenience I/O wrapper: read current project authority, then compute the pure report.

    Reuses this project's existing registered-score loading (``score_mapping_review.py``),
    reviewed-timing projection (``reviewed_arrangement_timing.py``), and post-reconciliation
    export projection (``reviewed_export_events.py``) rather than re-deriving any of them. It
    writes no review, timing, chart, or export authority and performs no packaging.
    """

    project = project_dir.expanduser().resolve()
    arrangement = reviewed_export_arrangement(project, role)
    timing = reviewed_arrangement_timing(project, role)
    if timing.score_sha256 != arrangement.score_sha256:
        raise EOFExportBoundaryCheckError(
            f"{role.value} reviewed timing does not match the reviewed export arrangement's score"
        )

    track_indices = _resolve_source_track_indices(arrangement)
    exported_notes = _exported_source_notes(arrangement)
    timing_points = [(point.source_time_seconds, point.reviewed_time_seconds) for point in timing.points]

    score = load_score_for_mapping_review(project)
    if score.source_sha256 != arrangement.score_sha256:
        raise EOFExportBoundaryCheckError("registered score does not match the reviewed export arrangement")
    stored = (project / score.imported_relative_path).resolve()
    if not stored.is_relative_to(project) or not stored.is_file() or sha256_file(stored) != score.source_sha256:
        raise EOFExportBoundaryCheckError("registered score source bytes do not match the project score contract")

    guitarpro = _load_guitarpro()
    try:
        song = guitarpro.parse(str(stored))
    except Exception as exc:  # noqa: BLE001 - mirrors guitarpro_import.import_guitarpro
        raise GuitarProImportError(f"Failed to parse Guitar Pro file: {stored.name}") from exc

    return compute_eof_export_boundary_check(
        song,
        track_indices=track_indices,
        role=role,
        exported_notes=exported_notes,
        timing_points=timing_points,
        source_sha256=arrangement.score_sha256,
        overlap_tolerance_seconds=overlap_tolerance_seconds,
        sustain_delta_tolerance_seconds=sustain_delta_tolerance_seconds,
        match_time_tolerance_seconds=match_time_tolerance_seconds,
        truncate_short_notes=truncate_short_notes,
        truncate_short_chords=truncate_short_chords,
    )
