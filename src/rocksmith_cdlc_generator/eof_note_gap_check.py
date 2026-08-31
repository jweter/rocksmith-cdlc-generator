from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .reviewed_export_events import ReviewedExportArrangement, ReviewedExportNote

EOF_UPSTREAM_REPOSITORY = "raynebc/editor-on-fire"
EOF_UPSTREAM_COMMIT = "c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100"
EOF_UPSTREAM_PATH = "src/song.c"
EOF_UPSTREAM_FUNCTION = "eof_get_note_max_length"

# raynebc/editor-on-fire src/song.c (audited at EOF_UPSTREAM_COMMIT), eof_get_note_max_length()
# is EOF's own bound on how long a note's sustain is allowed to run before the next note on a
# lane it shares: it walks forward to the next note and, unless the current note has "crazy"
# status *and* shares no lane/string with that next note (a guitar-hero-style multi-lane
# exception that has no equivalent for a pro-guitar string/fret track) or LINKNEXT status (which
# only relaxes the minimum-*distance* requirement, not the hard ceiling -- LINKNEXT still may not
# extend past the next note's own position: "the note is allowed to extend all the way up to the
# next note"), the sustain is bounded so it ends at or before the next note's position. There is
# no EOF-modeled case, pro-guitar or otherwise, in which one lane's/string's note is allowed to
# sound past the position where the next note on that same lane/string begins.
#
# This project's ReviewedExportArrangement (reviewed_export_events.reviewed_export_arrangement)
# is the post-reconciliation/post-materialization read model every Bass/Lead/Rhythm authoring
# and Rocksmith XML export path consumes: the same string/fret positions rocksmith_xml.py writes
# a "sustain" attribute from. This check reapplies EOF's own hard ceiling to that read model: for
# every pair of temporally-adjacent notes sharing one string_index, the earlier note's projected
# reviewed sustain (reviewed_start_seconds + reviewed_duration_seconds) must not extend past the
# later note's reviewed_start_seconds. A tied continuation note (techniques contains "tie") is
# excluded from the pair it closes, since this project models a tie as a deliberate second note
# event representing the same held pitch rather than as EOF's LINKNEXT flag on a single note; an
# untied overlap on the same string is not distinguishable from a genuine defect and is flagged.
#
# A note whose reconciliation/fret-mapping is not yet resolved (string_index or fret is None,
# i.e. ReviewedExportNote.position_ready is False) cannot be compared for same-string overlap and
# is excluded, consistent with this project's fail-closed review-first posture: the check reports
# it as undetermined rather than guessing a string assignment.
_TOUCH_TOLERANCE_SECONDS = 1e-6
_TIE_TECHNIQUE = "tie"

NAVIGATION_NOTE = (
    "This check only evaluates same-string sustain overlap between temporally-adjacent notes in "
    "one ReviewedExportArrangement -- the post-reconciliation/post-materialization read model "
    "every Bass/Lead/Rhythm export path consumes. It does not evaluate cross-string overlap "
    "(legitimate for chords), EOF's short-note/staccato/mute truncation preference (see "
    "eof_short_note_truncation_check.py) or explicit-rest boundaries (see "
    "eof_rest_boundary_check.py/eof_export_boundary_check.py), and it treats every note carrying "
    "the 'tie' technique as a deliberate continuation of the immediately preceding same-string "
    "note rather than an overlap defect."
)

EVIDENCE_NOTE = (
    "EOF-derived same-string note-gap evidence. Advisory and source-bound only: it may reveal a "
    "reconciliation/materialization overlap defect but never silently rewrites canonical chart "
    "state or trims a sustain."
)


class EOFNoteGapCheckError(ValueError):
    pass


