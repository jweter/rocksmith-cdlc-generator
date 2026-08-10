from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field

from .fretboard import BassTuning, FretPosition, candidate_positions
from .transcription import BassTranscription, NoteEvent, read_transcription


class MappedNote(BaseModel):
    start: float = Field(ge=0.0)
    duration: float = Field(gt=0.0)
    midi: int = Field(ge=0, le=127)
    string: int | None = Field(default=None, ge=0, le=3)
    fret: int | None = Field(default=None, ge=0)
    source_confidence: float = Field(ge=0.0, le=1.0)
    mapping_confidence: float = Field(ge=0.0, le=1.0)
    review_required: bool = False
    alternate_positions: list[FretPosition] = []

    @property
    def mapped(self) -> bool:
        return self.string is not None and self.fret is not None


class BassMapping(BaseModel):
    schema_version: int = 1
    tuning: BassTuning
    max_fret: int = Field(ge=0)
    notes: list[MappedNote]

    @property
    def unmapped_count(self) -> int:
        return sum(not note.mapped for note in self.notes)


@dataclass(frozen=True)
class MappingWeights:
    fret_movement: float = 1.0
    string_crossing: float = 1.35
    high_fret_bias: float = 0.035
    open_string_bonus: float = 0.20
    large_jump_threshold: int = 7
    large_jump_penalty: float = 0.65


def _position_cost(position: FretPosition, weights: MappingWeights) -> float:
    cost = position.fret * weights.high_fret_bias
    if position.fret == 0:
        cost -= weights.open_string_bonus
    return cost


def _transition_cost(
    previous: FretPosition,
    current: FretPosition,
    weights: MappingWeights,
) -> float:
    fret_delta = abs(current.fret - previous.fret)
    string_delta = abs(current.string - previous.string)
    cost = fret_delta * weights.fret_movement + string_delta * weights.string_crossing
    if fret_delta > weights.large_jump_threshold:
        cost += (fret_delta - weights.large_jump_threshold) * weights.large_jump_penalty
    return cost


def _confidence_from_margin(best_cost: float, second_cost: float | None) -> float:
    if second_cost is None:
        return 0.92
    margin = max(0.0, second_cost - best_cost)
    return min(0.99, 0.55 + margin / (margin + 5.0) * 0.44)


def map_bass_transcription(
    transcription: BassTranscription,
    tuning: BassTuning,
    *,
    max_fret: int = 24,
    weights: MappingWeights = MappingWeights(),
) -> BassMapping:
    """Choose a globally coherent fret/string path using dynamic programming."""

    candidate_sets = [candidate_positions(note.midi, tuning, max_fret=max_fret) for note in transcription.notes]
    mapped_notes: list[MappedNote | None] = [None] * len(transcription.notes)

    segment_start = 0
    while segment_start < len(transcription.notes):
        while segment_start < len(transcription.notes) and not candidate_sets[segment_start]:
            note = transcription.notes[segment_start]
            mapped_notes[segment_start] = MappedNote(
                start=note.start,
                duration=note.duration,
                midi=note.midi,
                source_confidence=note.confidence,
                mapping_confidence=0.0,
                review_required=True,
                alternate_positions=[],
            )
            segment_start += 1
        if segment_start >= len(transcription.notes):
            break

        segment_end = segment_start
        while segment_end < len(transcription.notes) and candidate_sets[segment_end]:
            segment_end += 1

        costs: list[list[float]] = []
        backrefs: list[list[int | None]] = []
        first_candidates = candidate_sets[segment_start]
        costs.append([_position_cost(position, weights) for position in first_candidates])
        backrefs.append([None] * len(first_candidates))

        for index in range(segment_start + 1, segment_end):
            current_candidates = candidate_sets[index]
            previous_candidates = candidate_sets[index - 1]
            current_costs: list[float] = []
            current_backrefs: list[int | None] = []
            for current in current_candidates:
                options = [
                    costs[-1][prev_index]
                    + _transition_cost(previous, current, weights)
                    + _position_cost(current, weights)
                    for prev_index, previous in enumerate(previous_candidates)
                ]
                best_prev = min(range(len(options)), key=options.__getitem__)
                current_costs.append(options[best_prev])
                current_backrefs.append(best_prev)
            costs.append(current_costs)
            backrefs.append(current_backrefs)

        final_costs = costs[-1]
        chosen = min(range(len(final_costs)), key=final_costs.__getitem__)
        chosen_indices = [chosen]
        for layer in range(len(backrefs) - 1, 0, -1):
            previous_index = backrefs[layer][chosen_indices[-1]]
            assert previous_index is not None
            chosen_indices.append(previous_index)
        chosen_indices.reverse()

        for offset, candidate_index in enumerate(chosen_indices):
            note_index = segment_start + offset
            note = transcription.notes[note_index]
            candidates = candidate_sets[note_index]
            selected = candidates[candidate_index]

            local_costs = []
            previous_selected = None
            if offset > 0:
                previous_selected = candidate_sets[note_index - 1][chosen_indices[offset - 1]]
            for candidate in candidates:
                cost = _position_cost(candidate, weights)
                if previous_selected is not None:
                    cost += _transition_cost(previous_selected, candidate, weights)
                local_costs.append(cost)
            ranked = sorted(local_costs)
            second_cost = ranked[1] if len(ranked) > 1 else None
            mapping_confidence = _confidence_from_margin(local_costs[candidate_index], second_cost)
            alternates = [candidate for idx, candidate in enumerate(candidates) if idx != candidate_index]
            review_required = note.review_required or mapping_confidence < 0.65

            mapped_notes[note_index] = MappedNote(
                start=note.start,
                duration=note.duration,
                midi=note.midi,
                string=selected.string,
                fret=selected.fret,
                source_confidence=note.confidence,
                mapping_confidence=mapping_confidence,
                review_required=review_required,
                alternate_positions=alternates,
            )

        segment_start = segment_end

    return BassMapping(
        tuning=tuning,
        max_fret=max_fret,
        notes=[note for note in mapped_notes if note is not None],
    )


def write_bass_mapping(mapping: BassMapping, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(mapping.model_dump_json(indent=2), encoding="utf-8")


def read_bass_mapping(path: Path) -> BassMapping:
    return BassMapping.model_validate_json(path.read_text(encoding="utf-8"))
