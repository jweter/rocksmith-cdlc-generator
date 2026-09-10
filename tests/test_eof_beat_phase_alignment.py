from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.beats import BeatEvent, TempoMap
from rocksmith_cdlc_generator.eof_beat_phase_alignment import (
    map_symbolic_beat_to_audio_time,
    solve_beat_phase,
    symbolic_beat_position_from_source_time,
)


def _tempo_map(times: list[float]) -> TempoMap:
    beats = [
        BeatEvent(
            time=time,
            beat=(index % 4) + 1,
            measure=(index // 4) + 1,
            bpm=120.0,
            confidence=0.98,
            is_downbeat=index % 4 == 0,
        )
        for index, time in enumerate(times)
    ]
    return TempoMap(engine="test", beats=beats)


def test_recovers_symbolic_fractional_position_without_using_source_seconds_as_audio_clock() -> None:
    source_beats = [0.0, 0.5, 1.0, 1.5]

    assert symbolic_beat_position_from_source_time(source_beats, 0.75) == pytest.approx(1.5)


def test_maps_subbeat_position_by_interpolating_authoritative_audio_beats() -> None:
    tempo_map = _tempo_map([4.0, 4.5, 5.1, 5.55, 6.2])

    mapped = map_symbolic_beat_to_audio_time(
        tempo_map,
        audio_beat_start_index=0,
        symbolic_beat_position=1.5,
    )

    assert mapped == pytest.approx(4.8)


def test_phase_solver_finds_which_click_is_symbolic_beat_zero_and_prefers_earliest_repeat() -> None:
    # The recording beat lattice is already correct. Symbolic beat zero belongs to
    # audio click 12 (7.13 s). A later repeated phrase at click 20 is deliberately
    # present to reproduce the failure class that previously bound two measures late.
    times = [1.13 + 0.5 * index for index in range(48)]
    tempo_map = _tempo_map(times)
    symbolic = [0.0, 0.5, 1.75, 3.0, 4.25, 6.0]

    def mapped(phase: int, position: float) -> float:
        return map_symbolic_beat_to_audio_time(
            tempo_map,
            audio_beat_start_index=phase,
            symbolic_beat_position=position,
        )

    audio_onsets = [mapped(12, position) for position in symbolic]
    # A complete later repeat must not steal authority from the first reliable match.
    audio_onsets.extend(mapped(20, position) for position in symbolic)
    # Unrelated attacks make the evidence look more like a real transcription.
    audio_onsets.extend([2.31, 3.87, 14.42, 18.09])

    solution = solve_beat_phase(
        tempo_map,
        symbolic_onset_positions=symbolic,
        audio_onsets_seconds=audio_onsets,
        max_start_index=24,
        tolerance_seconds=0.03,
    )

    assert solution.audio_beat_start_index == 12
    assert tempo_map.beats[solution.audio_beat_start_index].time == pytest.approx(7.13)
    assert solution.matched_onsets == len(symbolic)
    assert solution.mean_abs_error_seconds == pytest.approx(0.0)


def test_all_arrangements_can_share_one_phase_transform() -> None:
    times = [5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5]
    tempo_map = _tempo_map(times)
    phase = 2

    bass = map_symbolic_beat_to_audio_time(
        tempo_map, audio_beat_start_index=phase, symbolic_beat_position=0.0
    )
    lead = map_symbolic_beat_to_audio_time(
        tempo_map, audio_beat_start_index=phase, symbolic_beat_position=0.5
    )
    rhythm = map_symbolic_beat_to_audio_time(
        tempo_map, audio_beat_start_index=phase, symbolic_beat_position=1.0
    )

    assert bass == pytest.approx(6.0)
    assert lead == pytest.approx(6.25)
    assert rhythm == pytest.approx(6.5)


def test_phase_solver_fails_closed_when_audio_evidence_is_insufficient() -> None:
    tempo_map = _tempo_map([1.0 + 0.5 * index for index in range(24)])

    with pytest.raises(ValueError, match="review-required"):
        solve_beat_phase(
            tempo_map,
            symbolic_onset_positions=[0.0, 0.5, 1.75, 3.0, 4.25, 6.0],
            audio_onsets_seconds=[2.01, 9.17],
            max_start_index=12,
            tolerance_seconds=0.03,
        )
