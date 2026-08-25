from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .alignment import AlignmentRegion, AlignmentReport, map_source_time
from .source_import import ImportedSource
from .transcription import BassTranscription, NoteEvent, read_transcription


ALIGNMENT_REFINEMENT_PATH = Path("analysis") / "alignment_onset_refinement.json"
CURRENT_ALIGNMENT_REFINEMENT_VERSION = 2


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


def _timing_usable_audio_notes(audio: BassTranscription) -> list[NoteEvent]:
    """Return transcription events whose onset is useful even when pitch needs review.

    Product Reality #397 showed that requiring a fully trusted pitch classification can
    leave a long-intro song with too little evidence to repair an otherwise obvious global
    timing translation. Timing refinement may use a review-required event only when its
    onset confidence remains strong; reliable pitch contributes extra evidence separately.
    """

    return [
        note
        for note in audio.notes
        if note.confidence >= 0.55 and note.timing_confidence >= 0.70
    ]


def _match_evidence(
    source_notes,
    report: AlignmentReport,
    audio_notes: list[NoteEvent],
    *,
    shift_seconds: float,
    tolerance_seconds: float = 0.16,
) -> tuple[int, int, int]:
    """Score one global translation with one-to-one onset and pitch agreement."""

    unused = set(range(len(audio_notes)))
    onset_matches = 0
    pitch_matches = 0
    for symbolic in source_notes[:64]:
        projected = map_source_time(report, symbolic.start_seconds) + shift_seconds
        nearby = [
            index
            for index in unused
            if abs(audio_notes[index].start - projected) <= tolerance_seconds
        ]
        if not nearby:
            continue
        nearby.sort(
            key=lambda index: (
                0
                if audio_notes[index].midi == symbolic.midi
                and audio_notes[index].pitch_confidence >= 0.55
                else 1,
                abs(audio_notes[index].start - projected),
                audio_notes[index].start,
            )
        )
        chosen = nearby[0]
        unused.remove(chosen)
        onset_matches += 1
        if (
            audio_notes[chosen].midi == symbolic.midi
            and audio_notes[chosen].pitch_confidence >= 0.55
        ):
            pitch_matches += 1

    weighted = onset_matches + 2 * pitch_matches
    return weighted, onset_matches, pitch_matches


def _match_count(
    source_notes,
    report: AlignmentReport,
    audio_notes: list[NoteEvent],
    *,
    shift_seconds: float,
    tolerance_seconds: float = 0.16,
) -> int:
    """Compatibility helper: return the weighted timing/pitch evidence score."""

    return _match_evidence(
        source_notes,
        report,
        audio_notes,
        shift_seconds=shift_seconds,
        tolerance_seconds=tolerance_seconds,
    )[0]


def _candidate_shifts(source_notes, report: AlignmentReport, audio_notes: list[NoteEvent]) -> list[float]:
    candidates: set[float] = {0.0}
    early_source = list(source_notes[:24])
    early_audio = [note for note in audio_notes if note.start <= 60.0][:200]
    for symbolic in early_source:
        projected = map_source_time(report, symbolic.start_seconds)
        for audio_note in early_audio:
            shift = audio_note.start - projected
            if abs(shift) <= 30.0:
                candidates.add(round(shift, 6))
    return sorted(candidates)


