from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from math import ceil, floor
from typing import Sequence

from .beats import TempoMap


@dataclass(frozen=True)
class BeatPhaseCandidate:
    """One candidate mapping from symbolic beat zero to the audio beat lattice."""

    audio_beat_start_index: int
    matched_onsets: int
    total_onsets: int
    mean_abs_error_seconds: float

    @property
    def match_fraction(self) -> float:
        if self.total_onsets <= 0:
            return 0.0
        return self.matched_onsets / self.total_onsets


@dataclass(frozen=True)
class BeatPhaseSolution:
    """Authoritative symbolic-beat -> audio-beat phase decision.

    ``audio_beat_start_index`` is the only phase authority. No song-specific or
    free-floating global-seconds correction is stored here. Sub-beat positions are
    interpolated between the corresponding audio beat anchors.
    """

    audio_beat_start_index: int
    matched_onsets: int
    total_onsets: int
    mean_abs_error_seconds: float
    candidate_count: int


def symbolic_beat_position_from_source_time(
    source_beat_times_seconds: Sequence[float],
    source_time_seconds: float,
) -> float:
    """Recover a symbolic fractional beat position from legacy GP source timing.

    Guitar Pro's tempo map may recover musical coordinates, but its absolute seconds
    are not allowed to become the recording clock. The returned value is a beat
    coordinate: 0.0 is source beat zero and 1.5 is halfway through source beat one.
    """

    if len(source_beat_times_seconds) < 2:
        raise ValueError("at least two source beat times are required")
    if any(
        current <= previous
        for previous, current in zip(source_beat_times_seconds, source_beat_times_seconds[1:])
    ):
        raise ValueError("source beat times must be strictly increasing")

    if source_time_seconds <= source_beat_times_seconds[0]:
        left = 0
    elif source_time_seconds >= source_beat_times_seconds[-1]:
        left = len(source_beat_times_seconds) - 2
    else:
        right = bisect_right(source_beat_times_seconds, source_time_seconds)
        left = right - 1

    start = source_beat_times_seconds[left]
    end = source_beat_times_seconds[left + 1]
    fraction = (source_time_seconds - start) / (end - start)
    return float(left) + fraction


def map_symbolic_beat_to_audio_time(
    tempo_map: TempoMap,
    *,
    audio_beat_start_index: int,
    symbolic_beat_position: float,
) -> float:
    """Map one symbolic beat coordinate onto the authoritative audio beat grid.

    Notes are never rounded to clicks. Fractional beat positions are linearly
    interpolated between adjacent audio beat anchors so eighths, sixteenths, tuplets,
    pickups and syncopation remain intact.
    """

    if symbolic_beat_position < 0.0:
        raise ValueError("symbolic beat position must be non-negative")
    if len(tempo_map.beats) < 2:
        raise ValueError("audio tempo map needs at least two beats")
    if audio_beat_start_index < 0 or audio_beat_start_index >= len(tempo_map.beats) - 1:
        raise ValueError("audio beat start index is outside the tempo map")

    whole = floor(symbolic_beat_position)
    fraction = symbolic_beat_position - whole
    left_index = audio_beat_start_index + whole
    right_index = left_index + 1
    if right_index >= len(tempo_map.beats):
        raise ValueError("symbolic beat position extends beyond the audio tempo map")

    left_time = tempo_map.beats[left_index].time
    right_time = tempo_map.beats[right_index].time
    return left_time + fraction * (right_time - left_time)


def _nearest_onset_error(
    audio_onsets_seconds: Sequence[float],
    target_seconds: float,
    tolerance_seconds: float,
) -> float | None:
    left = bisect_left(audio_onsets_seconds, target_seconds - tolerance_seconds)
    right = bisect_right(audio_onsets_seconds, target_seconds + tolerance_seconds)
    if left >= right:
        return None
    return min(abs(audio_onsets_seconds[index] - target_seconds) for index in range(left, right))


