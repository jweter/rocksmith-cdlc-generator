from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .guitarpro_import import ArrangementKind, import_guitarpro
from .source_import import ImportedSource

EOF_UPSTREAM_REPOSITORY = "raynebc/editor-on-fire"
EOF_UPSTREAM_COMMIT = "c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100"
EOF_UPSTREAM_PATH = "src/gp_import.c"
EOF_UPSTREAM_FUNCTION = "eof_import_gp() note-tail resnap pass"

# raynebc/editor-on-fire src/gp_import.c (audited at EOF_UPSTREAM_COMMIT), immediately before
# returning the imported song, runs a dedicated pass over every imported note (comment at that
# exact call site, quoted verbatim):
#
#   "Resnap the end positions of notes that end 1ms after a grid snap position due to floating
#   point math rounding error"
#
# For each note, it computes the nearest "beat interval position" (EOF's grid-snap helper,
# eof_is_any_beat_interval_position()) to the note's end (pos + length, in whole milliseconds).
# If the note's end is not already exactly on that grid position, AND the nearest grid position
# is found, AND it is later than the note's start, AND the discrepancy between the note's current
# end and that grid position is exactly 1ms (`abs(snappos - (pos+length)) == 1`), the note's
# length is corrected so its end lands exactly on the grid position (and any tech/bend-point note
# glued to the old end position moves with it). This exists because GP's own tick-based timing is
# converted to milliseconds via floating-point math elsewhere in the same import pass, and that
# conversion can leave a note's computed end exactly 1ms off the grid position it was actually
# meant to land on.
#
# NOT independently verified: the exact internal resolution of eof_is_any_beat_interval_position()
# itself (its definition was not located in the accessible source tree after checking
# src/gp_import.c, src/beat.c, src/beat.h, src/utility.c, src/menu/beat.c, and src/song.c/song.h,
# all of which call it but do not define it -- likely defined in a file outside this repo's
# current EOF-source audit set). This check therefore does not assume any grid finer than this
# project's own imported beat-time grid (ImportedSource.beat_times_seconds): the calling context
# in gp_import.c is specifically about notes that were positioned against that same beat grid, so
# a ~1ms endpoint drift is attributable to tick/time-unit rounding against it, independent of
# whatever finer subdivision eof_is_any_beat_interval_position() may also support for other
# (non-import) EOF editing operations.
_EOF_DRIFT_TOLERANCE_SECONDS = 0.0011  # "exactly 1ms" in EOF's integer-ms model, with float slack
_EOF_EXACT_TOLERANCE_SECONDS = 1e-6  # already-on-the-grid; not a drift candidate at all

NAVIGATION_NOTE = (
    "This check only flags a note end that is within ~1ms of a beat-grid position without "
    "already being exactly on it -- the same narrow condition EOF's own resnap pass requires "
    "before correcting a note. It does not resnap chord/tech-note tails glued to the corrected "
    "position (EOF's pass does; this project has no equivalent secondary tech-note store yet), "
    "and it does not assume any beat-grid resolution finer than this project's own imported beat "
    "grid (see the module-level comment for what was and was not independently verified)."
)

EVIDENCE_NOTE = (
    "EOF-derived note-endpoint-drift evidence. Advisory and source-bound only: it may reveal a "
    "generator or importer rounding defect but never silently rewrites canonical chart state."
)


class EOFNoteEndpointResnapCheckError(ValueError):
    pass


class NoteEndpointDriftCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    track_index: int = Field(ge=0)
    note_index: int = Field(ge=0)
    note_end_seconds: float = Field(ge=0)
    nearest_grid_seconds: float = Field(ge=0)
    drift_seconds: float = Field(gt=0)


