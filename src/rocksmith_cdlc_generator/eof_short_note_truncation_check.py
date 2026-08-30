from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .guitarpro_import import (
    _GP_QUARTER_TICKS,
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
EOF_UPSTREAM_PREFERENCE_PATH = "src/main.c"

# raynebc/editor-on-fire src/gp_import.c (audited at EOF_UPSTREAM_COMMIT, inside
# EOF_UPSTREAM_FUNCTION) marks a note "note_is_short" when either:
#   (a) its duration -- after undoing time-signature/tuplet/dotted scaling -- is less than a
#       quarter note; PyGuitarPro's own Duration.time already reports absolute ticks (tuplet and
#       dotted factors applied, time signature NOT applied), so this reduces exactly to
#       "duration_ticks < _GP_QUARTER_TICKS" without needing EOF's own floating-point
#       measure-relative recomputation or its "avoid rounding error" guard for an exact quarter
#       note (that guard exists only because EOF's own comparison is a floating-point fraction of
#       a measure; integer tick comparison has no equivalent rounding hazard); or
#   (b) the note has the "staccato" technique (byte2 & 1), unconditionally, regardless of duration.
#
# Given note_is_short, the note is only actually truncated (sustain forced to ~1ms) if, in
# addition, none of the following holds:
#   - the note has tremolo-picking status (exempts the note_is_short branch only);
#   - the note has bend (with a nonzero-height point), vibrato, or any slide status (bend/slide/
#     vibrato/unpitched-slide all set the EOF_NOTE_TFLAG_DONT_TRUNCATE override).
# ...and one of the GP import preferences is enabled for the note's single-note-vs-chord shape:
# `eof_gp_import_truncate_short_notes` (single notes) or `eof_gp_import_truncate_short_chords`
# (chords), read via eof_note_count_colors_bitmask(). src/main.c defines their defaults as 1
# (enabled) and 0 (disabled) respectively.
#
# Independently of note_is_short/staccato, a note that is entirely string-muted (GP "dead" note
# type) or palm-muted is *always* eligible for truncation when it is a single note (not a chord)
# and either import preference is enabled -- this branch does not consult note_is_short at all
# and is not exempted by tremolo-picking, only by the same bend/slide/vibrato override.
#
# Because both of EOF's "unconditional regardless of duration" truncation branches (mute/palm-mute)
# require the note to be a single note rather than a chord, and `eof_gp_import_truncate_short_chords`
# defaults to disabled, no branch below can truncate a chord under EOF's default preferences. This
# check therefore evaluates each note independently (matching PyGuitarPro's per-Note effect model)
# rather than reproducing EOF's per-beat aggregate note-effect bookkeeping across a chord's several
# strings; that aggregate-across-a-chord behavior only has an observable effect when
# `eof_gp_import_truncate_short_chords` is enabled, which is out of scope for this default-preference
# slice.
#
# A note's truncation eligibility never depends on a neighboring note. eof_load_gp() decides it
# per note (gp_import.c ~4191-4218) inside the per-beat note-creation loop, strictly before the
# only two passes that walk the cross-beat note sequence -- "Correct slide directions" (~4498) and
# "Convert slide in from above/below notation..." (~4595) -- so a previous note's shift/legato
# slide-to status (or EOF_NOTE_TFLAG_SLIDE_IN, which is set only from a note's own "slide in from
# above/below" byte) cannot affect it.
NOTE_IS_SHORT_DURATION_THRESHOLD_TICKS = _GP_QUARTER_TICKS
EOF_TRUNCATED_SUSTAIN_SECONDS = 0.001  # EOF collapses a truncated note's length to 1ms.
EOF_DEFAULT_TRUNCATE_SHORT_NOTES = True  # src/main.c: eof_gp_import_truncate_short_notes = 1
EOF_DEFAULT_TRUNCATE_SHORT_CHORDS = False  # src/main.c: eof_gp_import_truncate_short_chords = 0

NAVIGATION_NOTE = (
    "This check evaluates EOF's short-note/staccato/mute sustain-truncation preferences "
    "(the 'note_is_short'/truncation logic in eof_load_gp) against the note sustains the "
    "generator's own current importer would keep; it is the next slice named by the "
    "EOFRestBoundaryReport navigation note and docs/integrations/EOF_PARITY_ROADMAP.md item B. "
    "It does not yet cover whether generated/exported arrangement output (as opposed to directly "
    "imported note data) respects the same truncation preferences; that remains out of scope for "
    "this slice. A previously suspected second gap -- a short note being exempted from truncation "
    "solely because the *previous* note's legato/shift slide targets it -- was investigated against "
    "EOF_UPSTREAM_COMMIT and does not exist: eof_load_gp's truncation-eligibility decision (gp_import.c "
    "~4191-4218) runs per note, inside the per-beat note-creation loop, strictly before the later "
    "'Correct slide directions' (~4498) and 'Convert slide in from above/below' (~4595) passes that are "
    "the only code walking the cross-beat note sequence; those later passes can therefore not influence "
    "an already-finalized truncation decision. EOF_NOTE_TFLAG_SLIDE_IN itself is set only from a note's "
    "own 'slide in from above/below' byte, never derived from a neighboring note's shift/legato slide-to "
    "status. A note's truncation eligibility is therefore fully determined by its own flags; only a slide "
    "notated directly on the note itself (including 'slide into this note from above/below') exempts it, "
    "which this check already covers."
)

EVIDENCE_NOTE = (
    "EOF-derived short-note/staccato/mute truncation evidence, computed against EOF's own default "
    "import preferences (truncate short notes enabled, truncate short chords disabled). Advisory "
    "and source-bound only: it may reveal a generator sustain defect but never silently rewrites "
    "canonical chart state."
)


class EOFShortNoteTruncationCheckError(ValueError):
    pass


class ShortNoteTruncationEvent(BaseModel):
    """One imported note, with EOF's default-preference truncation decision applied to it."""

    model_config = ConfigDict(frozen=True)

    measure_index: int = Field(ge=0)
    start_seconds: float = Field(ge=0)
    string_number: int
    fret: int = Field(ge=0)
    is_chord: bool
    is_short_duration: bool
    is_staccato: bool
    is_fully_muted_or_palm_muted: bool
    is_technique_exempt: bool
    eof_would_truncate: bool
    generator_sustain_seconds: float = Field(ge=0)
    eof_predicted_sustain_seconds: float = Field(ge=0)


class ShortNoteTruncationMismatch(BaseModel):
    model_config = ConfigDict(frozen=True)

    event: ShortNoteTruncationEvent
    sustain_delta_seconds: float = Field(gt=0)


class EOFShortNoteTruncationReport(BaseModel):
    """Advisory comparison of imported note sustains against EOF's default truncation preferences.

    Never rewrites canonical chart state; see EVIDENCE_NOTE. Matches
    ``docs/integrations/EOF_PARITY_ROADMAP.md`` item B's remaining short-note/staccato/mute slice.
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
    truncate_short_notes: bool
    truncate_short_chords: bool
    note_count: int = Field(ge=0)
    eof_truncated_count: int = Field(ge=0)
    mismatches: list[ShortNoteTruncationMismatch] = Field(default_factory=list)
    truncation_matches_eof_preferences: bool
    reason: str
    navigation_note: str = NAVIGATION_NOTE
    evidence_note: str = EVIDENCE_NOTE

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path


def _note_type_name(note: Any) -> str:
    note_type = getattr(note, "type", None)
    return str(getattr(note_type, "name", note_type) or "")


def _note_effect_is_staccato(effect: Any) -> bool:
    return bool(getattr(effect, "staccato", False))


def _note_effect_is_palm_mute(effect: Any) -> bool:
    return bool(getattr(effect, "palmMute", False))


def _note_effect_is_vibrato(effect: Any) -> bool:
    return bool(getattr(effect, "vibrato", False))


def _note_effect_is_tremolo_picking(effect: Any) -> bool:
    return getattr(effect, "tremoloPicking", None) is not None


def _note_effect_has_slide(effect: Any) -> bool:
    return bool(getattr(effect, "slides", None))


def _note_effect_has_nonzero_bend(effect: Any) -> bool:
    bend = getattr(effect, "bend", None)
    if bend is None:
        return False
    points = getattr(bend, "points", None) or []
    return any(getattr(point, "value", 0) for point in points)


def eof_truncation_decision(
    *,
    is_chord: bool,
    is_short_duration: bool,
    is_staccato: bool,
    is_fully_muted_or_palm_muted: bool,
    is_tremolo_picking: bool,
    is_technique_exempt: bool,
    truncate_short_notes: bool,
    truncate_short_chords: bool,
) -> bool:
    """Apply EOF's per-note truncation-eligibility decision (see module-top citation).

    Extracted as its own pure function so other EOF-parity checks (currently
    ``eof_export_boundary_check.py``, item B's generated/exported-output slice) can reuse
    exactly this decision instead of re-deriving it, keeping one source of truth for the
    audited EOF behavior this module documents above.
    """

    truncation_enabled = truncate_short_notes or truncate_short_chords
    truncate = False
    if (is_short_duration or is_staccato) and not is_tremolo_picking:
        if not is_chord and truncate_short_notes:
            truncate = True
        elif is_chord and truncate_short_chords:
            truncate = True
    if is_fully_muted_or_palm_muted:
        truncate = True
    if is_technique_exempt:
        truncate = False
    if not truncation_enabled:
        truncate = False
    return truncate


def compute_eof_short_note_truncation_check(
    song: Any,
    *,
    track_index: int,
    source_sha256: str,
    truncate_short_notes: bool = EOF_DEFAULT_TRUNCATE_SHORT_NOTES,
    truncate_short_chords: bool = EOF_DEFAULT_TRUNCATE_SHORT_CHORDS,
    sustain_delta_tolerance_seconds: float = 1e-6,
) -> EOFShortNoteTruncationReport:
    """Compare imported note sustains against EOF's short-note/staccato/mute truncation rules.

    ``song`` is the already-parsed Guitar Pro structure this project's importer already produces
    (``guitarpro.parse()`` output); it is not re-parsed here.

    ``truncate_short_notes``/``truncate_short_chords`` default to EOF's own out-of-the-box
    preference values (``src/main.c``): short single notes are truncated, short chords are not.

    Pure function: deterministic, no I/O, no network, no dependency on a live EOF process.
    """

    if sustain_delta_tolerance_seconds < 0:
        raise EOFShortNoteTruncationCheckError("sustain delta tolerance must be non-negative")

    tracks = list(getattr(song, "tracks", []) or [])
    if track_index < 0 or track_index >= len(tracks):
        raise EOFShortNoteTruncationCheckError(f"track index {track_index} is outside 0..{len(tracks) - 1}")
    track = tracks[track_index]

    measures = list(getattr(track, "measures", []) or [])
    if not measures:
        raise EOFShortNoteTruncationCheckError("selected track has no measures")

    tempo_points = _collect_tempo_points(song, track)

    events: list[ShortNoteTruncationEvent] = []
    for measure_index, measure in enumerate(measures):
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

                    eof_predicted_sustain_seconds = (
                        EOF_TRUNCATED_SUSTAIN_SECONDS if truncate else generator_sustain_seconds
                    )

                    events.append(
                        ShortNoteTruncationEvent(
                            measure_index=measure_index,
                            start_seconds=start_seconds,
                            string_number=int(getattr(source_note, "string")),
                            fret=int(getattr(source_note, "value")),
                            is_chord=is_chord,
                            is_short_duration=is_short_duration,
                            is_staccato=is_staccato,
                            is_fully_muted_or_palm_muted=is_fully_muted_or_palm_muted,
                            is_technique_exempt=is_technique_exempt,
                            eof_would_truncate=truncate,
                            generator_sustain_seconds=generator_sustain_seconds,
                            eof_predicted_sustain_seconds=eof_predicted_sustain_seconds,
                        )
                    )

    mismatches = [
        ShortNoteTruncationMismatch(
            event=event,
            sustain_delta_seconds=event.generator_sustain_seconds - event.eof_predicted_sustain_seconds,
        )
        for event in events
        if event.eof_would_truncate
        and (event.generator_sustain_seconds - event.eof_predicted_sustain_seconds)
        > sustain_delta_tolerance_seconds
    ]

    eof_truncated_count = sum(1 for event in events if event.eof_would_truncate)
    truncation_matches_eof_preferences = not mismatches

    if not events:
        reason = "No notes were present in the selected track; nothing to check."
    elif eof_truncated_count == 0:
        reason = (
            f"{len(events)} imported note(s) checked; none meet EOF's configured short-note/"
            "staccato/mute truncation preferences, so no truncation evidence applies."
        )
    elif truncation_matches_eof_preferences:
        reason = (
            f"{eof_truncated_count} of {len(events)} imported note(s) meet EOF's configured "
            "truncation preferences and the generator's imported sustain already collapses to "
            "EOF's ~1ms result."
        )
    else:
        first = mismatches[0].event
        reason = (
            f"{len(mismatches)} of {eof_truncated_count} EOF-truncatable note(s) keep a longer "
            f"generator sustain than EOF's configured preferences would produce: a note at "
            f"{first.start_seconds:.3f}s (measure {first.measure_index}) keeps "
            f"{first.generator_sustain_seconds:.3f}s instead of EOF's "
            f"{first.eof_predicted_sustain_seconds:.3f}s. This reflects a known, unimplemented gap: "
            "the generator does not yet apply EOF's short-note/staccato/mute sustain-truncation "
            "preferences on import."
        )

    return EOFShortNoteTruncationReport(
        source_sha256=source_sha256,
        track_index=track_index,
        truncate_short_notes=truncate_short_notes,
        truncate_short_chords=truncate_short_chords,
        note_count=len(events),
        eof_truncated_count=eof_truncated_count,
        mismatches=mismatches,
        truncation_matches_eof_preferences=truncation_matches_eof_preferences,
        reason=reason,
    )


def analyze_guitarpro_short_note_truncation(
    path: Path,
    *,
    instrument: ArrangementKind = "bass",
    track_index: int | None = None,
    truncate_short_notes: bool = EOF_DEFAULT_TRUNCATE_SHORT_NOTES,
    truncate_short_chords: bool = EOF_DEFAULT_TRUNCATE_SHORT_CHORDS,
    sustain_delta_tolerance_seconds: float = 1e-6,
) -> EOFShortNoteTruncationReport:
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
    return compute_eof_short_note_truncation_check(
        song,
        track_index=resolved_index,
        source_sha256=sha256_file(path),
        truncate_short_notes=truncate_short_notes,
        truncate_short_chords=truncate_short_chords,
        sustain_delta_tolerance_seconds=sustain_delta_tolerance_seconds,
    )
