from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .fretboard import BassTuning, FretPosition, candidate_positions
from .source_import import SourceTrustClass
from .transcription import BassTranscription, NoteEvent

# Bump whenever a change to fret-mapping logic can change which notes map/fail for an
# already-mapped project (for example the #322 fix that stopped promoting audio_only
# reconciliation evidence into authoritative Bass fret mapping). `bass_mapping_is_current`
# uses this to detect an on-disk `charts/bass_mapped.json` that predates the current
# algorithm so stale mapping output is not silently treated as complete/authoritative
# (recurring stale-derivative-state pattern tracked in #193).
CURRENT_BASS_MAPPING_ALGORITHM_VERSION = 2


class MappedNote(BaseModel):
    start: float = Field(ge=0.0)
    duration: float = Field(gt=0.0)
    midi: int = Field(ge=0, le=127)
    string: int | None = Field(default=None, ge=0, le=3)
    fret: int | None = Field(default=None, ge=0)
    source_confidence: float = Field(ge=0.0, le=1.0)
    mapping_confidence: float = Field(ge=0.0, le=1.0)
    review_required: bool = False
    alternate_positions: list[FretPosition] = Field(default_factory=list)
    position_source: Literal["inferred", "symbolic"] = "inferred"
    techniques: list[str] = Field(default_factory=list)
    trust_class: SourceTrustClass | None = None

    @property
    def mapped(self) -> bool:
        return self.string is not None and self.fret is not None


class BassMapping(BaseModel):
    schema_version: int = 1
    mapping_algorithm_version: int = CURRENT_BASS_MAPPING_ALGORITHM_VERSION
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


def _transition_cost(previous: FretPosition, current: FretPosition, weights: MappingWeights) -> float:
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
            mapped_notes[segment_start] = MappedNote(start=note.start, duration=note.duration, midi=note.midi, source_confidence=note.confidence, mapping_confidence=0.0, review_required=True)
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
                options = [costs[-1][prev_index] + _transition_cost(previous, current, weights) + _position_cost(current, weights) for prev_index, previous in enumerate(previous_candidates)]
                best_prev = min(range(len(options)), key=options.__getitem__)
                current_costs.append(options[best_prev])
                current_backrefs.append(best_prev)
            costs.append(current_costs)
            backrefs.append(current_backrefs)
        chosen = min(range(len(costs[-1])), key=costs[-1].__getitem__)
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
            previous_selected = candidate_sets[note_index - 1][chosen_indices[offset - 1]] if offset > 0 else None
            local_costs = [_position_cost(candidate, weights) + (_transition_cost(previous_selected, candidate, weights) if previous_selected is not None else 0.0) for candidate in candidates]
            ranked = sorted(local_costs)
            second_cost = ranked[1] if len(ranked) > 1 else None
            mapping_confidence = _confidence_from_margin(local_costs[candidate_index], second_cost)
            mapped_notes[note_index] = MappedNote(
                start=note.start,
                duration=note.duration,
                midi=note.midi,
                string=selected.string,
                fret=selected.fret,
                source_confidence=note.confidence,
                mapping_confidence=mapping_confidence,
                review_required=note.review_required or mapping_confidence < 0.65,
                alternate_positions=[candidate for idx, candidate in enumerate(candidates) if idx != candidate_index],
            )
        segment_start = segment_end
    return BassMapping(tuning=tuning, max_fret=max_fret, notes=[note for note in mapped_notes if note is not None])


def map_reconciled_bass_chart(chart: "ReconciledBassChart", tuning: BassTuning, *, max_fret: int = 24) -> BassMapping:
    """Map reconciled symbolic Bass content while keeping audio-only detections as review evidence."""
    from .reconciliation import ReconciledBassChart

    if not isinstance(chart, ReconciledBassChart):
        raise TypeError("chart must be a ReconciledBassChart")

    source_notes = [note for note in chart.notes if note.status != "audio_only"]
    transcription = BassTranscription(
        engine="reconciliation",
        source_path="charts/bass_reconciled.json",
        sample_rate_hz=44100,
        notes=[
            NoteEvent(
                start=note.start_seconds,
                duration=note.duration_seconds,
                midi=note.midi,
                confidence=max(note.symbolic_import_confidence or 0.0, note.audio_confidence or 0.0, 0.5),
                pitch_confidence=note.audio_confidence or note.symbolic_import_confidence or 0.5,
                timing_confidence=note.alignment_confidence,
                review_required=note.review_required,
            )
            for note in source_notes
        ],
    )
    mapping = map_bass_transcription(transcription, tuning, max_fret=max_fret)
    for index, source_note in enumerate(source_notes):
        mapped = mapping.notes[index]
        mapped.techniques = list(source_note.techniques)
        mapped.trust_class = source_note.trust_class
        if source_note.string_index is None or source_note.fret is None:
            continue
        string_index = source_note.string_index
        fret = source_note.fret
        valid = (
            0 <= string_index < len(tuning.open_midi)
            and string_index <= 3
            and 0 <= fret <= max_fret
            and tuning.open_midi[string_index] + fret == source_note.midi
        )
        if valid:
            mapped.string = string_index
            mapped.fret = fret
            mapped.position_source = "symbolic"
            mapped.mapping_confidence = 1.0 if source_note.trust_class == SourceTrustClass.symbolic_verified else 0.85
            mapped.review_required = source_note.review_required
            mapped.alternate_positions = [p for p in candidate_positions(source_note.midi, tuning, max_fret=max_fret) if not (p.string == string_index and p.fret == fret)]
        else:
            mapped.review_required = True
    return mapping


def write_bass_mapping(mapping: BassMapping, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(mapping.model_dump_json(indent=2), encoding="utf-8")


def read_bass_mapping(path: Path) -> BassMapping:
    return BassMapping.model_validate_json(path.read_text(encoding="utf-8"))


def bass_mapping_is_current(path: Path) -> bool:
    """Whether a persisted Bass mapping and its reconciliation authority are current."""

    try:
        mapping = read_bass_mapping(path)
    except (OSError, ValueError):
        return False
    if "mapping_algorithm_version" not in mapping.model_fields_set:
        return False
    if mapping.mapping_algorithm_version != CURRENT_BASS_MAPPING_ALGORITHM_VERSION:
        return False

    # A mapping built from reconciled symbolic authority cannot outlive that authority.
    # Older projects may have a mapping that is current by mapping-version alone while
    # charts/bass_reconciled.json predates a reconciliation semantic change (#363).
    reconciled_path = path.parent / "bass_reconciled.json"
    if reconciled_path.is_file():
        from .reconciliation import reconciled_bass_chart_is_current

        if not reconciled_bass_chart_is_current(reconciled_path):
            return False
    return True
