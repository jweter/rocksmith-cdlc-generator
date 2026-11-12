"""Corpus differential metrics (issue #693): metrics, trust tier, sanitized output, and mutation controls."""

from __future__ import annotations

import json

import pytest

from rocksmith_cdlc_generator.corpus_differential import (
    DiffNote,
    Thresholds,
    compare_arrangements,
    mutate_pitch,
    mutate_timing_phase,
)

PITCHES = [40, 43, 45, 47, 48, 50, 52, 55]


def song(count: int = 40, spacing: float = 0.5, scale: float = 1.0) -> list[DiffNote]:
    """A synthetic bass line; strings and frets are derived so alternate mappings are easy to build."""
    return [
        DiffNote(onset_seconds=round(i * spacing * scale, 6), duration_seconds=0.4,
                 midi=PITCHES[i % len(PITCHES)], string=i % 4, fret=i % 12)
        for i in range(count)
    ]


def test_an_identical_arrangement_passes_with_every_metric_clean() -> None:
    result = compare_arrangements(song(), song(), trust_tier="A")
    assert result.verdict == "PASS" and result.authoritative and result.reasons == ()
    assert (result.recall, result.precision, result.pitch_agreement) == (1.0, 1.0, 1.0)
    assert result.onset_phase_seconds == 0.0 and result.string_fret_agreement == 1.0 and result.duration_agreement == 1.0


def test_a_deliberate_timing_phase_mutation_is_detected() -> None:
    result = compare_arrangements(song(), mutate_timing_phase(song(), 0.12), trust_tier="A")
    assert result.verdict == "FAIL" and "TIMING_PHASE_ERROR" in result.reasons
    assert result.onset_phase_seconds == pytest.approx(0.12)
    assert result.first_event_phase_seconds == pytest.approx(0.12)
    assert result.recall == 1.0  # the notes are all there; the metric names the real fault instead of "missing notes"


def test_a_small_phase_error_is_review_required_not_pass_or_fail() -> None:
    result = compare_arrangements(song(), mutate_timing_phase(song(), 0.045), trust_tier="A")
    assert result.verdict == "REVIEW_REQUIRED" and "WITHIN_FAIL_LIMITS_BUT_NOT_CLEAN" in result.reasons


def test_a_deliberate_note_mutation_is_detected_in_the_metrics() -> None:
    one = compare_arrangements(song(), mutate_pitch(song(), [7]), trust_tier="A")
    assert one.wrong_pitch_notes == 1 and one.matched_notes == 39 and one.pitch_agreement < 1.0
    four = compare_arrangements(song(), mutate_pitch(song(), [3, 9, 15, 21]), trust_tier="A")
    assert four.verdict == "REVIEW_REQUIRED" and four.wrong_pitch_notes == 4
    many = compare_arrangements(song(), mutate_pitch(song(), range(0, 40, 3)), trust_tier="A")
    assert many.verdict == "FAIL" and "WRONG_NOTES" in many.reasons


def test_tempo_drift_across_the_song_is_measured_and_detected() -> None:
    reference = song(count=480)
    mild = compare_arrangements(reference, song(count=480, scale=1.0003), trust_tier="A")
    assert mild.onset_drift_seconds_per_minute == pytest.approx(0.018, abs=0.002) and mild.verdict == "PASS"
    steep = compare_arrangements(reference, song(count=480, scale=1.0010), trust_tier="A")
    assert steep.verdict == "FAIL" and "TEMPO_DRIFT" in steep.reasons


def test_equivalent_pitch_on_another_string_and_fret_is_a_match_reported_separately() -> None:
    reference = song()
    moved = [DiffNote(n.onset_seconds, n.duration_seconds, n.midi, string=(n.string or 0) + 1, fret=(n.fret or 0) + 5)
             for n in reference]
    result = compare_arrangements(reference, moved, trust_tier="B")
    assert result.verdict == "PASS" and result.pitch_agreement == 1.0
    assert result.string_fret_agreement == 0.0  # a separate metric, not absolute authority


def test_missing_and_extra_notes_are_counted() -> None:
    reference = song()
    generated = reference[:30] + [DiffNote(30.5, 0.4, 99)]
    result = compare_arrangements(reference, generated, trust_tier="A")
    assert result.matched_notes == 30 and result.missed_notes == 10 and result.extra_notes == 1
    assert result.recall == 0.75 and result.verdict == "FAIL" and "MISSING_NOTES" in result.reasons


def test_a_tier_c_reference_is_never_authoritative() -> None:
    clean = compare_arrangements(song(), song(), trust_tier="C")
    assert clean.authoritative is False and clean.verdict == "REVIEW_REQUIRED" and "TIER_C_NOT_AUTHORITATIVE" in clean.reasons
    broken = compare_arrangements(song(), mutate_timing_phase(song(), 0.2), trust_tier="C")
    assert broken.verdict == "REVIEW_REQUIRED" and "TIMING_PHASE_ERROR" in broken.reasons  # the finding is kept, not the authority


def test_the_trust_tier_is_required_and_validated() -> None:
    with pytest.raises(ValueError):
        compare_arrangements(song(), song(), trust_tier="D")  # type: ignore[arg-type]
    assert compare_arrangements(song(), song(), trust_tier="A").trust_tier == "A"


