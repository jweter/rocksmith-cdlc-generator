from __future__ import annotations

from pathlib import Path

from .eof_note_gap_check import compute_eof_note_gap_check
from .eof_rocksmith_validation import RocksmithRuleFinding
from .reviewed_export_events import ReviewedExportArrangement, reviewed_export_arrangement
from .reviewed_score_timing_authority import REVIEWED_SCORE_TIMING_PATH
from .score_source import ArrangementRole


def note_gap_rule_findings(
    arrangement: ReviewedExportArrangement,
) -> list[RocksmithRuleFinding]:
    """Project EOF same-string sustain overlap evidence into normal validation.

    The underlying EOF parity check never trims or rewrites chart authority.
    A same-string sustain that crosses the next attack is a deterministic export
    correctness defect, so this bridge promotes it to a fail-closed validation
    finding while leaving the actual timing/duration correction to human review.
    """

    report = compute_eof_note_gap_check(arrangement)
    return [
        RocksmithRuleFinding(
            code="rocksmith_same_string_sustain_overlap",
            severity="FAIL",
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
    post-review export arrangement to inspect. Once promoted authority exists,
    stale or corrupt authority is an actionable validation failure rather than
    an absent optional advisory.
    """

    project = project_dir.expanduser().resolve()
    authority_path = project / REVIEWED_SCORE_TIMING_PATH
    try:
        arrangement = reviewed_export_arrangement(project, role)
    except FileNotFoundError:
        if not authority_path.is_file():
            return []
        return [
            RocksmithRuleFinding(
                code="reviewed_score_timing_authority_invalid",
                severity="FAIL",
                message=(
                    f"{role.value.capitalize()} reviewed score timing authority exists "
                    "but its promoted export inputs are missing or inaccessible; refresh "
                    "the reviewed timing/export authority before packaging."
                ),
                priority=10,
            )
        ]
    except (OSError, ValueError) as exc:
        if not authority_path.is_file():
            return []
        return [
            RocksmithRuleFinding(
                code="reviewed_score_timing_authority_invalid",
                severity="FAIL",
                message=(
                    f"{role.value.capitalize()} reviewed score timing authority is stale "
                    f"or invalid: {exc}. Refresh and re-review the current timing/export "
                    "authority before packaging."
                ),
                priority=10,
            )
        ]
    return note_gap_rule_findings(arrangement)
