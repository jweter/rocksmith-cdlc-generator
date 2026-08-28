from __future__ import annotations

from bisect import bisect_left, bisect_right
from math import ceil
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .alignment import AlignmentRegion, AlignmentReport, map_source_time
from .source_import import ImportedSource
from .transcription import NoteEvent, read_transcription


EOF_FIRST_SYNC_PATH = Path("analysis") / "eof_first_sync_alignment.json"
CURRENT_EOF_FIRST_SYNC_VERSION = 1
EOF_UPSTREAM_REPOSITORY = "raynebc/editor-on-fire"
EOF_UPSTREAM_COMMIT = "c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100"
EOF_UPSTREAM_PATH = "src/gp_import.c"

_PREFIX_ONSET_LIMIT = 12
_MATCH_TOLERANCE_SECONDS = 0.20
_MAX_SYNC_SEARCH_SECONDS = 30.0
_MIN_MATERIAL_SHIFT_SECONDS = 0.20
_AUDIO_DEDUP_SECONDS = 0.025


class EOFFirstSyncAlignment(BaseModel):
    """Evidence for the EOF-derived first-sync-point timing pass.

    EOF's Guitar Pro importer computes realtime note positions from the project beat map.
    When the first synchronization point occurs after measure 1, EOF walks the preceding
    beats backward using the beat duration in effect and omits only beats that would fall
    before recording time zero.  This record captures the equivalent project-level decision:
    identify the earliest recording onset sequence that represents the beginning of the
    selected symbolic track, use that first playable event as the synchronization point,
    then translate the existing shared beat transform without adding a second intro offset.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    algorithm_version: int = CURRENT_EOF_FIRST_SYNC_VERSION
    upstream_repository: str = EOF_UPSTREAM_REPOSITORY
    upstream_commit: str = EOF_UPSTREAM_COMMIT
    upstream_path: str = EOF_UPSTREAM_PATH
    source_sha256: str
    track_index: int = Field(ge=0)
    source_first_playable_seconds: float = Field(ge=0)
    baseline_first_playable_seconds: float
    matched_first_playable_seconds: float | None = Field(default=None, ge=0)
    shift_seconds: float
    prefix_onset_count: int = Field(ge=0)
    matched_onset_count: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    applied: bool
    reason: str

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path


def _timing_usable_audio_notes(notes: list[NoteEvent]) -> list[NoteEvent]:
    return sorted(
        (
            note
            for note in notes
            if note.confidence >= 0.55 and note.timing_confidence >= 0.70
        ),
        key=lambda item: item.start,
    )


def _deduplicated_onsets(values: list[float], *, tolerance: float) -> list[float]:
    ordered = sorted(values)
    result: list[float] = []
    for value in ordered:
        if not result or value - result[-1] > tolerance:
            result.append(value)
    return result


def _source_prefix_onsets(source: ImportedSource, track_index: int) -> list[float]:
    track = next((item for item in source.tracks if item.source_track_index == track_index), None)
    if track is None:
        raise ValueError(f"alignment track index {track_index} not found in source")
    if not track.notes:
        raise ValueError("alignment track has no symbolic notes")
    return _deduplicated_onsets(
        [note.start_seconds for note in track.notes],
        tolerance=1e-6,
    )[:_PREFIX_ONSET_LIMIT]


def _match_count(
    audio_onsets: list[float],
    *,
    candidate_start: float,
    relative_targets: list[float],
) -> int:
    """Count one-to-one onset matches for a proposed first synchronization point."""

    unused: set[int] = set(range(len(audio_onsets)))
    matches = 0
    for relative in relative_targets:
        target = candidate_start + relative
        left = bisect_left(audio_onsets, target - _MATCH_TOLERANCE_SECONDS)
        right = bisect_right(audio_onsets, target + _MATCH_TOLERANCE_SECONDS)
        candidates = [index for index in range(left, right) if index in unused]
        if not candidates:
            continue
        chosen = min(candidates, key=lambda index: abs(audio_onsets[index] - target))
        unused.remove(chosen)
        matches += 1
    return matches


def _find_first_sync_point(
    report: AlignmentReport,
    source_onsets: list[float],
    audio_onsets: list[float],
) -> tuple[float | None, int, int]:
    """Find the earliest strongly supported recording occurrence of the score prefix.

    This deliberately does not rank arbitrary global shift buckets or require the first
    pitch estimate to be correct.  The complete score's first playable onset is treated as
    EOF's first synchronization point.  Repeated riffs are disambiguated by choosing the
    earliest occurrence whose following onset sequence has essentially the same support as
    the strongest occurrence.
    """

    if len(source_onsets) < 4 or len(audio_onsets) < 4:
        return None, 0, 0

    projected = [map_source_time(report, onset) for onset in source_onsets]
    baseline_first = projected[0]
    relative_targets = [value - baseline_first for value in projected]
    search_start = max(0.0, baseline_first - _MAX_SYNC_SEARCH_SECONDS)
    search_end = baseline_first + _MAX_SYNC_SEARCH_SECONDS
    candidate_starts = [
        onset for onset in audio_onsets if search_start <= onset <= search_end
    ]
    if not candidate_starts:
        return None, 0, 0

    scored = [
        (
            _match_count(
                audio_onsets,
                candidate_start=candidate,
                relative_targets=relative_targets,
            ),
            candidate,
        )
        for candidate in candidate_starts
    ]
    best_match_count = max(item[0] for item in scored)
    required = min(6, max(4, ceil(len(relative_targets) * 0.60)))
    if best_match_count < required:
        return None, best_match_count, len(candidate_starts)

    # A one-onset difference can come from a missed/extra transcription onset.  Among
    # candidates effectively tied with the strongest sequence, the first occurrence is the
    # correct one for a complete score beginning at song measure 1.  This is the specific
    # periodic-riff failure that kept binding the representative project two measures late.
    near_best = [
        item for item in scored if item[0] >= required and item[0] >= best_match_count - 1
    ]
    near_best.sort(key=lambda item: (item[1], -item[0]))
    chosen_matches, chosen_start = near_best[0]
    return chosen_start, chosen_matches, len(candidate_starts)


def _shift_regions_eof(report: AlignmentReport, shift_seconds: float) -> list[AlignmentRegion]:
    regions: list[AlignmentRegion] = []
    for region in report.regions:
        shifted_start = region.audio_start_seconds + shift_seconds
        shifted_end = region.audio_end_seconds + shift_seconds
        if shifted_end <= 0.0:
            continue

        source_start = region.source_start_seconds
        audio_start = shifted_start
        if shifted_start < 0.0:
            audio_span = shifted_end - shifted_start
            if audio_span <= 0.0:
                continue
            fraction_to_zero = -shifted_start / audio_span
            source_start = region.source_start_seconds + fraction_to_zero * (
                region.source_end_seconds - region.source_start_seconds
            )
            audio_start = 0.0

        if region.source_end_seconds <= source_start or shifted_end <= audio_start:
            continue
        regions.append(
            AlignmentRegion(
                source_start_seconds=source_start,
                source_end_seconds=region.source_end_seconds,
                audio_start_seconds=max(0.0, audio_start),
                audio_end_seconds=shifted_end,
                rms_residual_seconds=region.rms_residual_seconds,
                max_abs_residual_seconds=region.max_abs_residual_seconds,
                confidence=region.confidence,
            )
        )
    if not regions:
        raise ValueError("EOF first-sync alignment leaves no in-recording regions")
    return regions


def _apply_eof_sync_translation(
    report: AlignmentReport,
    shift_seconds: float,
) -> AlignmentReport:
    """Translate the project beat map with EOF's pre-zero-beat semantics.

    Direct behavior reference: raynebc/editor-on-fire ``src/gp_import.c`` at
    c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100.  EOF positions beats preceding the first
    sync point by walking backward with the beat duration in effect; beats remaining before
    0 ms are omitted, while later note timing continues from the retained project beat map.

    Our alignment report already represents that beat map piecewise.  Translating every
    anchor by the first-sync-point delta and clipping only the pre-zero portion is therefore
    the native equivalent; no song-specific offset is introduced.
    """

    shifted = [
        anchor.model_copy(update={"audio_time_seconds": anchor.audio_time_seconds + shift_seconds})
        for anchor in report.anchors
    ]
    anchors = [anchor for anchor in shifted if anchor.audio_time_seconds >= -1e-9]
    anchors = [
        anchor.model_copy(update={"audio_time_seconds": max(0.0, anchor.audio_time_seconds)})
        for anchor in anchors
    ]
    if len(anchors) < 2:
        raise ValueError("EOF first-sync alignment leaves fewer than two in-recording anchors")

    return report.model_copy(
        update={
            "global_offset_seconds": report.global_offset_seconds + shift_seconds,
            "anchors": anchors,
            "regions": _shift_regions_eof(report, shift_seconds),
            "warnings": [
                *report.warnings,
                (
                    "EOF-derived first-sync timing aligned the beginning of the symbolic "
                    f"track to the earliest supported recording occurrence ({shift_seconds:+.3f}s); "
                    "leading beats before recording zero are omitted using EOF gp_import.c semantics."
                ),
            ],
        }
    )


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


def eof_first_sync_alignment_is_current(project_dir: Path, report: AlignmentReport) -> bool:
    path = project_dir.expanduser().resolve() / EOF_FIRST_SYNC_PATH
    if not path.is_file():
        return False
    try:
        record = EOFFirstSyncAlignment.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return (
        record.algorithm_version == CURRENT_EOF_FIRST_SYNC_VERSION
        and record.source_sha256 == report.source_sha256
        and record.track_index == report.track_index
    )


def refine_project_alignment_from_eof_first_sync(
    project_dir: Path,
    source_path: Path,
) -> EOFFirstSyncAlignment:
    """Use an EOF-style first synchronization point instead of global shift ranking.

    The first playable event of the selected symbolic track is matched to the earliest
    strongly supported occurrence of its short onset sequence in the recording.  That pair
    becomes the synchronization point.  The whole project beat transform is then translated
    once, preserving EOF's treatment of leading beats before recording zero.
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
    source_onsets = _source_prefix_onsets(source, report.track_index)
    audio = read_transcription(transcription_path)
    audio_notes = _timing_usable_audio_notes(audio.notes)
    audio_onsets = _deduplicated_onsets(
        [note.start for note in audio_notes],
        tolerance=_AUDIO_DEDUP_SECONDS,
    )

    source_first = source_onsets[0]
    baseline_first = map_source_time(report, source_first)
    matched_first, matched_count, candidate_count = _find_first_sync_point(
        report,
        source_onsets,
        audio_onsets,
    )

    if matched_first is None:
        record = EOFFirstSyncAlignment(
            source_sha256=report.source_sha256,
            track_index=report.track_index,
            source_first_playable_seconds=source_first,
            baseline_first_playable_seconds=baseline_first,
            matched_first_playable_seconds=None,
            shift_seconds=0.0,
            prefix_onset_count=len(source_onsets),
            matched_onset_count=matched_count,
            candidate_count=candidate_count,
            applied=False,
            reason=(
                "No recording onset sequence had enough support to establish an EOF-style "
                "first synchronization point; timing remains review-required rather than "
                "falling back to periodic global-shift heuristics."
            ),
        )
        record.write_json(project / EOF_FIRST_SYNC_PATH)
        _invalidate_downstream(project)
        return record

    shift = matched_first - baseline_first
    if abs(shift) < _MIN_MATERIAL_SHIFT_SECONDS:
        record = EOFFirstSyncAlignment(
            source_sha256=report.source_sha256,
            track_index=report.track_index,
            source_first_playable_seconds=source_first,
            baseline_first_playable_seconds=baseline_first,
            matched_first_playable_seconds=matched_first,
            shift_seconds=0.0,
            prefix_onset_count=len(source_onsets),
            matched_onset_count=matched_count,
            candidate_count=candidate_count,
            applied=False,
            reason=(
                "EOF-style first synchronization point agrees with the existing transform "
                f"within {_MIN_MATERIAL_SHIFT_SECONDS:.2f}s; no translation was applied."
            ),
        )
        record.write_json(project / EOF_FIRST_SYNC_PATH)
        _invalidate_downstream(project)
        return record

    refined = _apply_eof_sync_translation(report, shift)
    refined.write_json(alignment_path)
    _invalidate_downstream(project)
    record = EOFFirstSyncAlignment(
        source_sha256=report.source_sha256,
        track_index=report.track_index,
        source_first_playable_seconds=source_first,
        baseline_first_playable_seconds=baseline_first,
        matched_first_playable_seconds=matched_first,
        shift_seconds=shift,
        prefix_onset_count=len(source_onsets),
        matched_onset_count=matched_count,
        candidate_count=candidate_count,
        applied=True,
        reason=(
            f"Applied {shift:+.3f}s from EOF-style first sync: source first playable "
            f"{source_first:.3f}s was previously projected to {baseline_first:.3f}s and the "
            f"earliest supported recording occurrence is {matched_first:.3f}s "
            f"({matched_count}/{len(source_onsets)} prefix onsets matched)."
        ),
    )
    record.write_json(project / EOF_FIRST_SYNC_PATH)
    return record
