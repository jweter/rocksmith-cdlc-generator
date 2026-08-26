from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .alignment import AlignmentRegion, AlignmentReport, map_source_time
from .source_import import ImportedSource
from .transcription import BassTranscription, NoteEvent, read_transcription


ALIGNMENT_REFINEMENT_PATH = Path("analysis") / "alignment_onset_refinement.json"
CURRENT_ALIGNMENT_REFINEMENT_VERSION = 3
_SHIFT_BUCKET_SECONDS = 0.05
_DISTINCT_SHIFT_SECONDS = 0.32
_MAX_SHIFT_SECONDS = 30.0
_MAX_SHIFT_HYPOTHESES = 64
_EDGE_TOLERANCE_SECONDS = 0.18
_EDGE_MATCH_LIMIT = 8
_EDGE_RANK_BONUS = 6


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
    """Return transcription events whose onset is useful even when pitch needs review."""

    return [
        note
        for note in audio.notes
        if note.confidence >= 0.55 and note.timing_confidence >= 0.70
    ]


def _audio_index(
    audio_notes: list[NoteEvent],
) -> tuple[list[float], list[tuple[int, NoteEvent]]]:
    ordered = sorted(enumerate(audio_notes), key=lambda item: item[1].start)
    return [item[1].start for item in ordered], ordered


def _nearby_indexed_audio(
    starts: list[float],
    ordered: list[tuple[int, NoteEvent]],
    center: float,
    radius: float,
) -> list[tuple[int, NoteEvent]]:
    left = bisect_left(starts, center - radius)
    right = bisect_right(starts, center + radius)
    return ordered[left:right]


def _match_evidence(
    source_notes,
    report: AlignmentReport,
    audio_notes: list[NoteEvent],
    *,
    shift_seconds: float,
    tolerance_seconds: float = 0.16,
    index: tuple[list[float], list[tuple[int, NoteEvent]]] | None = None,
) -> tuple[int, int, int]:
    """Score one global translation with indexed one-to-one onset/pitch agreement."""

    starts, ordered = _audio_index(audio_notes) if index is None else index
    unused = set(range(len(audio_notes)))
    onset_matches = 0
    pitch_matches = 0
    for symbolic in source_notes[:64]:
        projected = map_source_time(report, symbolic.start_seconds) + shift_seconds
        nearby = [
            (audio_index, note)
            for audio_index, note in _nearby_indexed_audio(
                starts,
                ordered,
                projected,
                tolerance_seconds,
            )
            if audio_index in unused
        ]
        if not nearby:
            continue
        nearby.sort(
            key=lambda item: (
                0
                if item[1].midi == symbolic.midi and item[1].pitch_confidence >= 0.55
                else 1,
                abs(item[1].start - projected),
                item[1].start,
            )
        )
        chosen_index, chosen = nearby[0]
        unused.remove(chosen_index)
        onset_matches += 1
        if chosen.midi == symbolic.midi and chosen.pitch_confidence >= 0.55:
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


def _edge_shift_candidate(
    source_notes,
    report: AlignmentReport,
    audio_notes: list[NoteEvent],
) -> float | None:
    """Propose the translation that aligns the first symbolic note to its earliest credible audio peer.

    Repeating riffs can make several measure-spaced translations score almost identically.
    The first reliable equal-pitch onset is a useful ordering constraint: a complete score's
    first written event should not silently bind to a later repetition while equally strong
    matching content already exists earlier in the recording.
    """

    if not source_notes or not audio_notes:
        return None
    first = source_notes[0]
    projected = map_source_time(report, first.start_seconds)
    same_pitch = [
        note
        for note in audio_notes
        if note.midi == first.midi
        and note.pitch_confidence >= 0.55
        and abs(note.start - projected) <= _MAX_SHIFT_SECONDS
    ]
    if not same_pitch:
        return None
    earliest = min(same_pitch, key=lambda note: note.start)
    shift = earliest.start - projected
    return round(shift / _SHIFT_BUCKET_SECONDS) * _SHIFT_BUCKET_SECONDS


