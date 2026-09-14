from types import SimpleNamespace

import pytest

from rocksmith_cdlc_generator.beats import BeatEvent, TempoMap
from rocksmith_cdlc_generator.mobile_product_reality import build_mobile_review_report
from rocksmith_cdlc_generator.score_source import ArrangementRole


def _tempo_map() -> TempoMap:
    return TempoMap(
        engine="fixture",
        beats=[
            BeatEvent(time=7.0, beat=1, measure=1, bpm=120.0, confidence=1.0, is_downbeat=True),
            BeatEvent(time=7.5, beat=2, measure=1, bpm=120.0, confidence=1.0),
            BeatEvent(time=8.0, beat=3, measure=1, bpm=120.0, confidence=1.0),
            BeatEvent(time=8.5, beat=4, measure=1, bpm=120.0, confidence=1.0),
        ],
    )


def _evidence(*, observed: float, expected: float):
    first_check = SimpleNamespace(
        code="bass_first_event",
        status="PASS",
        message="first event measured",
        observed=observed,
        expected=expected,
    )
    role_observation = SimpleNamespace(
        role=ArrangementRole.bass,
        first_playable_seconds=observed,
    )
    return SimpleNamespace(
        checks=[first_check],
        checkpoint_observations=[],
        role_observations=[role_observation],
        build=SimpleNamespace(commit_sha="a" * 40),
        scenario_id="beat-phase-wiring",
        scenario_sha256="b" * 64,
        observed_at_utc="2026-09-14T06:45:00Z",
        project_recording_sha256="c" * 64,
        tempo_map_sha256="d" * 64,
        result="PASS",
        human_only_acceptance=[],
    )


def test_mobile_report_uses_authoritative_tempo_map_for_true_beat_phase() -> None:
    report = build_mobile_review_report(
        _evidence(observed=8.0, expected=7.5),
        tempo_map=_tempo_map(),
    )

    assert report["arrangements"][0]["phase_beats"] == pytest.approx(1.0)


def test_mobile_report_leaves_phase_unknown_without_authoritative_tempo_map() -> None:
    report = build_mobile_review_report(_evidence(observed=8.0, expected=7.5))

    assert report["arrangements"][0]["phase_beats"] == "UNKNOWN"


def test_mobile_report_fails_closed_to_unknown_outside_known_beat_lattice() -> None:
    report = build_mobile_review_report(
        _evidence(observed=9.0, expected=7.5),
        tempo_map=_tempo_map(),
    )

    assert report["arrangements"][0]["phase_beats"] == "UNKNOWN"
