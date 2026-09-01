from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .printed_notation_import import PrintedNotationFixture


class MeasureCoverageIssue(BaseModel):
    model_config = ConfigDict(frozen=True)

    measure: int = Field(ge=1)
    code: Literal[
        "missing_measure",
        "event_outside_measure",
        "coverage_gap",
        "rest_note_overlap",
    ]
    detail: str


class PrintedNotationMeterReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    measure_count: int = Field(ge=0)
    issues: list[MeasureCoverageIssue] = Field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.issues


def _interval(beat: float, duration: float) -> tuple[float, float]:
    start = beat - 1.0
    return start, start + duration


def _overlap(first: tuple[float, float], second: tuple[float, float], tolerance: float) -> bool:
    return max(first[0], second[0]) < min(first[1], second[1]) - tolerance


def validate_printed_notation_meter(
    fixture: PrintedNotationFixture,
    *,
    tolerance_beats: float = 1e-6,
) -> PrintedNotationMeterReport:
    """Require explicit full-measure coverage before practice authoring.

    The union of sounded-note and explicit-rest intervals must cover every beat from
    measure start to measure end. Simultaneous notes/chords are allowed to overlap each
    other; a rest overlapping a note is not. This turns the printed-notation adapter's
    historical coverage warning into a hard gate for the photographed-score product
    path so a missed symbol cannot silently become playable chart silence.
    """

    if tolerance_beats < 0:
        raise ValueError("tolerance_beats must be non-negative")

    all_events = [
        (page, event, "note")
        for page in fixture.pages
        for event in page.events
    ] + [
        (page, rest, "rest")
        for page in fixture.pages
        for rest in page.rests
    ]
    if not all_events:
        return PrintedNotationMeterReport(measure_count=0, issues=[])

    maximum_measure = max(event.measure for _page, event, _kind in all_events)
    numerator = float(fixture.time_signature.numerator)
    issues: list[MeasureCoverageIssue] = []

    for measure_number in range(1, maximum_measure + 1):
        notes = [
            _interval(event.beat, event.duration_beats)
            for _page, event, kind in all_events
            if kind == "note" and event.measure == measure_number
        ]
        rests = [
            _interval(event.beat, event.duration_beats)
            for _page, event, kind in all_events
            if kind == "rest" and event.measure == measure_number
        ]
        intervals = [*notes, *rests]
        if not intervals:
            issues.append(
                MeasureCoverageIssue(
                    measure=measure_number,
                    code="missing_measure",
                    detail="measure has no reviewed note or explicit-rest events",
                )
            )
            continue

        outside = [
            interval
            for interval in intervals
            if interval[0] < -tolerance_beats or interval[1] > numerator + tolerance_beats
        ]
        if outside:
            issues.append(
                MeasureCoverageIssue(
                    measure=measure_number,
                    code="event_outside_measure",
                    detail=f"event interval(s) extend outside 0..{numerator:g} beats: {outside}",
                )
            )

        rest_overlap = any(
            _overlap(note, rest, tolerance_beats)
            for note in notes
            for rest in rests
        )
        if rest_overlap:
            issues.append(
                MeasureCoverageIssue(
                    measure=measure_number,
                    code="rest_note_overlap",
                    detail="an explicit rest overlaps a sounded note interval",
                )
            )

        bounded = sorted(
            (max(0.0, start), min(numerator, end))
            for start, end in intervals
            if end > 0.0 and start < numerator
        )
        cursor = 0.0
        gaps: list[tuple[float, float]] = []
        for start, end in bounded:
            if start > cursor + tolerance_beats:
                gaps.append((cursor, start))
            cursor = max(cursor, end)
        if cursor < numerator - tolerance_beats:
            gaps.append((cursor, numerator))
        if gaps:
            issues.append(
                MeasureCoverageIssue(
                    measure=measure_number,
                    code="coverage_gap",
                    detail=f"unexplained beat gap(s): {gaps}",
                )
            )

    return PrintedNotationMeterReport(
        measure_count=maximum_measure,
        issues=issues,
    )
