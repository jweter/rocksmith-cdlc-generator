from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .alignment import AlignmentReport, map_source_time
from .alignment_onset_refinement import (
    _audio_index,
    _nearby_indexed_audio,
    _shift_report,
    _timing_usable_audio_notes,
)
from .source_import import ImportedSource
from .transcription import NoteEvent, read_transcription


LEADING_REST_REFINEMENT_PATH = Path("analysis") / "alignment_leading_rest_refinement.json"
CURRENT_LEADING_REST_REFINEMENT_VERSION = 1
_MIN_LEADING_REST_SECONDS = 1.0
_MIN_SHIFT_SECONDS = 0.20
_SHIFT_BUCKET_SECONDS = 0.05
_PREFIX_LIMIT = 12
_ONSET_TOLERANCE_SECONDS = 0.20


class LeadingRestAlignmentRefinement(BaseModel):
    """Evidence for preserving score-leading rests when the audio beat grid starts late."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    algorithm_version: int = CURRENT_LEADING_REST_REFINEMENT_VERSION
    source_sha256: str
    track_index: int = Field(ge=0)
    leading_rest_seconds: float = Field(ge=0)
    applied: bool
    shift_seconds: float
    baseline_onset_matches: int = Field(ge=0)
    refined_onset_matches: int = Field(ge=0)
    baseline_pitch_matches: int = Field(ge=0)
    refined_pitch_matches: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    reason: str

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path


def _prefix_support(
    source_notes,
    report: AlignmentReport,
    audio_notes: list[NoteEvent],
    *,
    shift_seconds: float,
) -> tuple[int, int]:
    """Count one-to-one timing matches near the score edge, using pitch only as support."""

    prefix = list(source_notes[:_PREFIX_LIMIT])
    if not prefix or not audio_notes:
        return 0, 0

    starts, ordered = _audio_index(audio_notes)
    unused = set(range(len(audio_notes)))
    onset_matches = 0
    pitch_matches = 0
    for symbolic in prefix:
        projected = map_source_time(report, symbolic.start_seconds) + shift_seconds
        candidates = [
            (index, note)
            for index, note in _nearby_indexed_audio(
                starts,
                ordered,
                projected,
                _ONSET_TOLERANCE_SECONDS,
            )
            if index in unused
        ]
        if not candidates:
            continue
        index, chosen = min(candidates, key=lambda item: abs(item[1].start - projected))
        unused.remove(index)
        onset_matches += 1
        if chosen.midi == symbolic.midi and chosen.pitch_confidence >= 0.55:
            pitch_matches += 1
    return onset_matches, pitch_matches


def _candidate_shifts(
    source_notes,
    report: AlignmentReport,
    audio_notes: list[NoteEvent],
    *,
    leading_rest_seconds: float,
) -> list[float]:
    """Pair the first playable score event with credible earlier audio onsets.

    If the score begins with rests, a beat detector may start its grid at the first strong
    instrument entrance and accidentally consume those written rests.  The expected repair
    is therefore close to the negative leading-rest span.  Candidate generation is timing-
    only so a weak first Bass pitch estimate cannot hide the real score edge.
    """

    if not source_notes or not audio_notes:
        return []
    projected_first = map_source_time(report, source_notes[0].start_seconds)
    rest_tolerance = max(1.25, leading_rest_seconds * 0.40)
    max_adjustment = min(30.0, leading_rest_seconds + rest_tolerance)

    candidates: list[float] = []
    for note in sorted(audio_notes, key=lambda item: item.start):
        shift = note.start - projected_first
        if shift > -_MIN_SHIFT_SECONDS:
            continue
        if abs(shift) > max_adjustment:
            continue
        if abs(abs(shift) - leading_rest_seconds) > rest_tolerance:
            continue
        bucket = round(shift / _SHIFT_BUCKET_SECONDS) * _SHIFT_BUCKET_SECONDS
        candidates.append(bucket)
    return list(dict.fromkeys(candidates))


def _invalidate_downstream(project: Path) -> None:
    for relative in (
        "analysis/shared_timeline.json",
        "analysis/reviewed_score_timing.json",
        "analysis/source_timing_qualification.json",
        "charts/bass_reconciled.json",
        "charts/lead_source.json",
        "charts/rhythm_source.json",
        "charts/lead_shared_timeline.json",
        "charts/rhythm_shared_timeline.json",
        "review/validation_report.json",
        "review/lead_validation_report.json",
        "review/rhythm_validation_report.json",
    ):
        (project / relative).unlink(missing_ok=True)


def refine_project_alignment_from_leading_rest(
    project_dir: Path,
    source_path: Path,
) -> LeadingRestAlignmentRefinement:
    """Preserve a structured score's leading rests using onset-sequence evidence.

    This is deliberately narrower than general onset refinement.  It runs only when the
    selected symbolic track has a material rest before its first playable event, and it can
    only move the score earlier.  Several following timing onsets must support the same
    translation.  Pitch strengthens evidence but is not required for the first onset.
    """

    project = project_dir.expanduser().resolve()
    alignment_path = project / "analysis" / "alignment.json"
    transcription_path = project / "analysis" / "bass_raw.json"
    source = ImportedSource.read_json(source_path.expanduser().resolve())
    report = AlignmentReport.model_validate_json(alignment_path.read_text(encoding="utf-8"))
    audio = read_transcription(transcription_path)

    track = next((item for item in source.tracks if item.source_track_index == report.track_index), None)
    if track is None:
        raise ValueError(f"alignment track index {report.track_index} not found in source")
    source_notes = list(track.notes)
    if not source_notes:
        raise ValueError("alignment track has no symbolic notes")

    leading_rest_seconds = float(source_notes[0].start_seconds)
    audio_notes = _timing_usable_audio_notes(audio)
    baseline_onsets, baseline_pitches = _prefix_support(
        source_notes,
        report,
        audio_notes,
        shift_seconds=0.0,
    )

    if leading_rest_seconds < _MIN_LEADING_REST_SECONDS or not audio_notes:
        record = LeadingRestAlignmentRefinement(
            source_sha256=report.source_sha256,
            track_index=report.track_index,
            leading_rest_seconds=leading_rest_seconds,
            applied=False,
            shift_seconds=0.0,
            baseline_onset_matches=baseline_onsets,
            refined_onset_matches=baseline_onsets,
            baseline_pitch_matches=baseline_pitches,
            refined_pitch_matches=baseline_pitches,
            candidate_count=0,
            reason="No material symbolic leading-rest span or usable audio-onset evidence was present.",
        )
        record.write_json(project / LEADING_REST_REFINEMENT_PATH)
        return record

    candidates = _candidate_shifts(
        source_notes,
        report,
        audio_notes,
        leading_rest_seconds=leading_rest_seconds,
    )
    minimum_support = min(6, max(4, len(source_notes[:_PREFIX_LIMIT]) // 2))
    scored: list[tuple[int, int, int, float, float]] = []
    for shift in candidates:
        onsets, pitches = _prefix_support(
            source_notes,
            report,
            audio_notes,
            shift_seconds=shift,
        )
        score = onsets + 2 * pitches
        expected_error = abs(abs(shift) - leading_rest_seconds)
        scored.append((score, onsets, pitches, expected_error, shift))

    eligible = [
        item
        for item in scored
        if item[1] >= minimum_support
        and (item[2] >= 1 or item[1] >= 6)
        and item[1] >= max(minimum_support, baseline_onsets - 1)
        and item[0] >= (baseline_onsets + 2 * baseline_pitches) - 2
    ]
    eligible.sort(key=lambda item: (-item[0], -item[1], -item[2], item[3], item[4]))

    if not eligible:
        record = LeadingRestAlignmentRefinement(
            source_sha256=report.source_sha256,
            track_index=report.track_index,
            leading_rest_seconds=leading_rest_seconds,
            applied=False,
            shift_seconds=0.0,
            baseline_onset_matches=baseline_onsets,
            refined_onset_matches=baseline_onsets,
            baseline_pitch_matches=baseline_pitches,
            refined_pitch_matches=baseline_pitches,
            candidate_count=len(candidates),
            reason=(
                "No earlier onset-sequence candidate preserved the symbolic leading rest with "
                "enough repeated timing support."
            ),
        )
        record.write_json(project / LEADING_REST_REFINEMENT_PATH)
        return record

    _score, refined_onsets, refined_pitches, _expected_error, shift = eligible[0]
    refined = _shift_report(report, shift)
    refined = refined.model_copy(
        update={
            "warnings": [
                *refined.warnings,
                (
                    "Leading-rest refinement preserved the score prefix by moving the shared "
                    f"symbolic clock {shift:+.3f}s using onset-sequence evidence."
                ),
            ]
        }
    )
    refined.write_json(alignment_path)
    _invalidate_downstream(project)

    record = LeadingRestAlignmentRefinement(
        source_sha256=report.source_sha256,
        track_index=report.track_index,
        leading_rest_seconds=leading_rest_seconds,
        applied=True,
        shift_seconds=shift,
        baseline_onset_matches=baseline_onsets,
        refined_onset_matches=refined_onsets,
        baseline_pitch_matches=baseline_pitches,
        refined_pitch_matches=refined_pitches,
        candidate_count=len(candidates),
        reason=(
            f"Applied {shift:+.3f}s to preserve a {leading_rest_seconds:.3f}s symbolic "
            f"leading-rest span; prefix timing support {baseline_onsets}->{refined_onsets} "
            f"and pitch support {baseline_pitches}->{refined_pitches}."
        ),
    )
    record.write_json(project / LEADING_REST_REFINEMENT_PATH)
    return record