def _shift_report(report: AlignmentReport, shift_seconds: float) -> AlignmentReport:
    """Translate the score clock while preserving EOF-style score pre-roll semantics.

    Editor on Fire's GP/GPA importer permits synchronization to place leading symbolic
    beats before audio time zero. It then omits those pre-zero beats and offsets subsequent
    source beat positions instead of rejecting the synchronization.  This Python port keeps
    the same semantic boundary: transformed anchors before zero are omitted, at least two
    in-recording anchors must remain, and earlier source positions are represented by
    linear extrapolation from the retained beat map.

    Reference implementation: Berneer/editor-on-fire, src/gp_import.c, BSD-style license.
    """

    shifted_all = [
        anchor.model_copy(update={"audio_time_seconds": anchor.audio_time_seconds + shift_seconds})
        for anchor in report.anchors
    ]
    anchors = [anchor for anchor in shifted_all if anchor.audio_time_seconds >= -1e-9]
    anchors = [
        anchor.model_copy(update={"audio_time_seconds": max(0.0, anchor.audio_time_seconds)})
        for anchor in anchors
    ]
    if len(anchors) < 2:
        raise ValueError(
            "content-aware alignment refinement leaves fewer than two in-recording anchors"
        )

    regions = [
        AlignmentRegion(
            source_start_seconds=first.source_time_seconds,
            source_end_seconds=second.source_time_seconds,
            audio_start_seconds=first.audio_time_seconds,
            audio_end_seconds=second.audio_time_seconds,
            rms_residual_seconds=report.rms_residual_seconds,
            max_abs_residual_seconds=report.max_abs_residual_seconds,
            confidence=min(first.confidence, second.confidence, report.confidence),
        )
        for first, second in zip(anchors, anchors[1:])
    ]

    return report.model_copy(
        update={
            "global_offset_seconds": report.global_offset_seconds + shift_seconds,
            "anchors": anchors,
            "regions": regions,
            "warnings": [
                *report.warnings,
                f"Content-aware Bass onset refinement applied a global shift of {shift_seconds:+.3f}s based on repeated timing/pitch onset agreement using EOF-compatible pre-roll handling.",
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
    """Refine a beat-grid alignment using repeated Bass onset evidence.

    Beat-interval matching is ambiguous for long constant-tempo intros: a structured score
    may already contain leading rests while an audio beat detector also begins its grid at
    the audible performance. This pass tests only a global translation, using repeated
    one-to-one onset agreement plus reliable pitch matches. A correction is applied only
    when it materially beats the current translation and the next-best hypothesis.

    When the valid correction places score-only leading beats before recording time zero,
    the persisted alignment follows Editor on Fire's proven import behavior by omitting
    only those pre-zero anchors rather than rejecting the correction.
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
    audio_notes = _timing_usable_audio_notes(audio)
    candidates = _candidate_shifts(source_notes, report, audio_notes)
    baseline_score, baseline_onsets, baseline_pitches = _match_evidence(
        source_notes,
        report,
        audio_notes,
        shift_seconds=0.0,
    )

    ranked: list[tuple[int, int, int, float]] = []
    for shift in candidates:
        score, onset_matches, pitch_matches = _match_evidence(
            source_notes,
            report,
            audio_notes,
            shift_seconds=shift,
        )
        ranked.append((score, pitch_matches, onset_matches, shift))
    ranked.sort(key=lambda item: (-item[0], -item[1], -item[2], abs(item[3]), item[3]))

    best_score, best_pitches, best_onsets, best_shift = ranked[0]
    second_score = ranked[1][0] if len(ranked) > 1 else 0
    improvement = best_score - baseline_score
    winner_margin = best_score - second_score
    minimum_onset_support = min(8, max(4, len(source_notes[:64]) // 8)) if source_notes else 8
    has_pitch_support = best_pitches >= 2
    has_strong_rhythmic_support = best_onsets >= 12 and improvement >= 8 and winner_margin >= 3
    applied = (
        abs(best_shift) >= 0.20
        and best_onsets >= minimum_onset_support
        and improvement >= 4
        and winner_margin >= 1
        and (has_pitch_support or has_strong_rhythmic_support)
    )

    if applied:
        refined = _shift_report(report, best_shift)
        refined.write_json(alignment_path)
        reason = (
            f"Applied {best_shift:+.3f}s: weighted timing/pitch evidence improved from "
            f"{baseline_score} ({baseline_onsets} onsets/{baseline_pitches} pitch) to "
            f"{best_score} ({best_onsets} onsets/{best_pitches} pitch), margin {winner_margin}."
        )
    else:
        best_shift = 0.0
        reason = (
            "No global onset correction had enough clearly distinguished support; "
            f"baseline {baseline_score} ({baseline_onsets} onsets/{baseline_pitches} pitch), "
            f"best {best_score} ({best_onsets} onsets/{best_pitches} pitch), margin {winner_margin}."
        )

    record = AlignmentOnsetRefinement(
        source_sha256=report.source_sha256,
        track_index=report.track_index,
        applied=applied,
        shift_seconds=best_shift,
        baseline_match_count=baseline_score,
        refined_match_count=best_score,
        candidate_count=len(candidates),
        reason=reason,
    )
    record.write_json(project / ALIGNMENT_REFINEMENT_PATH)

    # Any execution under refinement-v2 invalidates authorities and derivatives built
    # from the previous transform. They must be regenerated/re-promoted through the
    # existing workflow gates; an old 17.9 s preview must never remain silently current.
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

    return record