def test_an_empty_reference_is_review_required_not_a_crash_or_a_pass() -> None:
    result = compare_arrangements([], song(), trust_tier="A")
    assert result.verdict == "REVIEW_REQUIRED" and result.reasons == ("NO_REFERENCE_EVENTS",)


def test_the_sanitized_report_has_only_aggregates_never_notes() -> None:
    report = compare_arrangements(song(), mutate_timing_phase(song(), 0.1), trust_tier="B").sanitized()
    text = json.dumps(report)
    assert set(report) >= {"trust_tier", "verdict", "reasons", "counts", "recall", "precision", "pitch_agreement"}
    assert "onset_seconds" not in text and "midi" not in text and "string" not in report.get("counts", {})
    assert json.loads(text) == report  # plain JSON-serializable


def test_invalid_note_times_are_refused() -> None:
    with pytest.raises(ValueError):
        DiffNote(float("nan"), 0.4, 40)
    with pytest.raises(ValueError):
        DiffNote(-1.0, 0.4, 40)


def test_custom_thresholds_are_honoured() -> None:
    strict = Thresholds(pass_phase_seconds=0.001, fail_phase_seconds=0.002)
    result = compare_arrangements(song(), mutate_timing_phase(song(), 0.01), trust_tier="A", thresholds=strict)
    assert result.verdict == "FAIL"


# ---- adversarial controls (review of #758): a repeated riff or cancelling errors must not hide a timing fault ----------

def riff(count: int, spacing: float, pitch: int = 40) -> list[DiffNote]:
    return [DiffNote(round(i * spacing, 6), spacing * 0.8, pitch, string=0, fret=0) for i in range(count)]


def test_a_repeated_pitch_riff_cannot_hide_a_global_timing_shift() -> None:
    """100 identical-pitch notes 0.125 s apart shifted by 0.12 s used to pair with their neighbours and PASS."""
    result = compare_arrangements(riff(100, 0.125), mutate_timing_phase(riff(100, 0.125), 0.12), trust_tier="A")
    assert result.verdict == "FAIL" and "TIMING_PHASE_ERROR" in result.reasons
    assert result.onset_phase_seconds == pytest.approx(0.12, abs=1e-6)
    assert result.matched_notes == 100


@pytest.mark.parametrize("shift", [0.25, 0.5, 2.0, 4.0])
def test_a_periodic_riff_shifted_by_a_beat_a_bar_or_a_period_is_still_a_timing_failure(shift: float) -> None:
    reference = song(count=64)  # an 8-note pitch cycle, one note every half second
    result = compare_arrangements(reference, mutate_timing_phase(reference, shift), trust_tier="A")
    assert result.verdict == "FAIL" and "TIMING_PHASE_ERROR" in result.reasons
    assert result.onset_phase_seconds == pytest.approx(shift, abs=1e-6)


def test_cancelling_onset_errors_cannot_pass_on_a_clean_fitted_clock() -> None:
    """Zero fitted phase and drift, perfect recall, but every note 0.15 s off: the residual must fail the comparison."""
    reference = [DiffNote(1.0 + i, 0.4, PITCHES[i % len(PITCHES)]) for i in range(40)]
    generated = [replace_onset(n, 0.15 if i % 4 in (0, 3) else -0.15) for i, n in enumerate(reference)]
    result = compare_arrangements(reference, generated, trust_tier="A")
    assert result.recall == 1.0 and abs(result.onset_phase_seconds or 0.0) < 0.01
    assert result.onset_jitter_seconds == pytest.approx(0.15, abs=0.01)
    assert result.verdict == "FAIL" and "TIMING_JITTER" in result.reasons


def replace_onset(note: DiffNote, delta: float) -> DiffNote:
    return DiffNote(note.onset_seconds + delta, note.duration_seconds, note.midi, note.string, note.fret)


def test_a_few_badly_mistimed_notes_are_counted_as_outliers_and_stop_a_clean_pass() -> None:
    reference = song(count=100)
    generated = [replace_onset(n, 0.1) if i % 10 == 0 else n for i, n in enumerate(reference)]  # 10% off by 0.1 s
    result = compare_arrangements(reference, generated, trust_tier="A")
    assert result.onset_outlier_fraction == pytest.approx(0.1, abs=0.03)
    assert result.verdict == "REVIEW_REQUIRED"


def test_a_late_first_note_with_an_otherwise_aligned_arrangement_is_not_a_clean_pass() -> None:
    reference = song(count=200)
    generated = [replace_onset(n, 0.2) if i == 0 else n for i, n in enumerate(reference)]
    result = compare_arrangements(reference, generated, trust_tier="A")
    assert result.first_event_phase_seconds == pytest.approx(0.2)
    assert result.verdict != "PASS"


def test_alignment_of_a_full_length_song_is_fast_enough_for_the_unattended_lane() -> None:
    import time

    reference = song(count=1500, spacing=0.2)
    started = time.perf_counter()
    result = compare_arrangements(reference, mutate_timing_phase(reference, 0.01), trust_tier="A")
    assert result.verdict == "PASS" and time.perf_counter() - started < 60
