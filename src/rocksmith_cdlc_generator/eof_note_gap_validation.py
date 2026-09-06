from __future__ import annotations

from pathlib import Path

from .eof_note_gap_check import compute_eof_note_gap_check
from .eof_rocksmith_validation import RocksmithRuleFinding
from .reviewed_export_events import ReviewedExportArrangement, reviewed_export_arrangement
from .score_source import ArrangementRole


def note_gap_rule_findings(
    arrangement: ReviewedExportArrangement,
) -> list[RocksmithRuleFinding]:
    """Project EOF same-string sustain overlap evidence into normal validation.

    The underlying EOF parity check remains advisory and never trims or rewrites
    chart authority. This bridge only makes its violations visible in the normal
    validation/review queue so authors do not have to run a separate diagnostic
    command to discover the defect class.
    """

    report = compute_eof_note_gap_check(arrangement)
    return [
        RocksmithRuleFinding(
            code="rocksmith_same_string_sustain_overlap",
            severity="WARNING",
            message=(
                f"{arrangement.role.value.capitalize()} source event "
                f"{violation.note_source_event_index} on string "
                f"{violation.string_index + 1} sustains "
                f"{violation.overlap_seconds * 1000:.3f}ms past the next "
                "note on that string. EOF bounds a note sustain at or before "
                "the next same-string note; review timing/duration before export."
            ),
            priority=90,
            time_seconds=violation.note_reviewed_start_seconds,
            note_index=violation.note_source_event_index,
        )
        for violation in report.violations
    ]


def project_note_gap_rule_findings(
    project_dir: Path,
    role: ArrangementRole,
) -> list[RocksmithRuleFinding]:
    """Return note-gap findings when current reviewed authority is available.

    A project that has not yet promoted reviewed timing simply has no
    post-review export arrangement to inspect. Existing validation gates remain
    responsible for that earlier workflow state; this EOF-derived advisory must
    not fabricate a substitute failure.
    """

    try:
        arrangement = reviewed_export_arrangement(project_dir, role)
    except (OSError, ValueError):
        return []
    return note_gap_rule_findings(arrangement)
