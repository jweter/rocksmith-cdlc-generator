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
EOF_UPSTREAM_PATH = "src/rs.c, src/note.c"
EOF_UPSTREAM_FUNCTION = "eof_note_can_be_played_within_fret_tolerance"
EOF_UPSTREAM_PREFERENCE_PATH = "src/main.c"

# raynebc/editor-on-fire src/rs.c (audited at EOF_UPSTREAM_COMMIT) implements EOF's mature
# fret-hand-position (FHP) playability rule: a chord/note can be played without moving the
# fretting hand from its currently established position only if the combined fret span it
# would then occupy -- the union of the position already in effect and this chord/note's own
# lowest/highest fretted string (src/note.c's eof_pro_guitar_note_lowest_fret/_highest_fret,
# which both ignore open strings and fully-unspecified-mute placeholders) -- does not exceed
# eof_fret_range_tolerances[lowest_fret]. src/main.c defines that table's out-of-the-box
# default as a uniform 4-fret span for the entire neck (eof_4_fret_range = 1, i.e. "a 4-fret
# span starting at fret 1 covers the whole fretboard"; eof_5_fret_range/eof_6_fret_range
# default to 0/undefined). This check reproduces only that default, uniform-4-fret table; it
# does not reproduce eof_build_fret_range_tolerances()'s "dynamic" per-track-built variant
# (which widens the table using the track's own widest already-notated chords) or EOF's
# user-configurable narrower/wider zones, since this project has no equivalent preference.
#
# eof_note_can_be_played_within_fret_tolerance() also does two things this check reproduces:
#   - a chord/note whose every used string is open (or fully mute-unspecified) imposes no
#     position constraint of its own; the function instead looks ahead to the next note with
#     actual fretted content and evaluates compatibility using that note's range instead
#     (rs.c's `while(1)` lookahead loop). An open-only chord/note with no later fretted note
#     in the track is always compatible with whatever position is already in effect.
#   - a position not yet established (current_low == 0, EOF's own overloaded "no position yet"
#     sentinel, faithfully reproduced here) is always compatible with the first note reached;
#     that note establishes the initial position outright.
#
# Explicitly out of scope for this slice (see NAVIGATION_NOTE): eof_pro_guitar_note_is_barre_chord's
# same-fret/non-contiguous-string special case (a barre chord is exempt from the ordinary
# lowest-fret-must-match-the-open-position rule; porting it correctly depends on EOF's own
# string-to-bitmask ordering convention, which this project's note model does not expose), the
# beat-level tap/slap/pop exemption (EOF's own gp_import.c reads that byte only for a debug log
# and PyGuitarPro's own SlapEffect is not yet consumed for any other purpose in this project),
# and the entire fingering/slide/arpeggio-phrase/capo/RS-phrase-boundary machinery in
# eof_generate_efficient_hand_positions_logic() that decides *where* to write each resulting
# fret-hand-position event and forces additional position changes for reasons unrelated to
# fret-span geometry (index-finger chord fingering, a preceding slide, an arpeggio/handshape
# phrase boundary, or an RS phrase requiring its own leading position). This check only answers
# a narrower question: applying EOF's own geometric compatibility test alone, and nothing else,
# how many times does this arrangement structurally require the fretting hand to relocate, and
# where? That is a lower bound on EOF's own real position count, never an upper bound.
DEFAULT_FRET_RANGE_TOLERANCE = 4  # src/main.c: eof_4_fret_range = 1 (whole neck, default)
UNINITIALIZED_POSITION_FRET = 0  # EOF's own overloaded "no position established yet" sentinel

NAVIGATION_NOTE = (
    "This check reproduces only EOF's default-preference, uniform-4-fret geometric compatibility "
    "test (eof_note_can_be_played_within_fret_tolerance against the static, non-dynamic "
    "eof_fret_range_tolerances table) as a lower bound on the number of fret-hand-position "
    "relocations an arrangement structurally requires. It intentionally excludes: the barre-chord "
    "same-position exemption (eof_pro_guitar_note_is_barre_chord), the beat-level tap/slap/pop "
    "exemption, EOF's dynamic per-track-built or user-widened tolerance tables, and the "
    "fingering/slide/arpeggio-phrase/capo/RS-phrase-boundary logic in "
    "eof_generate_efficient_hand_positions_logic that decides additional position changes and "
    "exact placement for reasons other than fret-span geometry. It also does not reproduce that "
    "function's own multi-position write-back bookkeeping; when a note fails the compatibility "
    "test, this check simply seeds the next position with that note's own fret range, which is "
    "the same choice a straightforward implementation of the identical predicate would make. "
    "docs/eof-subsystem-parity-matrix.md's 'FHP range/width' and 'Handshape/FHP violations' rows "
    "(issue #414) name the remaining fingering/arpeggio/slide-triggered position logic as the "
    "next slice."
)

