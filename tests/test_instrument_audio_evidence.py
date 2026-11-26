from __future__ import annotations

import math

import pytest

from rocksmith_cdlc_generator.instrument_audio_evidence import (
    MAX_FRET,
    plan_instrument_audio_evidence,
    midi_to_hz,
)

BASS_STANDARD = [28, 33, 38, 43]
BASS_DROP_D = [26, 33, 38, 43]
GUITAR_STANDARD = [40, 45, 50, 55, 59, 64]


def _plan(**overrides):
    args = dict(
        instrument="bass", tuning_midi=BASS_STANDARD, score_midi=33,
        string_index=1, fret=0, event_time_s=10.0,
        has_original_mix=True, has_stem=False, stem_is_current=False,
    )
    args.update(overrides)
    return plan_instrument_audio_evidence(**args)


def _status(plan, view):
    return next(v for v in plan.views if v.view == view)


def test_midi_to_hz_reference_pitches():
    assert midi_to_hz(69) == pytest.approx(440.0)
    assert midi_to_hz(28) == pytest.approx(41.2034, abs=1e-3)
    assert midi_to_hz(40) == pytest.approx(82.4069, abs=1e-3)


def test_ready_plan_reports_tuning_and_event_facts():
    plan = _plan()
    assert plan.blocker_code == "NONE"
    assert plan.low_open_midi == 28
    assert plan.low_open_hz == pytest.approx(41.2034, abs=1e-3)
    assert plan.score_midi == 33 and plan.score_hz == pytest.approx(55.0)
    assert plan.score_authority == "score" and plan.is_proof is False


def test_drop_tuning_changes_low_open_pitch():
    plan = _plan(tuning_midi=BASS_DROP_D, score_midi=26, string_index=0)
    assert plan.low_open_midi == 26
    assert plan.low_open_hz == pytest.approx(36.7081, abs=1e-3)


def test_uses_lowest_string_even_if_tuning_listed_unsorted():
    plan = _plan(tuning_midi=[43, 38, 33, 28], score_midi=43, string_index=0)
    assert plan.low_open_midi == 28


def test_band_surrounds_fundamental_and_is_capped():
    plan = _plan()
    assert plan.band_low_hz < plan.score_hz < plan.band_high_hz
    assert plan.band_low_hz == pytest.approx(55.0 * 2 ** (-2 / 12))
    assert plan.band_high_hz == pytest.approx(220.0)
    high = plan_instrument_audio_evidence(
        instrument="lead", tuning_midi=[80] * 6, score_midi=104,
        string_index=5, fret=24, event_time_s=1.0, has_original_mix=True,
    )
    assert high.blocker_code == "NONE"
    assert high.band_high_hz == 8000.0


def test_window_uses_event_time_and_duration_on_recording_clock():
    plan = _plan(event_time_s=10.0, event_duration_s=0.5)
    assert plan.event_time_s == 10.0
    assert plan.window_start_s == pytest.approx(9.75)
    assert plan.window_end_s == pytest.approx(10.75)


def test_window_start_clamped_at_zero_and_minimum_span_applied():
    plan = _plan(event_time_s=0.1, event_duration_s=0.0)
    assert plan.window_start_s == 0.0
    assert plan.window_end_s == pytest.approx(0.1 + 0.1 + 0.25)


def test_default_view_prefers_current_stem():
    plan = _plan(has_stem=True, stem_is_current=True)
    assert plan.default_view == "separated_stem"
    assert _status(plan, "separated_stem").status == "available"


def test_stale_stem_is_never_offered_or_defaulted():
    plan = _plan(has_stem=True, stem_is_current=False)
    assert _status(plan, "separated_stem").status == "stale"
    assert plan.default_view == "frequency_focused"


def test_current_flag_without_a_stem_does_not_make_one_available():
    plan = _plan(has_stem=False, stem_is_current=True)
    assert _status(plan, "separated_stem").status == "unavailable"


def test_mix_only_defaults_to_frequency_focused_and_marks_it_diagnostic():
    plan = _plan()
    assert plan.default_view == "frequency_focused"
    assert _status(plan, "frequency_focused").diagnostic_only is True
    assert _status(plan, "original_mix").diagnostic_only is False
    assert _status(plan, "original_mix").status == "available"


def test_no_recording_offers_nothing_but_keeps_tuning_facts():
    plan = _plan(has_original_mix=False)
    assert plan.blocker_code == "NONE"
    assert plan.default_view is None
    assert all(v.status == "unavailable" for v in plan.views)
    assert plan.low_open_midi == 28


def test_stem_alone_without_mix_still_defaults_to_stem():
    plan = _plan(has_original_mix=False, has_stem=True, stem_is_current=True)
    assert plan.default_view == "separated_stem"