class EOFNoteEndpointResnapReport(BaseModel):
    """Advisory comparison of imported note endpoints against the imported beat grid.

    Never rewrites canonical chart state; see EVIDENCE_NOTE.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    upstream_repository: str = EOF_UPSTREAM_REPOSITORY
    upstream_commit: str = EOF_UPSTREAM_COMMIT
    upstream_path: str = EOF_UPSTREAM_PATH
    upstream_function: str = EOF_UPSTREAM_FUNCTION
    source_sha256: str
    note_count: int = Field(ge=0)
    candidates: list[NoteEndpointDriftCandidate] = Field(default_factory=list)
    endpoints_are_grid_aligned: bool
    reason: str
    navigation_note: str = NAVIGATION_NOTE
    evidence_note: str = EVIDENCE_NOTE

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path


def _nearest_grid_seconds(target: float, grid: list[float]) -> float | None:
    if not grid:
        return None
    import bisect

    index = bisect.bisect_left(grid, target)
    candidates = [value for value in (grid[index - 1] if index > 0 else None, grid[index] if index < len(grid) else None) if value is not None]
    if not candidates:
        return None
    return min(candidates, key=lambda value: abs(value - target))


def compute_eof_note_endpoint_resnap_check(
    source: ImportedSource,
    *,
    drift_tolerance_seconds: float = _EOF_DRIFT_TOLERANCE_SECONDS,
    exact_tolerance_seconds: float = _EOF_EXACT_TOLERANCE_SECONDS,
) -> EOFNoteEndpointResnapReport:
    """Flag imported note endpoints that sit just off the imported beat grid.

    ``source`` is this project's own canonical ``ImportedSource`` (any adapter); the beat grid
    compared against is ``source.beat_times_seconds``, the same grid every note in ``source`` was
    positioned against. Pure function: deterministic, no I/O.
    """

    if drift_tolerance_seconds <= exact_tolerance_seconds:
        raise EOFNoteEndpointResnapCheckError(
            "drift tolerance must be greater than the exact-match tolerance"
        )

    grid = sorted(source.beat_times_seconds)
    candidates: list[NoteEndpointDriftCandidate] = []
    note_count = 0

    for track_index, track in enumerate(source.tracks):
        for note_index, note in enumerate(track.notes):
            note_count += 1
            end_seconds = note.start_seconds + note.duration_seconds
            nearest = _nearest_grid_seconds(end_seconds, grid)
            if nearest is None:
                continue
            drift = abs(nearest - end_seconds)
            if exact_tolerance_seconds < drift <= drift_tolerance_seconds:
                candidates.append(
                    NoteEndpointDriftCandidate(
                        track_index=track_index,
                        note_index=note_index,
                        note_end_seconds=end_seconds,
                        nearest_grid_seconds=nearest,
                        drift_seconds=drift,
                    )
                )

    endpoints_are_grid_aligned = not candidates
    if not grid:
        reason = "Source has no beat grid to compare against; nothing to check."
    elif endpoints_are_grid_aligned:
        reason = f"{note_count} imported note(s) checked against {len(grid)} beat-grid position(s); no endpoint drift found."
    else:
        first = candidates[0]
        reason = (
            f"{len(candidates)} note endpoint(s) found within {drift_tolerance_seconds * 1000:.2f}ms "
            f"of a beat-grid position without landing on it: track {first.track_index} note "
            f"{first.note_index} ends at {first.note_end_seconds:.6f}s, {first.drift_seconds * 1000:.3f}ms "
            f"from the grid position at {first.nearest_grid_seconds:.6f}s."
        )

    return EOFNoteEndpointResnapReport(
        source_sha256=source.provenance.source_sha256,
        note_count=note_count,
        candidates=candidates,
        endpoints_are_grid_aligned=endpoints_are_grid_aligned,
        reason=reason,
    )


def analyze_guitarpro_note_endpoint_resnap(
    path: Path,
    *,
    instrument: ArrangementKind = "bass",
    track_index: int | None = None,
    drift_tolerance_seconds: float = _EOF_DRIFT_TOLERANCE_SECONDS,
    exact_tolerance_seconds: float = _EOF_EXACT_TOLERANCE_SECONDS,
) -> EOFNoteEndpointResnapReport:
    """Convenience I/O wrapper: import a Guitar Pro file's selected arrangement track once,
    then compute the pure report against its own imported beat grid.

    Reuses this project's existing Guitar Pro importer (``guitarpro_import.import_guitarpro``)
    rather than re-implementing GP parsing or track selection, so the note endpoints checked
    here are exactly the ones the generator's own pipeline would produce.
    """

    source = import_guitarpro(path, track_index=track_index, instrument=instrument)
    return compute_eof_note_endpoint_resnap_check(
        source,
        drift_tolerance_seconds=drift_tolerance_seconds,
        exact_tolerance_seconds=exact_tolerance_seconds,
    )
