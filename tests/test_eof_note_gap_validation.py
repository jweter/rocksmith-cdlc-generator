from pathlib import Path

import pytest

from rocksmith_cdlc_generator.eof_note_gap_validation import (
    note_gap_rule_findings,
    project_note_gap_rule_findings,
)
from rocksmith_cdlc_generator.reviewed_export_events import (
    ReviewedExportArrangement,
    ReviewedExportNote,
)
from rocksmith_cdlc_generator.score_source import ArrangementRole
from rocksmith_cdlc_generator.source_import import SourceTrustClass


def _note(
    event_index: int,
    *,
    start: float,
    duration: float,
    string_index: int,
    techniques: list[str] | None = None,
) -> ReviewedExportNote:
    return ReviewedExportNote(
        source_event_index=event_index,
        source_start_seconds=start,
        source_duration_seconds=duration,
        reviewed_start_seconds=start,
        reviewed_duration_seconds=duration,
        midi=40 + event_index,
        string_index=string_index,
        fret=event_index,
        techniques=techniques or [],
        import_confidence=1.0,
        trust_class=SourceTrustClass.symbolic_unverified,
        position_ready=True,
    )


def _arrangement(notes: list[ReviewedExportNote]) -> ReviewedExportArrangement:
    return ReviewedExportArrangement(
        role=ArrangementRole.bass,
        source_track_index=0,
        source_output_json="sources/imported/synthetic.json",
        source_output_sha256="0" * 64,
        recording_sha256="1" * 64,
        score_sha256="2" * 64,
        tuning_midi=(28, 33, 38, 43),
        notes=notes,
        human_confirmed_timing=True,
    )


def test_note_gap_violation_becomes_normal_validation_warning() -> None:
    findings = note_gap_rule_findings(
        _arrangement(
            [
                _note(0, start=1.0, duration=1.5, string_index=0),
                _note(1, start=2.0, duration=0.5, string_index=0),
            ]
        )
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.code == "rocksmith_same_string_sustain_overlap"
    assert finding.severity == "WARNING"
    assert finding.priority == 90
    assert finding.time_seconds == 1.0
    assert "500.000ms" in finding.message


def test_different_strings_do_not_create_note_gap_warning() -> None:
    findings = note_gap_rule_findings(
        _arrangement(
            [
                _note(0, start=1.0, duration=1.5, string_index=0),
                _note(1, start=2.0, duration=0.5, string_index=1),
            ]
        )
    )
    assert findings == []


def test_tied_continuation_keeps_existing_exception() -> None:
    findings = note_gap_rule_findings(
        _arrangement(
            [
                _note(0, start=1.0, duration=1.5, string_index=0),
                _note(1, start=2.0, duration=0.5, string_index=0, techniques=["tie"]),
            ]
        )
    )
    assert findings == []


def test_project_without_promoted_timing_has_no_note_gap_finding(tmp_path: Path) -> None:
    assert project_note_gap_rule_findings(tmp_path, ArrangementRole.bass) == []


def test_stale_promoted_timing_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = tmp_path / "analysis" / "reviewed_score_timing.json"
    authority.parent.mkdir(parents=True)
    authority.write_text("{}\n", encoding="utf-8")

    def _stale(*args: object, **kwargs: object) -> ReviewedExportArrangement:
        raise ValueError("reviewed score timing authority is stale")

    monkeypatch.setattr(
        "rocksmith_cdlc_generator.eof_note_gap_validation.reviewed_export_arrangement",
        _stale,
    )
    findings = project_note_gap_rule_findings(tmp_path, ArrangementRole.bass)

    assert len(findings) == 1
    assert findings[0].code == "reviewed_score_timing_authority_invalid"
    assert findings[0].severity == "ERROR"
    assert "stale" in findings[0].message
