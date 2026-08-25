from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .alignment import AlignmentReport, map_source_time
from .source_import import ImportedSource
from .transcription import BassTranscription, NoteEvent, read_transcription


ALIGNMENT_REFINEMENT_PATH = Path("analysis") / "alignment_onset_refinement.json"
CURRENT_ALIGNMENT_REFINEMENT_VERSION = 1


class AlignmentOnsetRefinement(BaseModel):
    """Evidence record for one content-aware refinement of symbolic-to-audio alignment."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    algorithm_version: int = CURRENT_ALIGNMENT_REFINEMENT_VERSION
    source_sha256: str
    track_index: int = Field(ge=0)
    applied: bool
    shift_seconds: float
    baseline_match_count: int = Field(ge=0)
    refined_match_count: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    reason: str

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path


def _reliable_audio_notes(audio: BassTranscription) -> list[NoteEvent]:
    return [
        note
        for note in audio.notes
        if not note.review_required
        and note.confidence >= 0.80
        and note.pitch_confidence >= 0.70
        and note.timing_confidence >= 0.70
    ]


def _match_count(
    source_notes,
    report: AlignmentReport,
    audio_notes: list[NoteEvent],
    *,
    shift_seconds: float,
    tolerance_seconds: float = 0.14,
) -> int:
    by_midi: dict[int, list[float]] = {}
    for note in audio_notes:
        by_midi.setdefault(note.midi, []).append(note.start)

    matches = 0
    for symbolic in source_notes[:64]:
        projected = map_source_time(report, symbolic.start_seconds) + shift_seconds
        candidates = by_midi.get(symbolic.midi, [])
        if any(abs(audio_time - projected) <= tolerance_seconds for audio_time in candidates):
            matches += 1
    return matches


def _candidate_shifts(source_notes, report: AlignmentReport, audio_notes: list[NoteEvent]) -> list[float]:
    candidates: set[float] = {0.0}
    early_source = list(source_notes[:16])
    early_audio = [note for note in audio_notes if note.start <= 60.0][:160]
    for symbolic in early_source:
        projected = map_source_time(report, symbolic.start_seconds)
        for audio_note in early_audio:
            if audio_note.midi != symbolic.midi:
                continue
            shift = audio_note.start - projected
            if abs(shift) <= 30.0:
                candidates.add(round(shift, 6))
    return sorted(candidates)


def _shift_report(report: AlignmentReport, shift_seconds: float) -> AlignmentReport:
    anchors = [
        anchor.model_copy(update={"audio_time_seconds": anchor.audio_time_seconds + shift_seconds})
        for anchor in report.anchors
    ]
    if any(anchor.audio_time_seconds < 0 for anchor in anchors):
        raise ValueError("content-aware alignment refinement would move an anchor before recording time zero")
    regions = [
        region.model_copy(
            update={
                "audio_start_seconds": region.audio_start_seconds + shift_seconds,
                "audio_end_seconds": region.audio_end_seconds + shift_seconds,
            }
        )
        for region in report.regions
    ]
    return report.model_copy(
        update={
            "global_offset_seconds": report.global_offset_seconds + shift_seconds,
            "anchors": anchors,
            "regions": regions,
            "warnings": [
                *report.warnings,
                f"Content-aware Bass onset refinement applied a global shift of {shift_seconds:+.3f}s based on repeated pitch/onset agreement.",
            ],
        }
    )


def refinement_is_current(project_dir: Path, report: AlignmentReport) -> bool:
    path = project_dir.expanduser().resolve() / ALIGNMENT_REFINEMENT_PATH
    if not path.is_file():
        return False
    try:
        record = AlignmentOnsetRefinement.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return (
        record.algorithm_version == CURRENT_ALIGNMENT_REFINEMENT_VERSION
        and record.source_sha256 == report.source_sha256
        and record.track_index == report.track_index
    )


def refine_project_alignment_from_bass_onsets(project_dir: Path, source_path: Path) -> AlignmentOnsetRefinement:
    """Refine a beat-grid alignment using repeated high-confidence Bass onset evidence.

    Beat-interval matching is ambiguous for long constant-tempo intros: a structured score
    may contain extra count-in/intro measures while the recording does not. This pass keeps
    the reviewed beat-grid shape intact and tests only a global translation. Candidate
    shifts are proposed by equal-pitch symbolic/audio pairs, then scored across up to 64
    symbolic notes. A shift is applied only when it has enough repeated support and clearly
    improves over the unshifted alignment; otherwise the original alignment is preserved.
    """

    project = project_dir.expanduser().resolve()
    alignment_path = project / "analysis" / "alignment.json"
    transcription_path = project / "analysis" / "bass_raw.json"
    if not alignment_path.is_file():
        raise FileNotFoundError(alignment_path)
    if not transcription_path.is_file():
        raise FileNotFoundError(transcription_path)

    source = ImportedSource.read_json(source_path.expanduser().resolve())
    report = AlignmentReport.model_validate_json(alignment_path.read_text(encoding="utf-8"))
    audio = read_transcription(transcription_path)
    track = next((item for item in source.tracks if item.source_track_index == report.track_index), None)
    if track is None:
        raise ValueError(f"alignment track index {report.track_index} not found in source")

    source_notes = list(track.notes)
    audio_notes = _reliable_audio_notes(audio)
    candidates = _candidate_shifts(source_notes, report, audio_notes)
    baseline = _match_count(source_notes, report, audio_notes, shift_seconds=0.0)

    best_shift = 0.0
    best_count = baseline
    for shift in candidates:
        count = _match_count(source_notes, report, audio_notes, shift_seconds=shift)
        if count > best_count or (count == best_count and abs(shift) < abs(best_shift)):
            best_shift = shift
            best_count = count

    minimum_support = min(4, max(2, len(source_notes[:64]) // 8)) if source_notes else 4
    improvement = best_count - baseline
    applied = (
        abs(best_shift) >= 0.20
        and best_count >= minimum_support
        and improvement >= 3
    )

    if applied:
        refined = _shift_report(report, best_shift)
        refined.write_json(alignment_path)
        reason = (
            f"Applied {best_shift:+.3f}s: repeated pitch/onset matches improved from "
            f"{baseline} to {best_count}."
        )
    else:
        best_shift = 0.0
        reason = (
            "No global onset correction had enough repeated high-confidence support; "
            f"baseline matches {baseline}, best supported matches {best_count}."
        )

    record = AlignmentOnsetRefinement(
        source_sha256=report.source_sha256,
        track_index=report.track_index,
        applied=applied,
        shift_seconds=best_shift,
        baseline_match_count=baseline,
        refined_match_count=best_count,
        candidate_count=len(candidates),
        reason=reason,
    )
    record.write_json(project / ALIGNMENT_REFINEMENT_PATH)

    # Any alignment execution under the new semantics must invalidate authorities and
    # derivatives that were built from the previous transform. They will be rebuilt or
    # re-promoted through the existing workflow gates; no old chart may remain current.
    for relative in (
        "analysis/shared_timeline.json",
        "analysis/reviewed_score_timing.json",
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

    return record
