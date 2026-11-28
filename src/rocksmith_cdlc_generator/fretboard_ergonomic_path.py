from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from .fretboard_candidate_inventory import FretboardCandidateInventory, FretboardPositionCandidate

FingeringSource = Literal["explicit_score", "ergonomic_suggestion"]


class EventFingeringChoice(BaseModel):
    """One event's position in the advisory phrase-level ergonomic path."""

    model_config = ConfigDict(frozen=True)

    event_index: int = Field(ge=0)
    string_index: int = Field(ge=0)
    fret: int = Field(ge=0)
    fingering_source: FingeringSource


class ErgonomicFingeringPath(BaseModel):
    """Advisory phrase-level fretboard path that keeps valid explicit fingering fixed.

    This is a read-only review aid, not an authored fingering. Every event whose
    declared source string/fret is already one of FretboardCandidateInventory's
    pitch-correct candidates ("explicit_score") is never moved. The path only
    chooses among the remaining pitch-correct candidates for ambiguous, missing, or
    pitch-inconsistent events, minimizing total hand travel (summed fret and string
    distance between consecutive chosen positions) across the whole phrase. It does
    not rewrite source notation, auto-author chart fingering, feed export, or weaken
    any existing review/playability authority -- it is strictly additive evidence for
    a future human-reviewed fingering decision.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_track_index: int = Field(ge=0)
    tuning_midi: list[int] = Field(min_length=1)
    choices: list[EventFingeringChoice]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_hand_travel(self) -> int:
        return sum(
            _movement_cost(previous, current)
            for previous, current in zip(self.choices, self.choices[1:])
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ergonomic_suggestion_count(self) -> int:
        return sum(choice.fingering_source == "ergonomic_suggestion" for choice in self.choices)


def _movement_cost(a: EventFingeringChoice | FretboardPositionCandidate, b: EventFingeringChoice | FretboardPositionCandidate) -> int:
    return abs(a.fret - b.fret) + abs(a.string_index - b.string_index)


def build_ergonomic_fingering_path(inventory: FretboardCandidateInventory) -> ErgonomicFingeringPath:
    """Choose one pitch-correct position per event, pinning valid explicit fingering.

    Ambiguous, missing, and pitch-inconsistent events are resolved with a
    deterministic shortest-path search (Viterbi-style dynamic programming) over
    FretboardCandidateInventory's own pitch-correct candidates, minimizing total hand
    travel across the phrase. Events whose declared source position already matches a
    pitch-correct candidate keep that exact position regardless of ergonomic cost.
    Ties are broken by lowest string index then lowest fret, so the result is
    deterministic independent of dict/set ordering.
    """

    if not inventory.events:
        return ErgonomicFingeringPath(
            source_sha256=inventory.source_sha256,
            source_track_index=inventory.source_track_index,
            tuning_midi=inventory.tuning_midi,
            choices=[],
        )

    options: list[list[FretboardPositionCandidate]] = []
    for event in inventory.events:
        if event.source_position_status == "candidate":
            assert event.source_string_index is not None and event.source_fret is not None
            options.append(
                [
                    FretboardPositionCandidate(
                        string_index=event.source_string_index, fret=event.source_fret
                    )
                ]
            )
        else:
            options.append(
                sorted(event.candidates, key=lambda item: (item.string_index, item.fret))
            )

    # Viterbi-style dynamic programming: best_cost[i][k] is the minimal total hand
    # travel of any path ending at options[i][k]; best_predecessor records the
    # (lowest-sorted, hence deterministic) predecessor index achieving that minimum.
    best_cost: list[list[int]] = [[0 for _ in options[0]]]
    best_predecessor: list[list[int]] = [[-1 for _ in options[0]]]
    for event_index in range(1, len(options)):
        previous_costs = best_cost[event_index - 1]
        current_costs: list[int] = []
        current_predecessors: list[int] = []
        for candidate in options[event_index]:
            min_cost = None
            min_predecessor = -1
            for predecessor_index, predecessor_candidate in enumerate(options[event_index - 1]):
                cost = previous_costs[predecessor_index] + _movement_cost(
                    predecessor_candidate, candidate
                )
                if min_cost is None or cost < min_cost:
                    min_cost = cost
                    min_predecessor = predecessor_index
            current_costs.append(min_cost if min_cost is not None else 0)
            current_predecessors.append(min_predecessor)
        best_cost.append(current_costs)
        best_predecessor.append(current_predecessors)

    last_index = len(options) - 1
    chosen_index = min(range(len(options[last_index])), key=lambda i: best_cost[last_index][i])
    chosen_indices = [0] * len(options)
    chosen_indices[last_index] = chosen_index
    for event_index in range(last_index, 0, -1):
        chosen_indices[event_index - 1] = best_predecessor[event_index][chosen_indices[event_index]]

    choices = [
        EventFingeringChoice(
            event_index=event.event_index,
            string_index=event_options[chosen].string_index,
            fret=event_options[chosen].fret,
            fingering_source=(
                "explicit_score" if event.source_position_status == "candidate" else "ergonomic_suggestion"
            ),
        )
        for event, event_options, chosen in zip(inventory.events, options, chosen_indices)
    ]

    return ErgonomicFingeringPath(
        source_sha256=inventory.source_sha256,
        source_track_index=inventory.source_track_index,
        tuning_midi=inventory.tuning_midi,
        choices=choices,
    )
