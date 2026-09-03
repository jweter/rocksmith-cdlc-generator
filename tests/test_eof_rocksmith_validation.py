from rocksmith_cdlc_generator.eof_rocksmith_validation import (
    generic_unsupported_techniques,
    guitar_chart_rule_findings,
    note_rule_findings,
)


def _codes(findings):
    return {finding.code for finding in findings}


def test_fret_24_is_allowed_but_25_fails() -> None:
    allowed = note_rule_findings(
        fret=24,
        techniques=[],
        label="note 0",
        time_seconds=1.0,
        note_index=0,
    )
    rejected = note_rule_findings(
        fret=25,
        techniques=[],
        label="note 1",
        time_seconds=2.0,
        note_index=1,
    )

    assert "rocksmith_fret_limit_exceeded" not in _codes(allowed)
    finding = next(
        finding
        for finding in rejected
        if finding.code == "rocksmith_fret_limit_exceeded"
    )
    assert finding.severity == "FAIL"
    assert finding.priority == 100


def test_open_string_bend_gets_specific_review_findings() -> None:
    findings = note_rule_findings(
        fret=0,
        techniques=["bend"],
        label="note 0",
        time_seconds=8.5,
        note_index=0,
    )

    assert _codes(findings) == {
        "rocksmith_open_string_bend",
        "rocksmith_bend_detail_missing",
    }


def test_fretted_bend_does_not_claim_open_string_problem() -> None:
    findings = note_rule_findings(
        fret=7,
        techniques=["bend"],
        label="note 0",
        time_seconds=8.5,
        note_index=0,
    )

    assert _codes(findings) == {"rocksmith_bend_detail_missing"}


def test_bend_with_exportable_curve_suppresses_detail_missing_finding() -> None:
    findings = note_rule_findings(
        fret=7,
        techniques=["bend"],
        label="note 0",
        time_seconds=8.5,
        note_index=0,
        has_exportable_bend_curve=True,
    )

    assert _codes(findings) == set()


def test_open_string_bend_with_exportable_curve_still_flags_open_string() -> None:
    findings = note_rule_findings(
        fret=0,
        techniques=["bend"],
        label="note 0",
        time_seconds=8.5,
        note_index=0,
        has_exportable_bend_curve=True,
    )

    assert _codes(findings) == {"rocksmith_open_string_bend"}


def test_slide_reports_missing_structured_rocksmith_detail() -> None:
    findings = note_rule_findings(
        fret=7,
        techniques=["slide"],
        label="note 0",
        time_seconds=12.0,
        note_index=0,
    )

    assert _codes(findings) == {"rocksmith_slide_detail_missing"}


def test_slide_with_exportable_target_suppresses_detail_missing_finding() -> None:
    findings = note_rule_findings(
        fret=7,
        techniques=["slide"],
        label="note 0",
        time_seconds=12.0,
        note_index=0,
        has_exportable_slide_target=True,
    )

    assert _codes(findings) == set()


def test_specialized_bend_and_slide_do_not_duplicate_generic_warning() -> None:
    assert generic_unsupported_techniques(["bend", "slide", "tap"]) == ("tap",)


def test_guitar_chart_warns_once_for_missing_fhp_and_fingering() -> None:
    findings = guitar_chart_rule_findings(chord_count=3, playable_event_count=8)

    assert _codes(findings) == {
        "rocksmith_chord_fingering_missing",
        "rocksmith_fhp_missing",
    }


def test_note_only_guitar_chart_requires_fhp_but_not_chord_fingering() -> None:
    findings = guitar_chart_rule_findings(chord_count=0, playable_event_count=8)

    assert _codes(findings) == {"rocksmith_fhp_missing"}


def test_empty_chart_does_not_emit_missing_authoring_structure_warnings() -> None:
    assert guitar_chart_rule_findings(chord_count=0, playable_event_count=0) == []