def _edge_match_evidence(
    source_notes,
    report: AlignmentReport,
    audio_notes: list[NoteEvent],
    *,
    shift_seconds: float,
    tolerance_seconds: float = _EDGE_TOLERANCE_SECONDS,
) -> tuple[bool, int, float]:
    """Measure whether one translation aligns the beginning of the score to the recording edge.

    The edge is accepted only when the first symbolic pitch lands on the earliest reliable
    equal-pitch audio onset *and* the following short symbolic sequence receives repeated
    equal-pitch onset support. This prevents one early transcription blip from moving a
    complete arrangement while still disambiguating periodic intros.
    """

    if not source_notes or not audio_notes:
        return False, 0, float("inf")

    first = source_notes[0]
    same_pitch = [
        note
        for note in audio_notes
        if note.midi == first.midi and note.pitch_confidence >= 0.55
    ]
    if not same_pitch:
        return False, 0, float("inf")
    earliest = min(same_pitch, key=lambda note: note.start)
    first_projected = map_source_time(report, first.start_seconds) + shift_seconds
    first_error = abs(first_projected - earliest.start)

    unused = set(range(len(audio_notes)))
    matches = 0
    for symbolic in source_notes[:_EDGE_MATCH_LIMIT]:
        projected = map_source_time(report, symbolic.start_seconds) + shift_seconds
        candidates = [
            (index, note)
            for index, note in enumerate(audio_notes)
            if index in unused
            and note.midi == symbolic.midi
            and note.pitch_confidence >= 0.55
            and abs(note.start - projected) <= tolerance_seconds
        ]
        if not candidates:
            continue
        index, _note = min(candidates, key=lambda item: abs(item[1].start - projected))
        unused.remove(index)
        matches += 1

    return first_error <= tolerance_seconds, matches, first_error


def _candidate_shifts(
    source_notes,
    report: AlignmentReport,
    audio_notes: list[NoteEvent],
    *,
    index: tuple[list[float], list[tuple[int, NoteEvent]]] | None = None,
) -> list[float]:
    """Return a bounded, clustered set of globally plausible translation hypotheses.

    Full-song audio is never scanned for every source/candidate pair. For each of the
    first symbolic events, the indexed audio lookup is bounded to +/-30 seconds around
    that event's current projected time. Nearby raw shifts are coalesced into 50 ms
    buckets. Repeated reliable equal-pitch evidence receives extra proposal weight, but
    onset-only evidence can still propose a correction when pitch classification is weak.

    The leading-edge hypothesis is inserted explicitly before ranked periodic candidates so
    a crowded repeating riff cannot evict the only translation that aligns the score start.
    """

    starts, ordered = _audio_index(audio_notes) if index is None else index
    buckets: Counter[float] = Counter()
    for symbolic in source_notes[:24]:
        projected = map_source_time(report, symbolic.start_seconds)
        for _audio_index_value, audio_note in _nearby_indexed_audio(
            starts,
            ordered,
            projected,
            _MAX_SHIFT_SECONDS,
        ):
            shift = audio_note.start - projected
            bucket = round(shift / _SHIFT_BUCKET_SECONDS) * _SHIFT_BUCKET_SECONDS
            pitch_weight = (
                3
                if audio_note.midi == symbolic.midi
                and audio_note.pitch_confidence >= 0.55
                else 1
            )
            buckets[bucket] += pitch_weight

    ranked = sorted(
        buckets.items(),
        key=lambda item: (-item[1], abs(item[0]), item[0]),
    )
    candidates = [0.0]
    edge_shift = _edge_shift_candidate(source_notes, report, audio_notes)
    if edge_shift is not None and abs(edge_shift) > 1e-9:
        candidates.append(edge_shift)
    candidates.extend(
        shift
        for shift, _support in ranked[:_MAX_SHIFT_HYPOTHESES]
        if abs(shift) > 1e-9
    )
    # Preserve proposal order while removing duplicate zero/edge/bucket candidates.
    return list(dict.fromkeys(candidates))


def _shift_regions(report: AlignmentReport, shift_seconds: float) -> list[AlignmentRegion]:
    """Translate/clip regions without upgrading their original confidence evidence."""

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
        raise ValueError("content-aware alignment refinement leaves no in-recording regions")
    return regions


