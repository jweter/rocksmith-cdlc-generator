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
    # Earliest phase wins as a mapping hypothesis, but the later complete
    # two-measure repeat makes the absolute alignment unverified.
    assert solution.phase_ambiguous is True
    assert solution.equivalent_best_phases >= 2


def test_near_tied_onset_count_does_not_let_a_later_full_match_silently_outrank_the_true_earliest_phase() -> None:
    # Reproduces the exact #431 failure class: the true earliest phase (click 12)
    # is missing one onset (one undetected/noisy attack is ordinary in real
    # transcription), while a later, fully-repeated riff (click 20, two measures
    # later) matches every onset. Strict "most onsets wins" would hand authority
    # to click 20 with phase_ambiguous=False -- a confident, silent, wrong answer.
    times = [1.13 + 0.5 * index for index in range(48)]
    tempo_map = _tempo_map(times)
    symbolic = [0.0, 0.5, 1.75, 3.0, 4.25, 6.0]

    def mapped(phase: int, position: float) -> float:
        return map_symbolic_beat_to_audio_time(
            tempo_map,
            audio_beat_start_index=phase,
            symbolic_beat_position=position,
        )

    # Click 12 is missing its last onset; click 20 matches the complete riff.
    audio_onsets = [mapped(12, position) for position in symbolic][:-1]
    audio_onsets.extend(mapped(20, position) for position in symbolic)
    audio_onsets.extend([2.31, 3.87, 14.42, 18.09])

    solution = solve_beat_phase(
        tempo_map,
        symbolic_onset_positions=symbolic,
        audio_onsets_seconds=audio_onsets,
        max_start_index=24,
        tolerance_seconds=0.03,
    )

    # The true earliest phase must win, not the later fully-matched repeat.
    assert solution.audio_beat_start_index == 12
    assert solution.matched_onsets == len(symbolic) - 1
    # Two genuinely competitive phases remain -- this must be surfaced as
    # ambiguous so downstream trust cannot treat it as an unqualified PASS.
    assert solution.phase_ambiguous is True
    assert solution.equivalent_best_phases == 2


def test_a_one_beat_neighboring_alias_cannot_outrank_a_unique_complete_match() -> None:
    # Production-shaped regression (reported by independent review against the
    # prior fix above): a longer onset prefix at the default tolerance dilutes a
    # single missed-onset penalty below the equivalence tolerance, so a trivial
    # one-beat-shifted window recovering nearly every onset by arithmetic
    # coincidence must not be allowed to contend with a unique, complete,
    # correctly placed phase.
    times = [0.5 * index for index in range(60)]
    tempo_map = _tempo_map(times)
    symbolic = list(range(12))

    def mapped(phase: int, position: float) -> float:
        return map_symbolic_beat_to_audio_time(
            tempo_map,
            audio_beat_start_index=phase,
            symbolic_beat_position=position,
        )

    audio_onsets = [mapped(12, position) for position in symbolic]

    solution = solve_beat_phase(
        tempo_map,
        symbolic_onset_positions=symbolic,
        audio_onsets_seconds=audio_onsets,
        tolerance_seconds=0.20,
    )

    assert solution.audio_beat_start_index == 12
    assert solution.matched_onsets == len(symbolic)
    assert solution.phase_ambiguous is False
    assert solution.equivalent_best_phases == 1


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


def test_unique_onset_phase_is_not_falsely_classified_as_ambiguous() -> None:
    tempo_map = _tempo_map([1.13 + .5 * index for index in range(48)])
    symbolic = [0.0, .5, 1.75, 3.0, 4.25, 6.0]
    onsets = [
        map_symbolic_beat_to_audio_time(
            tempo_map, audio_beat_start_index=12, symbolic_beat_position=position
        )
        for position in symbolic
    ]
    solution = solve_beat_phase(
        tempo_map, symbolic_onset_positions=symbolic,
        audio_onsets_seconds=onsets, max_start_index=24,
        tolerance_seconds=.03,
    )
    assert solution.audio_beat_start_index == 12
    assert solution.phase_ambiguous is False
    assert solution.equivalent_best_phases == 1