def test_views_are_always_the_three_known_views():
    assert [v.view for v in _plan().views] == [
        "original_mix", "frequency_focused", "separated_stem",
    ]


@pytest.mark.parametrize(
    ("overrides", "blocker"),
    [
        ({"tuning_midi": None}, "INVALID_INSTRUMENT_OR_TUNING"),
        ({"tuning_midi": [28, 33]}, "INVALID_INSTRUMENT_OR_TUNING"),
        ({"tuning_midi": [28, 33, 38, 200]}, "INVALID_INSTRUMENT_OR_TUNING"),
        ({"tuning_midi": [28.0, 33, 38, 43]}, "INVALID_INSTRUMENT_OR_TUNING"),
        ({"tuning_midi": "EADG"}, "INVALID_INSTRUMENT_OR_TUNING"),
        ({"instrument": "keys"}, "INVALID_INSTRUMENT_OR_TUNING"),
        ({"instrument": None}, "INVALID_INSTRUMENT_OR_TUNING"),
        ({"event_time_s": -0.001}, "INVALID_EVENT_TIME"),
        ({"event_time_s": math.nan}, "INVALID_EVENT_TIME"),
        ({"event_time_s": math.inf}, "INVALID_EVENT_TIME"),
        ({"event_time_s": True}, "INVALID_EVENT_TIME"),
        ({"event_time_s": "10"}, "INVALID_EVENT_TIME"),
        ({"event_duration_s": -1.0}, "INVALID_EVENT_TIME"),
        ({"event_duration_s": math.nan}, "INVALID_EVENT_TIME"),
        ({"score_midi": True}, "INVALID_SCORE_PITCH"),
        ({"score_midi": 33.0}, "INVALID_SCORE_PITCH"),
        ({"score_midi": -1}, "INVALID_SCORE_PITCH"),
        ({"score_midi": 128}, "INVALID_SCORE_PITCH"),
        ({"string_index": -1}, "INVALID_STRING_OR_FRET"),
        ({"string_index": 4}, "INVALID_STRING_OR_FRET"),
        ({"string_index": True}, "INVALID_STRING_OR_FRET"),
        ({"string_index": 1.0}, "INVALID_STRING_OR_FRET"),
        ({"fret": -1}, "INVALID_STRING_OR_FRET"),
        ({"fret": MAX_FRET + 1}, "INVALID_STRING_OR_FRET"),
        ({"fret": False}, "INVALID_STRING_OR_FRET"),
        ({"score_midi": 34}, "PITCH_STRING_FRET_MISMATCH"),
        ({"fret": 2}, "PITCH_STRING_FRET_MISMATCH"),
        ({"score_midi": 28}, "PITCH_STRING_FRET_MISMATCH"),
    ],
)
def test_bad_input_fails_closed_with_named_blocker(overrides, blocker):
    plan = _plan(has_original_mix=True, has_stem=True, stem_is_current=True, **overrides)
    assert plan.blocker_code == blocker
    assert plan.views == ()
    assert plan.default_view is None
    assert plan.band_low_hz is None and plan.window_start_s is None
    assert plan.is_proof is False and plan.score_authority == "score"


def test_pitch_above_usable_band_is_blocked():
    plan = plan_instrument_audio_evidence(
        instrument="lead", tuning_midi=[96, 96, 96, 96, 96, 96], score_midi=120,
        string_index=0, fret=24, event_time_s=1.0, has_original_mix=True,
    )
    assert plan.blocker_code == "PITCH_OUTSIDE_AUDIBLE_RANGE"
    assert plan.views == ()


def test_pitch_below_audible_floor_is_blocked():
    plan = plan_instrument_audio_evidence(
        instrument="bass", tuning_midi=[10, 15, 20, 25], score_midi=10,
        string_index=0, fret=0, event_time_s=1.0, has_original_mix=True,
    )
    assert plan.blocker_code == "PITCH_OUTSIDE_AUDIBLE_RANGE"


def test_extended_range_and_seven_string_guitar_supported():
    plan = plan_instrument_audio_evidence(
        instrument="rhythm", tuning_midi=[35, 40, 45, 50, 55, 59, 64],
        score_midi=35, string_index=0, fret=0, event_time_s=2.0,
        has_original_mix=True,
    )
    assert plan.blocker_code == "NONE" and plan.low_open_midi == 35


def test_plan_is_immutable_and_never_proof():
    plan = _plan(has_stem=True, stem_is_current=True)
    with pytest.raises(Exception):
        plan.is_proof = True  # type: ignore[misc]
    assert plan.is_proof is False