def score_beat_phase_candidate(
    tempo_map: TempoMap,
    *,
    audio_beat_start_index: int,
    symbolic_onset_positions: Sequence[float],
    audio_onsets_seconds: Sequence[float],
    tolerance_seconds: float = 0.20,
) -> BeatPhaseCandidate:
    """Score one beat-index phase without introducing an arbitrary time shift."""

    if tolerance_seconds <= 0.0:
        raise ValueError("tolerance_seconds must be positive")
    if not symbolic_onset_positions:
        raise ValueError("at least one symbolic onset is required")

    ordered_audio = sorted(audio_onsets_seconds)
    errors: list[float] = []
    for position in symbolic_onset_positions:
        try:
            target = map_symbolic_beat_to_audio_time(
                tempo_map,
                audio_beat_start_index=audio_beat_start_index,
                symbolic_beat_position=position,
            )
        except ValueError:
            continue
        error = _nearest_onset_error(ordered_audio, target, tolerance_seconds)
        if error is not None:
            errors.append(error)

    mean_error = sum(errors) / len(errors) if errors else float("inf")
    return BeatPhaseCandidate(
        audio_beat_start_index=audio_beat_start_index,
        matched_onsets=len(errors),
        total_onsets=len(symbolic_onset_positions),
        mean_abs_error_seconds=mean_error,
    )


def solve_beat_phase(
    tempo_map: TempoMap,
    *,
    symbolic_onset_positions: Sequence[float],
    audio_onsets_seconds: Sequence[float],
    max_start_index: int | None = None,
    tolerance_seconds: float = 0.20,
    minimum_matches: int = 4,
    minimum_match_fraction: float = 0.60,
) -> BeatPhaseSolution:
    """Find which audio click corresponds to symbolic beat zero.

    Candidate phases are evaluated only at real beat-grid indices. Maximum onset support
    wins first. If multiple phases have the same strongest support, the earliest reliable
    phase wins, preventing a complete score from binding to a later repeated riff without
    allowing an earlier but objectively weaker phase to steal authority.
    """

    if not symbolic_onset_positions:
        raise ValueError("at least one symbolic onset is required")
    if minimum_matches < 1:
        raise ValueError("minimum_matches must be positive")
    if not 0.0 < minimum_match_fraction <= 1.0:
        raise ValueError("minimum_match_fraction must be in (0, 1]")
    if len(tempo_map.beats) < 2:
        raise ValueError("audio tempo map needs at least two beats")

    highest_position = max(symbolic_onset_positions)
    needed_beats = floor(highest_position) + 2
    natural_max = len(tempo_map.beats) - needed_beats
    if natural_max < 0:
        raise ValueError("audio tempo map is shorter than the symbolic onset prefix")
    search_max = natural_max if max_start_index is None else min(max_start_index, natural_max)
    if search_max < 0:
        raise ValueError("max_start_index leaves no phase candidates")

    candidates = [
        score_beat_phase_candidate(
            tempo_map,
            audio_beat_start_index=index,
            symbolic_onset_positions=symbolic_onset_positions,
            audio_onsets_seconds=audio_onsets_seconds,
            tolerance_seconds=tolerance_seconds,
        )
        for index in range(search_max + 1)
    ]
    best_matches = max(candidate.matched_onsets for candidate in candidates)
    required = max(
        minimum_matches,
        ceil(len(symbolic_onset_positions) * minimum_match_fraction),
    )
    if best_matches < required:
        raise ValueError(
            "no beat-index phase has enough onset support; timing must remain review-required"
        )

    strongest = [
        candidate
        for candidate in candidates
        if candidate.matched_onsets == best_matches
    ]
    strongest.sort(
        key=lambda candidate: (
            candidate.audio_beat_start_index,
            candidate.mean_abs_error_seconds,
        )
    )
    chosen = strongest[0]
    return BeatPhaseSolution(
        audio_beat_start_index=chosen.audio_beat_start_index,
        matched_onsets=chosen.matched_onsets,
        total_onsets=chosen.total_onsets,
        mean_abs_error_seconds=chosen.mean_abs_error_seconds,
        candidate_count=len(candidates),
    )