def _shift_report(report: AlignmentReport, shift_seconds: float) -> AlignmentReport:
    """Translate the score clock while preserving EOF-style score pre-roll semantics.

    Editor on Fire's GP/GPA importer permits synchronization to place leading symbolic
    beats before audio time zero. It then omits those pre-zero beats and offsets subsequent
    source beat positions instead of rejecting the synchronization. This Python port keeps
    the same semantic boundary: transformed anchors before zero are omitted, at least two
    in-recording anchors must remain, and earlier source positions are represented by
    linear extrapolation from the retained beat map.

    Region-local residual/confidence evidence is translated or clipped, never replaced by
    stronger anchor/global confidence. This keeps reconciliation review thresholds intact.

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

    return report.model_copy(
        update={
            "global_offset_seconds": report.global_offset_seconds + shift_seconds,
            "anchors": anchors,
            "regions": _shift_regions(report, shift_seconds),
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
    one-to-one onset agreement plus reliable pitch matches. When periodic material leaves
    several translations competitive, a supported leading score/audio onset edge breaks
    the tie instead of preferring the smaller-magnitude late translation.
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
    index = _audio_index(audio_notes)
    candidates = _candidate_shifts(source_notes, report, audio_notes, index=index)
    baseline_score, baseline_onsets, baseline_pitches = _match_evidence(
        source_notes,
        report,
        audio_notes,
        shift_seconds=0.0,
        index=index,
    )

    edge_min_support = (
        min(4, max(2, len(source_notes[:_EDGE_MATCH_LIMIT]) // 2)) if source_notes else 4
    )
    proposal_order = {shift: position for position, shift in enumerate(candidates)}
    ranked: list[tuple[int, int, int, int, int, bool, float, float]] = []
    for shift in candidates:
        score, onset_matches, pitch_matches = _match_evidence(
            source_notes,
            report,
            audio_notes,
            shift_seconds=shift,
            index=index,
        )
        edge_aligned, edge_matches, edge_error = _edge_match_evidence(
            source_notes,
            report,
            audio_notes,
            shift_seconds=shift,
        )
        edge_supported = edge_aligned and edge_matches >= edge_min_support
        rank_score = score + (_EDGE_RANK_BONUS if edge_supported else 0)
        ranked.append(
            (
                rank_score,
                score,
                edge_matches,
                pitch_matches,
                onset_matches,
                edge_supported,
                edge_error,
                shift,
            )
        )
    ranked.sort(
        key=lambda item: (
            -item[0],
            -item[1],
            -item[2],
            -item[3],
            -item[4],
            not item[5],
            proposal_order[item[7]],
            abs(item[7]),
            item[7],
        )
    )

    (
        best_rank_score,
        best_score,
        best_edge_matches,
        best_pitches,
        best_onsets,
        best_edge_supported,
        best_edge_error,
        best_shift,
    ) = ranked[0]
    second_distinct = next(
        (
            item
            for item in ranked[1:]
            if abs(item[7] - best_shift) >= _DISTINCT_SHIFT_SECONDS
        ),
        None,
    )
    second_rank_score = second_distinct[0] if second_distinct is not None else 0
    second_score = second_distinct[1] if second_distinct is not None else 0
    improvement = best_score - baseline_score
    winner_margin = best_score - second_score
    rank_margin = best_rank_score - second_rank_score
    minimum_onset_support = min(8, max(4, len(source_notes[:64]) // 8)) if source_notes else 8
    has_pitch_support = best_pitches >= 2
    has_strong_rhythmic_support = best_onsets >= 12 and improvement >= 8 and winner_margin >= 3
    standard_support = (
        improvement >= 4
        and winner_margin >= 1
        and (has_pitch_support or has_strong_rhythmic_support)
    )
    edge_disambiguation_support = (
        best_edge_supported
        and best_score >= baseline_score
        and best_pitches >= 2
        and rank_margin >= 2
    )
    applied = (
        abs(best_shift) >= 0.20
        and best_onsets >= minimum_onset_support
        and (standard_support or edge_disambiguation_support)
    )

    proposed_shift = best_shift
    edge_detail = (
        f", leading-edge support {best_edge_matches}/{min(_EDGE_MATCH_LIMIT, len(source_notes))} "
        f"(first-onset error {best_edge_error:.3f}s)"
        if best_edge_supported
        else ""
    )
    if applied:
        refined = _shift_report(report, best_shift)
        refined.write_json(alignment_path)
        reason = (
            f"Applied {best_shift:+.3f}s: weighted timing/pitch evidence changed from "
            f"{baseline_score} ({baseline_onsets} onsets/{baseline_pitches} pitch) to "
            f"{best_score} ({best_onsets} onsets/{best_pitches} pitch), "
            f"distinct raw margin {winner_margin}, ranked margin {rank_margin}{edge_detail}."
        )
    else:
        best_shift = 0.0
        reason = (
            "No global onset correction had enough clearly distinguished support; "
            f"baseline {baseline_score} ({baseline_onsets} onsets/{baseline_pitches} pitch), "
            f"best candidate {proposed_shift:+.3f}s scored {best_score} "
            f"({best_onsets} onsets/{best_pitches} pitch), distinct raw margin {winner_margin}, "
            f"ranked margin {rank_margin}{edge_detail}."
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

    # Any execution under refinement-v3 invalidates authorities and derivatives built
    # from the previous transform. They must be regenerated/re-promoted through the
    # existing workflow gates; a periodic-riff late preview must never remain current.
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
