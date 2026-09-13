from __future__ import annotations

from rocksmith_cdlc_generator.arrangement_preview_clock_diagnostics import (
    ClockSample,
    analyze_playback_clock_samples,
)


def _samples(pairs: list[tuple[float, float]]) -> list[ClockSample]:
    return [ClockSample(wall_clock_seconds=wall, position_seconds=position) for wall, position in pairs]


def test_steady_real_time_playback_passes() -> None:
    samples = _samples([(0.0, 0.0), (0.05, 0.05), (0.10, 0.10), (0.15, 0.15), (0.20, 0.20)])

    report = analyze_playback_clock_samples(samples)

    assert report.status == "PASS"
    assert report.anomalies == []
    assert report.sample_count == 5


def test_single_or_empty_sample_lists_pass_trivially() -> None:
    assert analyze_playback_clock_samples([]).status == "PASS"
    assert analyze_playback_clock_samples(_samples([(0.0, 0.0)])).status == "PASS"


def test_small_poll_jitter_does_not_false_positive() -> None:
    """Real polling intervals are not exact; tiny timing noise must not be flagged."""

    samples = _samples([(0.0, 0.0), (0.048, 0.05), (0.101, 0.10), (0.151, 0.155)])

    report = analyze_playback_clock_samples(samples)

    assert report.status == "PASS"


def test_backward_jump_is_detected() -> None:
    samples = _samples([(0.0, 5.0), (0.05, 5.05), (0.10, 4.20), (0.15, 4.25)])

    report = analyze_playback_clock_samples(samples)

    assert report.status == "FAIL"
    codes = [anomaly.code for anomaly in report.anomalies]
    assert "clock_backward_jump" in codes
    anomaly = next(item for item in report.anomalies if item.code == "clock_backward_jump")
    assert anomaly.sample_index == 2
    assert "backward" in anomaly.message


def test_stalled_position_is_detected() -> None:
    samples = _samples([(0.0, 1.0), (0.05, 1.05), (0.10, 1.10), (0.80, 1.10), (0.85, 1.15)])

    report = analyze_playback_clock_samples(samples)

    assert report.status == "FAIL"
    codes = [anomaly.code for anomaly in report.anomalies]
    assert "clock_stalled" in codes
    anomaly = next(item for item in report.anomalies if item.code == "clock_stalled")
    assert anomaly.sample_index == 3


def test_sustained_speed_mismatch_is_detected() -> None:
    """Position advancing twice as fast as wall-clock time, sustained over a real interval."""

    samples = _samples([(0.0, 0.0), (1.0, 2.0)])

    report = analyze_playback_clock_samples(samples)

    assert report.status == "FAIL"
    anomaly = next(item for item in report.anomalies if item.code == "clock_speed_mismatch")
    assert anomaly.sample_index == 1
    assert "100%" in anomaly.message


def test_out_of_order_or_duplicate_wall_clock_samples_are_skipped_not_flagged() -> None:
    samples = _samples([(1.0, 1.0), (1.0, 1.05), (1.05, 1.10)])

    report = analyze_playback_clock_samples(samples)

    assert report.status == "PASS"


def test_custom_tolerances_are_respected() -> None:
    samples = _samples([(0.0, 0.0), (0.2, 0.5)])

    default_report = analyze_playback_clock_samples(samples)
    assert default_report.status == "FAIL"

    lenient_report = analyze_playback_clock_samples(samples, speed_tolerance_ratio=5.0)
    assert lenient_report.status == "PASS"