EVIDENCE_NOTE = (
    "EOF-derived fret-hand-position tolerance evidence, computed against EOF's own default "
    "4-fret tolerance table. Advisory and source-bound only: it may reveal that the generator's "
    "exported arrangement carries structurally required fret-hand-positions it does not yet "
    "generate, but never selects, writes, or rewrites any fret-hand-position itself."
)


class EOFFretRangeToleranceCheckError(ValueError):
    pass


class FretRangeChordEvent(BaseModel):
    """One imported chord/note's fret-span data, in track order."""

    model_config = ConfigDict(frozen=True)

    measure_index: int = Field(ge=0)
    start_seconds: float = Field(ge=0)
    is_open_only: bool
    lowest_fret: int = Field(ge=0)
    highest_fret: int = Field(ge=0)


class RequiredFretHandPosition(BaseModel):
    """One point where EOF's tolerance test requires the fretting hand to relocate."""

    model_config = ConfigDict(frozen=True)

    event: FretRangeChordEvent
    fret: int = Field(ge=0)


class EOFFretRangeToleranceReport(BaseModel):
    """Advisory lower-bound count of EOF-derived required fret-hand-position relocations.

    Never selects, writes, or rewrites any fret-hand-position; see EVIDENCE_NOTE. Matches
    ``docs/eof-subsystem-parity-matrix.md``'s 'FHP range/width' row (issue #414).
    """

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    upstream_repository: str = EOF_UPSTREAM_REPOSITORY
    upstream_commit: str = EOF_UPSTREAM_COMMIT
    upstream_path: str = EOF_UPSTREAM_PATH
    upstream_function: str = EOF_UPSTREAM_FUNCTION
    upstream_preference_path: str = EOF_UPSTREAM_PREFERENCE_PATH
    source_sha256: str
    track_index: int = Field(ge=0)
    fret_range_tolerance: int = DEFAULT_FRET_RANGE_TOLERANCE
    chord_count: int = Field(ge=0)
    required_positions: list[RequiredFretHandPosition] = Field(default_factory=list)
    generator_anchor_count: Literal[0] = 0
    matches_generator_output: bool
    reason: str
    navigation_note: str = NAVIGATION_NOTE
    evidence_note: str = EVIDENCE_NOTE

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path


def _chord_fret_span(beat_notes: list[Any]) -> tuple[int, int]:
    """Return (lowest, highest) fret used by this beat's notes, ignoring open strings.

    Mirrors src/note.c's eof_pro_guitar_note_lowest_fret_np/eof_pro_guitar_note_highest_fret:
    a note played on an open string (fret 0) contributes to neither bound.
    """

    frets = [int(getattr(note, "value", 0) or 0) for note in beat_notes]
    fretted = [fret for fret in frets if fret > 0]
    if not fretted:
        return 0, 0
    return min(fretted), max(fretted)


