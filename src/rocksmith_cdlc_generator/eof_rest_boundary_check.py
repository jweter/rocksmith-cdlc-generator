from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .guitarpro_import import (
    ArrangementKind,
    GuitarProImportError,
    _collect_tempo_points,
    _load_guitarpro,
    _normalized_tick,
    _ticks_to_seconds,
    select_arrangement_track,
)
from .hashing import sha256_file

EOF_UPSTREAM_REPOSITORY = "raynebc/editor-on-fire"
EOF_UPSTREAM_COMMIT = "c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100"
EOF_UPSTREAM_PATH = "src/gp_import.c"
EOF_UPSTREAM_FUNCTION = "eof_load_gp"

# raynebc/editor-on-fire src/gp_import.c (audited at EOF_UPSTREAM_COMMIT, inside
# EOF_UPSTREAM_FUNCTION) reads a per-beat "is a rest" bitmask bit followed by a rest-type byte
# that distinguishes an "empty" beat (no notes were authored and no rest symbol was written)
# from a "rest" beat (the score explicitly notates silence) -- but EOF discards that byte's
# value without branching on it: either way, no note is created for that beat. The realized
# invariant is therefore emergent rather than a ported algorithm: EOF's parser structurally
# never produces a note event that occupies a beat with no notes, explicit rest or otherwise.
#
# PyGuitarPro's own parsed object model already normalizes the same empty/rest/normal
# distinction onto every Beat as `status`, a `BeatStatus` enum (see PyGuitarPro's
# `guitarpro/models.py`). This check reproduces EOF's structural invariant for this project's
# own importer by cross-checking the note intervals it would extract (mirroring
# guitarpro_import.convert_guitarpro_song's own beat walk) against every beat whose `status`
# is explicitly `rest`; an `empty` beat carries no authored musical meaning and is not checked.
_EXPLICIT_REST_STATUS_NAME = "rest"

NAVIGATION_NOTE = (
    "This check only evaluates explicit rest beats (BeatStatus.rest) against the note "
    "intervals the generator's own current importer would extract (guitarpro_import."
    "convert_guitarpro_song silently omits beats with no notes, so today no explicit-rest "
    "boundary is independently verified at all). It does not evaluate EOF's separate "
    "short-note/staccato/mute sustain-truncation preferences in src/gp_import.c (the "
    "'note_is_short'/truncation logic later in eof_load_gp), which remain unaudited and out "
    "of scope for this slice."
)

EVIDENCE_NOTE = (
    "EOF-derived explicit-rest boundary evidence. Advisory and source-bound only: it may reveal "
    "a generator sustain defect but never silently rewrites canonical chart state."
)


class EOFRestBoundaryCheckError(ValueError):
    pass


class ExplicitRestInterval(BaseModel):
    """One explicitly authored rest beat's realtime interval in the selected track."""

    model_config = ConfigDict(frozen=True)

    measure_index: int = Field(ge=0)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)


class NoteInterval(BaseModel):
    """One imported note's realtime interval, independent of source_import.py's richer model."""

    model_config = ConfigDict(frozen=True)

    measure_index: int = Field(ge=0)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    string_number: int
    fret: int = Field(ge=0)


class RestBoundaryViolation(BaseModel):
    model_config = ConfigDict(frozen=True)

    note: NoteInterval
    rest: ExplicitRestInterval
    overlap_seconds: float = Field(gt=0)


class EOFRestBoundaryReport(BaseModel):
    """Advisory comparison of imported note sustains against EOF-derived explicit rest bounds.

    Never rewrites canonical chart state; see EVIDENCE_NOTE. Matches the design principle in
    ``docs/integrations/EOF_PARITY_ROADMAP.md`` item B ("explicit rests must remain empty").
    """

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    upstream_repository: str = EOF_UPSTREAM_REPOSITORY
    upstream_commit: str = EOF_UPSTREAM_COMMIT
    upstream_path: str = EOF_UPSTREAM_PATH
    upstream_function: str = EOF_UPSTREAM_FUNCTION
    source_sha256: str
    track_index: int = Field(ge=0)
    explicit_rest_count: int = Field(ge=0)
    note_count: int = Field(ge=0)
    violations: list[RestBoundaryViolation] = Field(default_factory=list)
    boundaries_respected: bool
    reason: str
    navigation_note: str = NAVIGATION_NOTE
    evidence_note: str = EVIDENCE_NOTE

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path


def extract_explicit_rest_intervals(
    track: Any,
    tempo_points: list[tuple[int, float]],
) -> list[ExplicitRestInterval]:
    """Read every explicit rest beat's realtime interval from an already-parsed GP track.

    Performs no file I/O and does not re-parse anything; ``track`` and ``tempo_points`` are
    the same already-parsed/derived objects ``guitarpro_import`` consumes internally.
    """

    intervals: list[ExplicitRestInterval] = []
    for measure_index, measure in enumerate(getattr(track, "measures", []) or []):
        for voice in getattr(measure, "voices", []) or []:
            for beat in getattr(voice, "beats", []) or []:
                status = getattr(beat, "status", None)
                status_name = str(getattr(status, "name", status) or "")
                if status_name != _EXPLICIT_REST_STATUS_NAME:
                    continue
                start_tick = _normalized_tick(getattr(beat, "start", 0))
                duration_obj = getattr(beat, "duration", None)
                duration_ticks = int(getattr(duration_obj, "time", 0) or 0)
                if duration_ticks <= 0:
                    continue
                intervals.append(
                    ExplicitRestInterval(
                        measure_index=measure_index,
                        start_seconds=_ticks_to_seconds(start_tick, tempo_points),
                        end_seconds=_ticks_to_seconds(start_tick + duration_ticks, tempo_points),
                    )
                )
    return intervals


