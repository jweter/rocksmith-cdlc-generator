from pathlib import Path

import pytest

from rocksmith_cdlc_generator.click_track_render import render_click_track_wav
from rocksmith_cdlc_generator.deterministic_tempo_map import build_deterministic_tempo_map
from rocksmith_cdlc_generator.printed_notation_validation import (
    PrintedNotationValidationError,
    check_click_track_measure_alignment,
    check_printed_notation_sustain_boundaries,
)
from rocksmith_cdlc_generator.reviewed_export_events import (
    ReviewedExportArrangement,
    ReviewedExportNote,
)
from rocksmith_cdlc_generator.score_source import ArrangementRole
from rocksmith_cdlc_generator.source_import import SourceTrustClass

_SHA = "ab" * 32


def _note(index: int, *, string: int, start: float, duration: float) -> ReviewedExportNote:
    return ReviewedExportNote(
        source_event_index=index,
        source_start_seconds=start,
        source_duration_seconds=duration,
        reviewed_start_seconds=start,
        reviewed_duration_seconds=duration,
        midi=40 + string,
        string_index=string,
        fret=0,
        import_confidence=1.0,
        trust_class=SourceTrustClass.user_confirmed,
        position_ready=True,
    )


def _arrangement(notes: list[ReviewedExportNote]) -> ReviewedExportArrangement:
    return ReviewedExportArrangement(
        role=ArrangementRole.bass,
        source_track_index=0,
        source_output_json="sources/imported/page1.json",
        source_output_sha256=_SHA,
        recording_sha256=_SHA,
        score_sha256=_SHA,
        tuning_midi=(28, 33, 38, 43),
        notes=notes,
        chord_groups=[],
        human_confirmed_timing=True,
    )


def test_no_overlap_passes() -> None:
    arrangement = _arrangement(
        [
            _note(0, string=0, start=0.0, duration=0.5),
            _note(1, string=0, start=0.5, duration=0.5),
        ]
    )
    report = check_printed_notation_sustain_boundaries(arrangement)
    assert report.boundaries_respected is True
    assert report.violations == []


def test_same_string_overlap_is_flagged() -> None:
    arrangement = _arrangement(
        [
            _note(0, string=0, start=0.0, duration=1.0),
            _note(1, string=0, start=0.5, duration=0.5),
        ]
    )
    report = check_printed_notation_sustain_boundaries(arrangement)
    assert report.boundaries_respected is False
    assert len(report.violations) == 1
    violation = report.violations[0]
    assert violation.string_index == 0
    assert violation.first_source_event_index == 0
    assert violation.second_source_event_index == 1
    assert violation.overlap_seconds == pytest.approx(0.5)


def test_different_strings_overlapping_is_a_chord_not_a_violation() -> None:
    arrangement = _arrangement(
        [
            _note(0, string=0, start=0.0, duration=1.0),
            _note(1, string=1, start=0.0, duration=1.0),
        ]
    )
    report = check_printed_notation_sustain_boundaries(arrangement)
    assert report.boundaries_respected is True


def test_negative_tolerance_rejected() -> None:
    arrangement = _arrangement([_note(0, string=0, start=0.0, duration=0.5)])
    with pytest.raises(PrintedNotationValidationError):
        check_printed_notation_sustain_boundaries(arrangement, overlap_tolerance_seconds=-1.0)


def test_click_track_measure_alignment_passes_for_matched_pair(tmp_path: Path) -> None:
    tempo_map = build_deterministic_tempo_map(measure_count=4, bpm=132.0)
    destination = tmp_path / "click.wav"
    render_click_track_wav(tempo_map, destination, count_in_measures=2, trailing_seconds=0.2)

    report = check_click_track_measure_alignment(tempo_map, destination, count_in_measures=2)

    assert report.aligned is True
    assert report.measure_count == 4
    assert report.violations == []


def test_click_track_measure_alignment_flags_mismatched_tempo_map(tmp_path: Path) -> None:
    rendered_map = build_deterministic_tempo_map(measure_count=4, bpm=132.0)
    destination = tmp_path / "click.wav"
    render_click_track_wav(rendered_map, destination, count_in_measures=2, trailing_seconds=0.2)

    # A tempo map with a different BPM has a different beat grid: pairing it with a WAV
    # rendered from a different map is exactly the "stale WAV vs. edited tempo map" failure
    # mode the report's docstring calls out. Same measure count/sample rate so the earlier
    # hard checks (empty beats, sample-rate mismatch) don't short-circuit this scenario.
    mismatched_map = build_deterministic_tempo_map(measure_count=4, bpm=90.0)

    report = check_click_track_measure_alignment(mismatched_map, destination, count_in_measures=2)

    assert report.aligned is False
    assert len(report.violations) > 0


def test_click_track_alignment_rejects_sample_rate_mismatch(tmp_path: Path) -> None:
    tempo_map = build_deterministic_tempo_map(measure_count=1, bpm=120.0)
    destination = tmp_path / "click.wav"
    render_click_track_wav(tempo_map, destination, count_in_measures=1, trailing_seconds=0.1)

    mismatched_map = tempo_map.model_copy(update={"sample_rate_hz": 22050})
    with pytest.raises(PrintedNotationValidationError):
        check_click_track_measure_alignment(mismatched_map, destination, count_in_measures=1)


def test_click_track_alignment_rejects_empty_tempo_map(tmp_path: Path) -> None:
    tempo_map = build_deterministic_tempo_map(measure_count=1, bpm=120.0)
    destination = tmp_path / "click.wav"
    render_click_track_wav(tempo_map, destination, count_in_measures=1, trailing_seconds=0.1)

    empty_map = tempo_map.model_copy(update={"beats": []})
    with pytest.raises(Exception):
        check_click_track_measure_alignment(empty_map, destination, count_in_measures=1)