def compute_eof_fret_range_tolerance_check(
    song: Any,
    *,
    track_index: int,
    source_sha256: str,
    fret_range_tolerance: int = DEFAULT_FRET_RANGE_TOLERANCE,
) -> EOFFretRangeToleranceReport:
    """Compare an imported arrangement against EOF's default fret-hand-position tolerance rule.

    ``song`` is the already-parsed Guitar Pro structure this project's importer already produces
    (``guitarpro.parse()`` output); it is not re-parsed here.

    Pure function: deterministic, no I/O, no network, no dependency on a live EOF process.
    """

    if fret_range_tolerance <= 0:
        raise EOFFretRangeToleranceCheckError("fret range tolerance must be positive")

    tracks = list(getattr(song, "tracks", []) or [])
    if track_index < 0 or track_index >= len(tracks):
        raise EOFFretRangeToleranceCheckError(f"track index {track_index} is outside 0..{len(tracks) - 1}")
    track = tracks[track_index]

    measures = list(getattr(track, "measures", []) or [])
    if not measures:
        raise EOFFretRangeToleranceCheckError("selected track has no measures")

    tempo_points = _collect_tempo_points(song, track)

    chords: list[FretRangeChordEvent] = []
    for measure_index, measure in enumerate(measures):
        for voice in getattr(measure, "voices", []) or []:
            for beat in getattr(voice, "beats", []) or []:
                beat_notes = list(getattr(beat, "notes", None) or [])
                if not beat_notes:
                    continue
                start_tick = _normalized_tick(getattr(beat, "start", 0))
                start_seconds = _ticks_to_seconds(start_tick, tempo_points)
                lowest, highest = _chord_fret_span(beat_notes)
                chords.append(
                    FretRangeChordEvent(
                        measure_index=measure_index,
                        start_seconds=start_seconds,
                        is_open_only=(lowest == 0 and highest == 0),
                        lowest_fret=lowest,
                        highest_fret=highest,
                    )
                )

    # EOF's own lookahead: a chord/note with no fretted content imposes no constraint of its
    # own and is instead evaluated using the next chord/note that does have fretted content.
    effective_spans: list[tuple[int, int]] = [(0, 0)] * len(chords)
    next_fretted_low = 0
    next_fretted_high = 0
    for index in range(len(chords) - 1, -1, -1):
        chord = chords[index]
        if not chord.is_open_only:
            next_fretted_low, next_fretted_high = chord.lowest_fret, chord.highest_fret
            effective_spans[index] = (chord.lowest_fret, chord.highest_fret)
        else:
            effective_spans[index] = (next_fretted_low, next_fretted_high)

    required_positions: list[RequiredFretHandPosition] = []
    current_low = UNINITIALIZED_POSITION_FRET
    current_high = UNINITIALIZED_POSITION_FRET
    for chord, (effective_low, effective_high) in zip(chords, effective_spans):
        if current_low == UNINITIALIZED_POSITION_FRET:
            current_low, current_high = effective_low, effective_high
            if current_low != UNINITIALIZED_POSITION_FRET:
                # Only fretted content actually establishes a position; a chord that is itself
                # open-only with no later fretted chord in the track (effective_low still 0
                # after the lookahead substitution above) leaves the position uninitialized,
                # matching EOF's own final flush condition (current_low == last_anchor == 0
                # writes nothing).
                required_positions.append(RequiredFretHandPosition(event=chord, fret=current_low))
            continue

        if effective_low == 0:
            merged_low = current_low
        elif current_low != 0 and current_low < effective_low:
            merged_low = current_low
        else:
            merged_low = effective_low
        merged_high = max(current_high, effective_high)

        if merged_high - merged_low + 1 > fret_range_tolerance:
            current_low, current_high = effective_low, effective_high
            required_positions.append(RequiredFretHandPosition(event=chord, fret=current_low))
        else:
            current_low, current_high = merged_low, merged_high

    matches_generator_output = len(required_positions) == 0
    if not chords:
        reason = "No notes were present in the selected track; nothing to check."
    elif matches_generator_output:
        reason = (
            f"{len(chords)} imported chord/note event(s) checked; EOF's default fret-hand-"
            "position tolerance rule requires no position beyond the track's initial one, "
            "consistent with the generator's current empty fret-hand-position output."
        )
    else:
        first = required_positions[0].event
        reason = (
            f"EOF's default fret-hand-position tolerance rule requires {len(required_positions)} "
            f"fret-hand-position(s) across {len(chords)} imported chord/note event(s) -- the first "
            f"at {first.start_seconds:.3f}s (measure {first.measure_index}) -- but the generator's "
            "real Rocksmith XML export currently always writes an empty <anchors> list "
            "(rocksmith_xml.py) for every difficulty. This reflects a known, unimplemented gap: "
            "the generator does not yet generate any fret-hand-positions on export."
        )

    return EOFFretRangeToleranceReport(
        source_sha256=source_sha256,
        track_index=track_index,
        fret_range_tolerance=fret_range_tolerance,
        chord_count=len(chords),
        required_positions=required_positions,
        matches_generator_output=matches_generator_output,
        reason=reason,
    )


def analyze_guitarpro_fret_range_tolerance(
    path: Path,
    *,
    instrument: ArrangementKind = "bass",
    track_index: int | None = None,
    fret_range_tolerance: int = DEFAULT_FRET_RANGE_TOLERANCE,
) -> EOFFretRangeToleranceReport:
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
    return compute_eof_fret_range_tolerance_check(
        song,
        track_index=resolved_index,
        source_sha256=sha256_file(path),
        fret_range_tolerance=fret_range_tolerance,
    )
