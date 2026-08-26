from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .source_import import ImportedSource, SourceNoteEvent
from .transcription import NoteEvent, read_transcription


SOURCE_TIMING_QUALIFICATION_PATH = Path("analysis") / "source_timing_qualification.json"
_SHIFT_BUCKET_SECONDS = 0.05
_MAX_SHIFT_SECONDS = 30.0
_DISTINCT_SHIFT_SECONDS = 0.36
_MAX_SHIFT_HYPOTHESES = 48
_EDGE_TOLERANCE_SECONDS = 0.18
_EDGE_MATCH_LIMIT = 8


class SourceTimingQualification(BaseModel):
    """Media-free evidence that a score timing candidate agrees with the recording.

    This gate diagnoses rather than repairs timing. A strong repeated mismatch blocks
    promotion; weak evidence falls back to the existing human timing-review gate instead
    of inventing an offset.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    method: Literal["multi-event-bass-onset-consistency-v2"] = (
        "multi-event-bass-onset-consistency-v2"
    )
    recording_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority_output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority_track_index: int = Field(ge=0)
    status: Literal["pass", "review_required", "insufficient_evidence"]
    compared_symbolic_notes: int = Field(ge=0)
    usable_audio_notes: int = Field(ge=0)
    baseline_match_count: int = Field(ge=0)
    best_match_count: int = Field(ge=0)
    second_best_match_count: int = Field(ge=0)
    best_shift_seconds: float
    first_projected_note_seconds: float | None = None
    first_audio_note_seconds: float | None = None
    reason: str

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path


def _project_time(anchors: list[Any], source_time: float) -> float:
    if len(anchors) < 2:
        raise ValueError("timing qualification requires at least two alignment anchors")
    if source_time <= anchors[0].source_time_seconds:
        first, second = anchors[0], anchors[1]
    elif source_time >= anchors[-1].source_time_seconds:
        first, second = anchors[-2], anchors[-1]
    else:
        source_times = [item.source_time_seconds for item in anchors]
        right = bisect_right(source_times, source_time)
        first, second = anchors[right - 1], anchors[right]
    span = second.source_time_seconds - first.source_time_seconds
    if span <= 0:
        raise ValueError("timing qualification candidate anchors are not strictly increasing")
    fraction = (source_time - first.source_time_seconds) / span
    return first.audio_time_seconds + fraction * (
        second.audio_time_seconds - first.audio_time_seconds
    )


def _usable_audio_notes(notes: list[NoteEvent]) -> list[NoteEvent]:
    """Keep strong onset+pitch evidence; review-required status alone does not discard it."""

    return [
        note
        for note in notes
        if note.confidence >= 0.60
        and note.timing_confidence >= 0.75
        and note.pitch_confidence >= 0.60
    ]


def _audio_by_midi_index(
    audio_notes: list[NoteEvent],
) -> dict[int, tuple[list[float], list[tuple[int, NoteEvent]]]]:
    grouped: dict[int, list[tuple[int, NoteEvent]]] = {}
    for index, note in enumerate(audio_notes):
        grouped.setdefault(note.midi, []).append((index, note))

    result: dict[int, tuple[list[float], list[tuple[int, NoteEvent]]]] = {}
    for midi, items in grouped.items():
        items.sort(key=lambda item: item[1].start)
        result[midi] = ([item[1].start for item in items], items)
    return result


def _nearby_same_pitch(
    by_midi: dict[int, tuple[list[float], list[tuple[int, NoteEvent]]]],
    midi: int,
    center: float,
    radius: float,
) -> list[tuple[int, NoteEvent]]:
    indexed = by_midi.get(midi)
    if indexed is None:
        return []
    starts, items = indexed
    left = bisect_left(starts, center - radius)
    right = bisect_right(starts, center + radius)
    return items[left:right]


def _leading_edge_shift(
    source_notes: list[SourceNoteEvent],
    anchors: list[Any],
    audio_notes: list[NoteEvent],
    *,
    by_midi: dict[int, tuple[list[float], list[tuple[int, NoteEvent]]]] | None = None,
) -> float | None:
    """Return the first-score-event to earliest reliable equal-pitch audio translation."""

    if not source_notes or not audio_notes:
        return None
    index = _audio_by_midi_index(audio_notes) if by_midi is None else by_midi
    first = source_notes[0]
    projected = _project_time(anchors, first.start_seconds)
    candidates = _nearby_same_pitch(
        index,
        first.midi,
        projected,
        _MAX_SHIFT_SECONDS,
    )
    if not candidates:
        return None
    earliest = min((note for _audio_index, note in candidates), key=lambda note: note.start)
    shift = earliest.start - projected
    return round(shift / _SHIFT_BUCKET_SECONDS) * _SHIFT_BUCKET_SECONDS


def _candidate_shifts(
    source_notes: list[SourceNoteEvent],
    anchors: list[Any],
    audio_notes: list[NoteEvent],
    *,
    by_midi: dict[int, tuple[list[float], list[tuple[int, NoteEvent]]]] | None = None,
) -> list[float]:
    """Return bounded repeated translation hypotheses around the actual score passage.

    The audio evidence is indexed by pitch and searched +/-30 seconds around each projected
    symbolic event. The explicit leading-edge hypothesis is retained even when a repeating
    riff fills the normal candidate budget with measure-spaced alternatives.
    """

    index = _audio_by_midi_index(audio_notes) if by_midi is None else by_midi
    buckets: Counter[float] = Counter()
    for symbolic in source_notes[:24]:
        projected = _project_time(anchors, symbolic.start_seconds)
        for _audio_index_value, audio_note in _nearby_same_pitch(
            index,
            symbolic.midi,
            projected,
            _MAX_SHIFT_SECONDS,
        ):
            shift = audio_note.start - projected
            bucket = round(shift / _SHIFT_BUCKET_SECONDS) * _SHIFT_BUCKET_SECONDS
            buckets[bucket] += 1

    ranked = sorted(
        buckets.items(),
        key=lambda item: (-item[1], abs(item[0]), item[0]),
    )
    candidates = [0.0]
    edge_shift = _leading_edge_shift(
        source_notes,
        anchors,
        audio_notes,
        by_midi=index,
    )
    if edge_shift is not None and abs(edge_shift) > 1e-9:
        candidates.append(edge_shift)
    candidates.extend(
        shift
        for shift, _count in ranked[:_MAX_SHIFT_HYPOTHESES]
        if abs(shift) > 1e-9
    )
    return list(dict.fromkeys(candidates))


def _match_count(
    source_notes: list[SourceNoteEvent],
    anchors: list[Any],
    audio_notes: list[NoteEvent],
    *,
    shift_seconds: float,
    tolerance_seconds: float = 0.18,
    by_midi: dict[int, tuple[list[float], list[tuple[int, NoteEvent]]]] | None = None,
    limit: int = 64,
) -> int:
    """Count indexed one-to-one equal-pitch onset matches for one translation."""

    index = _audio_by_midi_index(audio_notes) if by_midi is None else by_midi
    unused = set(range(len(audio_notes)))
    matches = 0
    for symbolic in source_notes[:limit]:
        projected = _project_time(anchors, symbolic.start_seconds) + shift_seconds
        candidates = [
            (audio_index, note)
            for audio_index, note in _nearby_same_pitch(
                index,
                symbolic.midi,
                projected,
                tolerance_seconds,
            )
            if audio_index in unused
        ]
        if not candidates:
            continue
        audio_index, _note = min(
            candidates,
            key=lambda item: abs(item[1].start - projected),
        )
        unused.remove(audio_index)
        matches += 1
    return matches


def _insufficient(
    candidate: Any,
    *,
    symbolic: int,
    audio: int,
    reason: str,
) -> SourceTimingQualification:
    return SourceTimingQualification(
        recording_sha256=candidate.recording_sha256,
        score_sha256=candidate.score_sha256,
        authority_output_sha256=candidate.authority_output_sha256,
        authority_track_index=candidate.authority_track_index,
        status="insufficient_evidence",
        compared_symbolic_notes=symbolic,
        usable_audio_notes=audio,
        baseline_match_count=0,
        best_match_count=0,
        second_best_match_count=0,
        best_shift_seconds=0.0,
        reason=reason,
    )


def qualify_project_score_timing(
    project_dir: Path,
    candidate: Any,
) -> SourceTimingQualification:
    """Qualify a shared score-to-recording candidate before it becomes song authority.

    A strong repeated non-zero translation becomes ``review_required``. A well-supported
    current translation becomes ``pass``. Sparse or ambiguous evidence becomes
    ``insufficient_evidence`` and leaves human timing review authoritative. A complete
    score whose first reliable event binds to a later repetition is also blocked when the
    earlier leading edge is supported by a short repeated equal-pitch sequence.
    """

    project = project_dir.expanduser().resolve()
    source_path = (project / candidate.authority_output_json).resolve()
    if not source_path.is_relative_to(project) or not source_path.is_file():
        raise ValueError(
            "source timing qualification authority output is not a current project file"
        )

    imported = ImportedSource.read_json(source_path)
    track = next(
        (
            item
            for item in imported.tracks
            if item.source_track_index == candidate.authority_track_index
        ),
        None,
    )
    if track is None:
        raise ValueError("source timing qualification cannot find the authority track")
    source_notes = list(track.notes[:64])

    transcription_path = project / "analysis" / "bass_raw.json"
    if not transcription_path.is_file():
        report = _insufficient(
            candidate,
            symbolic=len(source_notes),
            audio=0,
            reason=(
                "No audio-derived Bass transcription is available for independent "
                "multi-event timing qualification."
            ),
        )
        report.write_json(project / SOURCE_TIMING_QUALIFICATION_PATH)
        return report

    audio = read_transcription(transcription_path)
    audio_notes = _usable_audio_notes(list(audio.notes))
    if len(source_notes) < 4 or len(audio_notes) < 4:
        report = _insufficient(
            candidate,
            symbolic=len(source_notes),
            audio=len(audio_notes),
            reason=(
                "Fewer than four strong symbolic/audio events are available; do not "
                "infer a global score offset."
            ),
        )
        report.write_json(project / SOURCE_TIMING_QUALIFICATION_PATH)
        return report

    anchors = list(candidate.anchors)
    by_midi = _audio_by_midi_index(audio_notes)
    shifts = _candidate_shifts(
        source_notes,
        anchors,
        audio_notes,
        by_midi=by_midi,
    )
    scored = [
        (
            _match_count(
                source_notes,
                anchors,
                audio_notes,
                shift_seconds=shift,
                by_midi=by_midi,
            ),
            shift,
        )
        for shift in shifts
    ]
    scored.sort(key=lambda item: (-item[0], abs(item[1]), item[1]))

    best_count, best_shift = scored[0]
    second_count = next(
        (
            count
            for count, shift in scored[1:]
            if abs(shift - best_shift) >= _DISTINCT_SHIFT_SECONDS
        ),
        0,
    )
    baseline = next((count for count, shift in scored if abs(shift) <= 1e-9), 0)
    improvement = best_count - baseline
    margin = best_count - second_count
    minimum_support = max(5, min(8, len(source_notes) // 8 or 5))

    first_projected = _project_time(anchors, source_notes[0].start_seconds)
    first_audio = min(note.start for note in audio_notes)
    edge_shift = _leading_edge_shift(
        source_notes,
        anchors,
        audio_notes,
        by_midi=by_midi,
    )
    edge_count = (
        _match_count(
            source_notes,
            anchors,
            audio_notes,
            shift_seconds=edge_shift,
            tolerance_seconds=_EDGE_TOLERANCE_SECONDS,
            by_midi=by_midi,
            limit=_EDGE_MATCH_LIMIT,
        )
        if edge_shift is not None
        else 0
    )
    edge_minimum_support = min(4, max(2, len(source_notes[:_EDGE_MATCH_LIMIT]) // 2))
    edge_mismatch = (
        edge_shift is not None
        and abs(edge_shift) >= 0.75
        and edge_count >= edge_minimum_support
    )

    if best_count >= minimum_support and abs(best_shift) <= 0.35 and not edge_mismatch:
        status: Literal["pass", "review_required", "insufficient_evidence"] = "pass"
        reason = (
            "Current score-to-recording translation is supported by "
            f"{best_count} repeated equal-pitch onset matches; best residual translation "
            f"is only {best_shift:+.3f}s."
        )
    elif edge_mismatch:
        status = "review_required"
        best_shift = edge_shift
        best_count = max(best_count, edge_count)
        reason = (
            f"Probable leading-edge score/alignment mismatch: the first reliable score "
            f"event and {edge_count}/{min(_EDGE_MATCH_LIMIT, len(source_notes))} early "
            f"equal-pitch events support a {edge_shift:+.3f}s translation. A repeating "
            "riff must not bind the complete score to a later measure-spaced repetition; "
            "review/rebuild alignment before promotion."
        )
    elif (
        abs(best_shift) >= 0.75
        and best_count >= minimum_support
        and improvement >= 3
        and margin >= 2
    ):
        status = "review_required"
        reason = (
            f"Probable source/alignment mismatch: a {best_shift:+.3f}s translation yields "
            f"{best_count} repeated matches versus {baseline} at the current timing, with "
            f"a {margin}-match lead over the next distinct hypothesis. Do not promote this "
            "score as timing authority until the score version and alignment are reviewed."
        )
    else:
        status = "insufficient_evidence"
        reason = (
            f"Timing evidence is ambiguous: current timing has {baseline} repeated matches; "
            f"best hypothesis has {best_count} at {best_shift:+.3f}s with distinct-hypothesis "
            f"margin {margin}. Keep human timing review authoritative."
        )

    report = SourceTimingQualification(
        recording_sha256=candidate.recording_sha256,
        score_sha256=candidate.score_sha256,
        authority_output_sha256=candidate.authority_output_sha256,
        authority_track_index=candidate.authority_track_index,
        status=status,
        compared_symbolic_notes=len(source_notes),
        usable_audio_notes=len(audio_notes),
        baseline_match_count=baseline,
        best_match_count=best_count,
        second_best_match_count=second_count,
        best_shift_seconds=best_shift,
        first_projected_note_seconds=first_projected,
        first_audio_note_seconds=first_audio,
        reason=reason,
    )
    report.write_json(project / SOURCE_TIMING_QUALIFICATION_PATH)
    return report