class NoteGapViolation(BaseModel):
    model_config = ConfigDict(frozen=True)

    string_index: int = Field(ge=0)
    note_source_event_index: int = Field(ge=0)
    note_reviewed_start_seconds: float = Field(ge=0)
    note_reviewed_end_seconds: float = Field(ge=0)
    next_note_source_event_index: int = Field(ge=0)
    next_note_reviewed_start_seconds: float = Field(ge=0)
    overlap_seconds: float = Field(gt=0)


class EOFNoteGapReport(BaseModel):
    """Advisory comparison of exported same-string note sustains against EOF's max-length ceiling.

    Never rewrites canonical chart state; see EVIDENCE_NOTE.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    upstream_repository: str = EOF_UPSTREAM_REPOSITORY
    upstream_commit: str = EOF_UPSTREAM_COMMIT
    upstream_path: str = EOF_UPSTREAM_PATH
    upstream_function: str = EOF_UPSTREAM_FUNCTION
    role: str
    note_count: int = Field(ge=0)
    position_ready_note_count: int = Field(ge=0)
    violations: list[NoteGapViolation] = Field(default_factory=list)
    gaps_respected: bool
    reason: str
    navigation_note: str = NAVIGATION_NOTE
    evidence_note: str = EVIDENCE_NOTE

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path


def compute_eof_note_gap_check(
    arrangement: ReviewedExportArrangement,
    *,
    touch_tolerance_seconds: float = _TOUCH_TOLERANCE_SECONDS,
) -> EOFNoteGapReport:
    """Flag exported notes whose sustain overlaps the next note sharing its string.

    ``arrangement`` is this project's own ``ReviewedExportArrangement`` (any role); notes are
    already ordered by ``reviewed_start_seconds`` (enforced by that model). Pure function:
    deterministic, no I/O.
    """

    if touch_tolerance_seconds < 0:
        raise EOFNoteGapCheckError("touch tolerance must be non-negative")

    by_string: dict[int, list[ReviewedExportNote]] = {}
    position_ready_count = 0
    for note in arrangement.notes:
        if note.string_index is None:
            continue
        position_ready_count += 1
        by_string.setdefault(note.string_index, []).append(note)

    violations: list[NoteGapViolation] = []
    for string_index, notes in by_string.items():
        for current, following in zip(notes, notes[1:]):
            if _TIE_TECHNIQUE in following.techniques:
                continue
            current_end = current.reviewed_start_seconds + current.reviewed_duration_seconds
            overlap = current_end - following.reviewed_start_seconds
            if overlap > touch_tolerance_seconds:
                violations.append(
                    NoteGapViolation(
                        string_index=string_index,
                        note_source_event_index=current.source_event_index,
                        note_reviewed_start_seconds=current.reviewed_start_seconds,
                        note_reviewed_end_seconds=current_end,
                        next_note_source_event_index=following.source_event_index,
                        next_note_reviewed_start_seconds=following.reviewed_start_seconds,
                        overlap_seconds=overlap,
                    )
                )

    violations.sort(key=lambda item: (item.note_reviewed_start_seconds, item.string_index))
    gaps_respected = not violations
    if not arrangement.notes:
        reason = "Arrangement has no notes; nothing to check."
    elif gaps_respected:
        reason = (
            f"{position_ready_count} position-ready note(s) checked across "
            f"{len(by_string)} string(s); no same-string sustain overlap found."
        )
    else:
        first = violations[0]
        reason = (
            f"{len(violations)} same-string overlap(s) found: string {first.string_index} note "
            f"(source event {first.note_source_event_index}) sustains until "
            f"{first.note_reviewed_end_seconds:.6f}s, {first.overlap_seconds * 1000:.3f}ms past "
            f"the next note on that string (source event {first.next_note_source_event_index}) "
            f"starting at {first.next_note_reviewed_start_seconds:.6f}s."
        )

    return EOFNoteGapReport(
        role=arrangement.role.value,
        note_count=len(arrangement.notes),
        position_ready_note_count=position_ready_count,
        violations=violations,
        gaps_respected=gaps_respected,
        reason=reason,
    )