def extract_note_intervals(
    track: Any,
    tempo_points: list[tuple[int, float]],
) -> list[NoteInterval]:
    """Read every authored note's realtime interval from an already-parsed GP track.

    Mirrors ``guitarpro_import.convert_guitarpro_song``'s own beat/note walk so the intervals
    checked here are the same ones the generator's importer would produce, without requiring
    that function's source-path/hash/instrument-selection arguments.
    """

    intervals: list[NoteInterval] = []
    for measure_index, measure in enumerate(getattr(track, "measures", []) or []):
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
                for source_note in beat_notes:
                    intervals.append(
                        NoteInterval(
                            measure_index=measure_index,
                            start_seconds=start_seconds,
                            end_seconds=end_seconds,
                            string_number=int(getattr(source_note, "string")),
                            fret=int(getattr(source_note, "value")),
                        )
                    )
    return intervals


def compute_eof_rest_boundary_check(
    song: Any,
    *,
    track_index: int,
    source_sha256: str,
    overlap_tolerance_seconds: float = 1e-6,
) -> EOFRestBoundaryReport:
    """Compare imported note sustains against EOF-derived explicit rest boundaries.

    ``song`` is the already-parsed Guitar Pro structure this project's importer already
    produces (``guitarpro.parse()`` output); it is not re-parsed here.

    Pure function: deterministic, no I/O, no network, no dependency on a live EOF process.
    """

    if overlap_tolerance_seconds < 0:
        raise EOFRestBoundaryCheckError("overlap tolerance must be non-negative")

    tracks = list(getattr(song, "tracks", []) or [])
    if track_index < 0 or track_index >= len(tracks):
        raise EOFRestBoundaryCheckError(f"track index {track_index} is outside 0..{len(tracks) - 1}")
    track = tracks[track_index]

    measures = list(getattr(track, "measures", []) or [])
    if not measures:
        raise EOFRestBoundaryCheckError("selected track has no measures")

    tempo_points = _collect_tempo_points(song, track)
    rests = extract_explicit_rest_intervals(track, tempo_points)
    notes = extract_note_intervals(track, tempo_points)

    violations: list[RestBoundaryViolation] = []
    for rest in rests:
        for note in notes:
            overlap = min(note.end_seconds, rest.end_seconds) - max(note.start_seconds, rest.start_seconds)
            if overlap > overlap_tolerance_seconds:
                violations.append(
                    RestBoundaryViolation(note=note, rest=rest, overlap_seconds=overlap)
                )

    boundaries_respected = not violations
    if not rests:
        reason = "No explicit rest beats were present in the selected track; nothing to check."
    elif boundaries_respected:
        reason = (
            f"{len(rests)} explicit rest beat(s) found across {len(notes)} imported note(s); "
            "no note sustain overlaps an explicit rest boundary."
        )
    else:
        first = violations[0]
        reason = (
            f"{len(violations)} note/explicit-rest overlap(s) found: a note starting at "
            f"{first.note.start_seconds:.3f}s (measure {first.note.measure_index}) overlaps an "
            f"explicit rest at {first.rest.start_seconds:.3f}s-{first.rest.end_seconds:.3f}s "
            f"(measure {first.rest.measure_index}) by {first.overlap_seconds:.3f}s."
        )

    return EOFRestBoundaryReport(
        source_sha256=source_sha256,
        track_index=track_index,
        explicit_rest_count=len(rests),
        note_count=len(notes),
        violations=violations,
        boundaries_respected=boundaries_respected,
        reason=reason,
    )


def analyze_guitarpro_rest_boundaries(
    path: Path,
    *,
    instrument: ArrangementKind = "bass",
    track_index: int | None = None,
    overlap_tolerance_seconds: float = 1e-6,
) -> EOFRestBoundaryReport:
    """Convenience I/O wrapper: parse a Guitar Pro file once, then compute the pure report.

    Reuses this project's existing Guitar Pro loading/track-selection (``guitarpro_import.py``)
    rather than re-implementing GP parsing or track scoring.
    """

    path = path.expanduser().resolve()
    guitarpro = _load_guitarpro()
    try:
        song = guitarpro.parse(str(path))
    except Exception as exc:  # noqa: BLE001 - mirrors guitarpro_import.import_guitarpro
        raise GuitarProImportError(f"Failed to parse Guitar Pro file: {path.name}") from exc
    resolved_index, _ = select_arrangement_track(song, instrument=instrument, track_index=track_index)
    return compute_eof_rest_boundary_check(
        song,
        track_index=resolved_index,
        source_sha256=sha256_file(path),
        overlap_tolerance_seconds=overlap_tolerance_seconds,
    )
