from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .guitarpro_import import (
    ArrangementKind,
    GuitarProImportError,
    _load_guitarpro,
    select_arrangement_track,
)
from .hashing import sha256_file


EOF_UPSTREAM_REPOSITORY = "raynebc/editor-on-fire"
EOF_UPSTREAM_COMMIT = "c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100"
EOF_UPSTREAM_PATH = "src/gp_import.c"
EOF_UPSTREAM_FUNCTION = "eof_unwrap_gp_track"

# GP measure-header repeat/alternate-ending fields are single bytes in the on-disk format
# (see PyGuitarPro's gp3.py/gp5.py readers: repeatClose via readI8/readSByte, repeatAlternative
# via readU8), and EOF's own gp_import.c stores the equivalent fields as `unsigned char`. These
# bounds mirror that native byte width; they are not an EOF behavioral choice, just the format's
# physical field size.
_REPEAT_COUNT_BYTE_MAX = 255
_ALT_ENDING_MASK_BITS = 0xFF

# Defensive only: EOF's C loop is implicitly bounded because its repeat counters are
# `unsigned char` (max 255) and it walks a fixed, already-validated in-memory measure array.
# Python has no such implicit width limit, so a malformed or adversarial synthetic fixture could
# otherwise loop indefinitely. This budget is a fail-closed guard, not a port of EOF behavior.
_MAX_UNFOLD_STEPS = 100_000

NAVIGATION_SYMBOLS_NOTE = (
    "EOF's eof_unwrap_gp_track() (same function, same file/commit) also resolves "
    "'Da Capo'/'Da Segno'/'Coda'/'Fine'-style navigation symbols by consulting a separate "
    "gp->symbols table that EOF populates while parsing the raw Guitar Pro binary. "
    "PyGuitarPro's parsed Song/Track object model (this project's Guitar Pro import "
    "dependency) does not expose an equivalent normalized navigation-symbol table, and this "
    "project's importer does not currently extract one. Those navigation markers are "
    "therefore intentionally out of scope for this parity check: only measure-level repeat "
    "starts/ends and bitmask alternate endings are unfolded here. A GP score that relies on "
    "Da Capo/Segno/Coda/Fine navigation will not be fully unfolded by this check."
)

EVIDENCE_NOTE = (
    "EOF-derived repeat/alternate-ending unfolding evidence. Advisory and source-bound only: "
    "it may reveal a generator repeat-unfolding defect but never silently rewrites canonical "
    "chart state."
)


class EOFRepeatUnfoldingError(ValueError):
    pass


class MeasureRepeatMarkers(BaseModel):
    """One written measure's repeat/alternate-ending markers.

    Direct behavior reference: raynebc/editor-on-fire ``src/gp_import.c`` at
    ``c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100``, ``eof_unwrap_gp_track()``. EOF reads three
    raw per-measure fields directly from the parsed Guitar Pro file: a start-of-repeat flag,
    an end-of-repeat repeat count, and an alternate-ending bitmask (``gp->measure[].
    start_of_repeat`` / ``num_of_repeats`` / ``alt_endings``).

    This project's Guitar Pro importer uses PyGuitarPro rather than EOF's own binary reader.
    PyGuitarPro already normalizes the same three fields onto every ``MeasureHeader`` as
    ``isRepeatOpen`` / ``repeatClose`` / ``repeatAlternative`` -- including GP5's off-by-one
    repeat-count correction that EOF's own ``gp_import.c`` applies natively for that file
    version (search for "Version 5 ... slightly different counting" in the audited file), and
    including GP3/GP4/GP5 alternate-ending values always resolving to the same
    bit-per-repeat-pass bitmask that EOF's own bitmask branch consumes
    (``readRepeatAlternative()`` in PyGuitarPro's ``gp3.py``, inherited unmodified by
    ``gp4.py``). EOF's separate "highest pass number" branch for raw GP4 bytes is therefore not
    needed here; PyGuitarPro has already done that normalization for every supported version.
    """

    model_config = ConfigDict(frozen=True)

    index: int = Field(ge=0)
    start_of_repeat: bool
    num_of_repeats: int = Field(ge=0, le=_REPEAT_COUNT_BYTE_MAX)
    alt_ending_mask: int = Field(ge=0, le=_ALT_ENDING_MASK_BITS)


class SourceEventIdentity(BaseModel):
    """A stable pointer to one authored Guitar Pro note, independent of playback timing.

    Identity is (written measure, beat tick within that measure, string, fret) rather than
    realized/unfolded time, because the same written measure can appear at more than one
    realized playback position once repeats are unfolded; its authored identity does not
    change between those occurrences.
    """

    model_config = ConfigDict(frozen=True)

    written_measure_index: int = Field(ge=0)
    tick: int = Field(ge=0)
    string_number: int
    fret: int = Field(ge=0)


class RealizedMeasureEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    realized_position: int = Field(ge=0)
    written_measure_index: int = Field(ge=0)
    first_event: SourceEventIdentity | None = None
    last_event: SourceEventIdentity | None = None


class EOFRepeatUnfoldingReport(BaseModel):
    """Advisory comparison of the generator's realized measure order against EOF-derived
    repeat/alternate-ending unfolding semantics.

    This never rewrites canonical chart state (see EVIDENCE_NOTE); it only reports agreement
    or disagreement so a defect can be triaged before timing authority is promoted, matching
    the design principle in ``docs/integrations/EOF_PARITY_ROADMAP.md``.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    upstream_repository: str = EOF_UPSTREAM_REPOSITORY
    upstream_commit: str = EOF_UPSTREAM_COMMIT
    upstream_path: str = EOF_UPSTREAM_PATH
    upstream_function: str = EOF_UPSTREAM_FUNCTION
    source_sha256: str
    track_index: int = Field(ge=0)
    measure_count: int = Field(ge=0)
    has_repeat_or_alt_ending_markers: bool
    generator_measure_sequence: list[int]
    eof_measure_sequence: list[int]
    sequence_matches: bool
    first_divergence_position: int | None = Field(default=None, ge=0)
    missing_measure_indices: list[int] = Field(default_factory=list)
    duplicated_measure_indices: list[int] = Field(default_factory=list)
    generator_events: list[RealizedMeasureEvent] = Field(default_factory=list)
    realized_events: list[RealizedMeasureEvent] = Field(default_factory=list)
    navigation_symbols_supported: bool = False
    navigation_symbols_note: str = NAVIGATION_SYMBOLS_NOTE
    reason: str
    evidence_note: str = EVIDENCE_NOTE

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path


def extract_repeat_markers(song: Any) -> list[MeasureRepeatMarkers]:
    """Read per-measure repeat/alternate-ending markers from an already-parsed GP song.

    ``song`` is the object returned by PyGuitarPro's ``guitarpro.parse()`` -- the same
    already-parsed structure ``guitarpro_import.convert_guitarpro_song`` consumes. This
    function performs no file I/O and does not re-parse anything.
    """

    headers = list(getattr(song, "measureHeaders", []) or [])
    markers: list[MeasureRepeatMarkers] = []
    for index, header in enumerate(headers):
        start_of_repeat = bool(getattr(header, "isRepeatOpen", False))

        raw_close = getattr(header, "repeatClose", -1)
        try:
            raw_close_int = int(raw_close)
        except (TypeError, ValueError):
            raw_close_int = -1
        num_of_repeats = min(_REPEAT_COUNT_BYTE_MAX, raw_close_int) if raw_close_int > 0 else 0

        raw_alt = getattr(header, "repeatAlternative", 0) or 0
        try:
            alt_ending_mask = int(raw_alt) & _ALT_ENDING_MASK_BITS
        except (TypeError, ValueError):
            alt_ending_mask = 0

        markers.append(
            MeasureRepeatMarkers(
                index=index,
                start_of_repeat=start_of_repeat,
                num_of_repeats=num_of_repeats,
                alt_ending_mask=alt_ending_mask,
            )
        )
    return markers


def unfold_measure_sequence(markers: list[MeasureRepeatMarkers]) -> list[int]:
    """Compute EOF's realized playback-measure order from repeat/alternate-ending markers.

    This is a direct algorithmic port of the repeat-start, end-of-repeat, and
    alternate-ending decision branches of raynebc/editor-on-fire ``src/gp_import.c``
    ``eof_unwrap_gp_track()`` at ``c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100``. It intentionally
    omits that function's separate navigation-symbol branches (Da Capo/Segno/Coda/Fine); see
    ``NAVIGATION_SYMBOLS_NOTE``.

    Pure function: deterministic, no I/O, no network, no dependency on a live EOF process.
    """

    num_measures = len(markers)
    if num_measures == 0:
        return []

    working_num_of_repeats = [marker.num_of_repeats for marker in markers]
    original_num_of_repeats = list(working_num_of_repeats)
    sequence: list[int] = []
    current = 0
    last_start_of_repeat = 0
    curr_repeat = 0
    steps = 0

    def _charge_step() -> None:
        nonlocal steps
        steps += 1
        if steps > _MAX_UNFOLD_STEPS:
            raise EOFRepeatUnfoldingError(
                "repeat unfolding exceeded the defensive iteration budget "
                f"({_MAX_UNFOLD_STEPS} steps); the repeat/alternate-ending structure may be "
                "malformed"
            )

    while current < num_measures:
        _charge_step()
        marker = markers[current]

        if marker.start_of_repeat and last_start_of_repeat != current:
            # This measure begins a new start of repeat: reset the repeat-pass counter.
            curr_repeat = 0
            last_start_of_repeat = current

        alt_mask = marker.alt_ending_mask
        in_alt_ending = bool(alt_mask & (1 << curr_repeat)) if alt_mask else False

        if not alt_mask or in_alt_ending:
            # This measure isn't part of an alternate ending, or the current repeat pass is
            # the pass this alternate ending plays on: realize it.
            sequence.append(current)
            if working_num_of_repeats[current]:
                # End of repeat with passes remaining: jump back to the start of repeat.
                if not in_alt_ending:
                    working_num_of_repeats[current] -= 1
                current = last_start_of_repeat
                curr_repeat += 1
            else:
                # Not an end of repeat with passes left; restore its count in case a later
                # navigation symbol would cause it to be unwrapped again (not modeled here;
                # kept for algorithmic fidelity with the audited function) and continue.
                working_num_of_repeats[current] = original_num_of_repeats[current]
                current += 1
        else:
            # This measure begins a different alternate ending: skip forward to the next
            # measure that ends the scope of this alternate ending (an end of repeat, or the
            # start of a differently-numbered alternate ending), without realizing it.
            curr_alt_ending = alt_mask
            while current < num_measures:
                _charge_step()
                if markers[current].num_of_repeats:
                    current += 1
                    break
                if markers[current].alt_ending_mask and markers[current].alt_ending_mask != curr_alt_ending:
                    break
                current += 1

    return sequence


def _measure_event_identities(
    track: Any,
) -> list[tuple[SourceEventIdentity, SourceEventIdentity] | None]:
    """First/last note identity per written measure, or ``None`` for an empty measure."""

    results: list[tuple[SourceEventIdentity, SourceEventIdentity] | None] = []
    for measure_index, measure in enumerate(getattr(track, "measures", []) or []):
        identities: list[SourceEventIdentity] = []
        for voice in getattr(measure, "voices", []) or []:
            for beat in getattr(voice, "beats", []) or []:
                beat_notes = list(getattr(beat, "notes", None) or [])
                if not beat_notes:
                    continue
                tick = int(getattr(beat, "start", 0) or 0)
                for source_note in sorted(beat_notes, key=lambda item: int(getattr(item, "string", 0))):
                    identities.append(
                        SourceEventIdentity(
                            written_measure_index=measure_index,
                            tick=tick,
                            string_number=int(getattr(source_note, "string")),
                            fret=int(getattr(source_note, "value")),
                        )
                    )
        results.append((identities[0], identities[-1]) if identities else None)
    return results


def _realized_events(
    sequence: list[int],
    identities: list[tuple[SourceEventIdentity, SourceEventIdentity] | None],
) -> list[RealizedMeasureEvent]:
    events: list[RealizedMeasureEvent] = []
    for position, measure_index in enumerate(sequence):
        pair = identities[measure_index] if 0 <= measure_index < len(identities) else None
        first_event, last_event = pair if pair is not None else (None, None)
        events.append(
            RealizedMeasureEvent(
                realized_position=position,
                written_measure_index=measure_index,
                first_event=first_event,
                last_event=last_event,
            )
        )
    return events


def compute_eof_repeat_unfolding(
    song: Any,
    *,
    track_index: int,
    source_sha256: str,
) -> EOFRepeatUnfoldingReport:
    """Compare the generator's realized measure order with EOF-derived repeat unfolding.

    ``song`` is the already-parsed Guitar Pro structure this project's importer already
    produces (``guitarpro.parse()`` output) -- it is not re-parsed here. The generator side of
    the comparison is the written-score-order sequence the existing importer currently treats
    as realized (``guitarpro_import.convert_guitarpro_song`` does not unfold repeats; it only
    emits a warning when repeat markers are present). The EOF side is computed by
    ``unfold_measure_sequence`` from the audited upstream semantics.

    Pure function: deterministic, no I/O, no network, no dependency on a live EOF process.
    """

    tracks = list(getattr(song, "tracks", []) or [])
    if track_index < 0 or track_index >= len(tracks):
        raise EOFRepeatUnfoldingError(f"track index {track_index} is outside 0..{len(tracks) - 1}")
    track = tracks[track_index]

    markers = extract_repeat_markers(song)
    measures = list(getattr(track, "measures", []) or [])
    measure_count = len(measures)
    if measure_count == 0:
        raise EOFRepeatUnfoldingError("selected track has no measures")
    if markers and len(markers) != measure_count:
        raise EOFRepeatUnfoldingError(
            f"song measureHeaders count ({len(markers)}) does not match the selected track's "
            f"measure count ({measure_count}); cannot align repeat markers to measure content"
        )
    if not markers:
        # No song-level measure headers were provided at all: there is no repeat/alternate
        # ending information to unfold, so this fails closed to identity passthrough rather
        # than fabricating markers.
        markers = [
            MeasureRepeatMarkers(index=index, start_of_repeat=False, num_of_repeats=0, alt_ending_mask=0)
            for index in range(measure_count)
        ]

    identities = _measure_event_identities(track)
    generator_sequence = list(range(measure_count))
    eof_sequence = unfold_measure_sequence(markers)

    generator_events = _realized_events(generator_sequence, identities)
    realized_events = _realized_events(eof_sequence, identities)

    sequence_matches = generator_sequence == eof_sequence
    min_len = min(len(generator_sequence), len(eof_sequence))
    first_divergence_position: int | None = None
    for position in range(min_len):
        if generator_sequence[position] != eof_sequence[position]:
            first_divergence_position = position
            break
    else:
        if len(generator_sequence) != len(eof_sequence):
            first_divergence_position = min_len

    eof_counts = Counter(eof_sequence)
    missing_measure_indices = sorted(index for index in range(measure_count) if eof_counts[index] == 0)
    duplicated_measure_indices = sorted(index for index, count in eof_counts.items() if count > 1)

    has_markers = any(
        marker.start_of_repeat or marker.num_of_repeats > 0 or marker.alt_ending_mask > 0
        for marker in markers
    )

    if sequence_matches:
        reason = (
            (
                "EOF-derived repeat/alternate-ending unfolding agrees with the generator's "
                f"written score order across all {measure_count} measure(s)."
            )
            if has_markers
            else (
                "No repeat or alternate-ending markers were present; written score order is "
                "already the realized playback order."
            )
        )
    else:
        reason = (
            "EOF-derived repeat/alternate-ending unfolding disagrees with the generator's "
            f"written score order starting at realized position {first_divergence_position}: "
            f"the generator currently emits each of the {measure_count} written measure(s) "
            f"exactly once (no unfolding; see the 'repeat structure is not unfolded yet' "
            f"import warning), while EOF-derived semantics realize {len(eof_sequence)} "
            f"playback measure(s) ({len(duplicated_measure_indices)} written measure(s) "
            f"repeated, {len(missing_measure_indices)} written measure(s) never reached)."
        )

    return EOFRepeatUnfoldingReport(
        source_sha256=source_sha256,
        track_index=track_index,
        measure_count=measure_count,
        has_repeat_or_alt_ending_markers=has_markers,
        generator_measure_sequence=generator_sequence,
        eof_measure_sequence=eof_sequence,
        sequence_matches=sequence_matches,
        first_divergence_position=first_divergence_position,
        missing_measure_indices=missing_measure_indices,
        duplicated_measure_indices=duplicated_measure_indices,
        generator_events=generator_events,
        realized_events=realized_events,
        reason=reason,
    )


def analyze_guitarpro_repeat_unfolding(
    path: Path,
    *,
    instrument: ArrangementKind = "bass",
    track_index: int | None = None,
) -> EOFRepeatUnfoldingReport:
    """Convenience I/O wrapper: parse a Guitar Pro file once, then compute the pure report.

    Reuses this project's existing Guitar Pro loading/track-selection
    (``guitarpro_import.py``) rather than re-implementing GP parsing or track scoring.
    """

    path = path.expanduser().resolve()
    guitarpro = _load_guitarpro()
    try:
        song = guitarpro.parse(str(path))
    except Exception as exc:  # noqa: BLE001 - mirrors guitarpro_import.import_guitarpro
        raise GuitarProImportError(f"Failed to parse Guitar Pro file: {path.name}") from exc
    resolved_index, _ = select_arrangement_track(song, instrument=instrument, track_index=track_index)
    return compute_eof_repeat_unfolding(
        song,
        track_index=resolved_index,
        source_sha256=sha256_file(path),
    )
