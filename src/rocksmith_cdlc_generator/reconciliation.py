from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .alignment import AlignmentReport, map_source_time
from .source_import import ImportedSource, SourceTrustClass
from .transcription import BassTranscription, NoteEvent, read_transcription

EvidenceStatus = Literal["verified_match", "pitch_conflict", "symbolic_only", "audio_only"]


class ReconciledBassNote(BaseModel):
    start_seconds: float = Field(ge=0)
    duration_seconds: float = Field(gt=0)
    midi: int = Field(ge=0, le=127)
    string_index: int | None = Field(default=None, ge=0)
    fret: int | None = Field(default=None, ge=0)
    techniques: list[str] = Field(default_factory=list)
    status: EvidenceStatus
    trust_class: SourceTrustClass
    review_required: bool
    symbolic_start_seconds: float | None = Field(default=None, ge=0)
    audio_start_seconds: float | None = Field(default=None, ge=0)
    onset_delta_seconds: float | None = Field(default=None, ge=0)
    symbolic_midi: int | None = Field(default=None, ge=0, le=127)
    audio_midi: int | None = Field(default=None, ge=0, le=127)
    symbolic_import_confidence: float | None = Field(default=None, ge=0, le=1)
    audio_confidence: float | None = Field(default=None, ge=0, le=1)
    alignment_confidence: float = Field(ge=0, le=1)


class ReconciledBassChart(BaseModel):
    schema_version: int = 1
    source_sha256: str
    track_index: int = Field(ge=0)
    onset_tolerance_seconds: float = Field(gt=0)
    verified_onset_tolerance_seconds: float = Field(gt=0)
    notes: list[ReconciledBassNote]
    # Present only when this chart was built by materializing a human-composed
    # multi-track note stream (score role composition, issue #232) rather than the
    # ordinary single confirmed-primary-track import. Both fields are bound together:
    # either both are set (composed) or both are None (single-track). Mirrors
    # ``SharedGuitarDraftManifest.composed_source_track_indices`` /
    # ``composed_fanout_record_sha256`` in ``shared_guitar.py``. Bass fan-out does not
    # yet populate these (composed multi-track consumption is not wired in for Bass
    # yet), but the fields exist so staleness invalidation can be bound to the full
    # fan-out content identity, not ``(score_sha256, track_index)`` alone -- see "Trap 2"
    # in docs/score-role-composition-fanout-review.md.
    composed_source_track_indices: list[int] | None = None
    composed_fanout_record_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class SourceDisagreement(BaseModel):
    status: Literal["pitch_conflict", "symbolic_only", "audio_only"]
    review_required: bool = True
    symbolic_start_seconds: float | None = Field(default=None, ge=0)
    audio_start_seconds: float | None = Field(default=None, ge=0)
    onset_delta_seconds: float | None = Field(default=None, ge=0)
    symbolic_midi: int | None = Field(default=None, ge=0, le=127)
    audio_midi: int | None = Field(default=None, ge=0, le=127)
    symbolic_string_index: int | None = Field(default=None, ge=0)
    symbolic_fret: int | None = Field(default=None, ge=0)
    audio_confidence: float | None = Field(default=None, ge=0, le=1)
    alignment_confidence: float = Field(ge=0, le=1)
    reason: str


class SourceDisagreementReport(BaseModel):
    schema_version: int = 1
    source_sha256: str
    track_index: int = Field(ge=0)
    disagreements: list[SourceDisagreement]
    # See ``ReconciledBassChart.composed_source_track_indices`` /
    # ``composed_fanout_record_sha256`` above; the same identity binding applies here.
    composed_source_track_indices: list[int] | None = None
    composed_fanout_record_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


def _alignment_confidence_at(report: AlignmentReport, source_time: float) -> float:
    for region in report.regions:
        if region.source_start_seconds <= source_time <= region.source_end_seconds:
            return region.confidence
    return report.confidence


def _mapped_duration(report: AlignmentReport, start: float, duration: float) -> float:
    mapped_start = map_source_time(report, start)
    mapped_end = map_source_time(report, start + duration)
    return max(0.001, mapped_end - mapped_start)


def _nearest_unmatched_audio(
    audio_notes: list[NoteEvent],
    used_audio: set[int],
    target_start: float,
    tolerance: float,
) -> tuple[int, NoteEvent, float] | None:
    candidates: list[tuple[float, int, NoteEvent]] = []
    for index, note in enumerate(audio_notes):
        if index in used_audio:
            continue
        delta = abs(note.start - target_start)
        if delta <= tolerance:
            candidates.append((delta, index, note))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    delta, index, note = candidates[0]
    return index, note, delta


def reconcile_bass_sources(
    source: ImportedSource,
    alignment: AlignmentReport,
    audio: BassTranscription,
    *,
    onset_tolerance_seconds: float = 0.15,
    verified_onset_tolerance_seconds: float = 0.08,
    minimum_audio_confidence: float = 0.70,
    minimum_alignment_confidence: float = 0.70,
) -> tuple[ReconciledBassChart, SourceDisagreementReport]:
    if onset_tolerance_seconds <= 0:
        raise ValueError("onset tolerance must be positive")
    if verified_onset_tolerance_seconds <= 0:
        raise ValueError("verified onset tolerance must be positive")
    if verified_onset_tolerance_seconds > onset_tolerance_seconds:
        raise ValueError("verified onset tolerance cannot exceed matching tolerance")
    if not 0 <= minimum_audio_confidence <= 1:
        raise ValueError("minimum audio confidence must be between 0 and 1")
    if not 0 <= minimum_alignment_confidence <= 1:
        raise ValueError("minimum alignment confidence must be between 0 and 1")
    if source.provenance.source_sha256 != alignment.source_sha256:
        raise ValueError("alignment source SHA-256 does not match imported source")

    track = next((t for t in source.tracks if t.source_track_index == alignment.track_index), None)
    if track is None:
        raise ValueError(f"alignment track index {alignment.track_index} not found in imported source")

    used_audio: set[int] = set()
    reconciled: list[ReconciledBassNote] = []
    disagreements: list[SourceDisagreement] = []

    for symbolic in track.notes:
        mapped_start = map_source_time(alignment, symbolic.start_seconds)
        mapped_duration = _mapped_duration(alignment, symbolic.start_seconds, symbolic.duration_seconds)
        region_confidence = _alignment_confidence_at(alignment, symbolic.start_seconds)
        nearest = _nearest_unmatched_audio(audio.notes, used_audio, mapped_start, onset_tolerance_seconds)

        if nearest is None:
            reconciled.append(ReconciledBassNote(
                start_seconds=mapped_start,
                duration_seconds=mapped_duration,
                midi=symbolic.midi,
                string_index=symbolic.string_index,
                fret=symbolic.fret,
                techniques=symbolic.techniques,
                status="symbolic_only",
                trust_class=symbolic.trust_class,
                review_required=True,
                symbolic_start_seconds=symbolic.start_seconds,
                symbolic_midi=symbolic.midi,
                symbolic_import_confidence=symbolic.import_confidence,
                alignment_confidence=region_confidence,
            ))
            disagreements.append(SourceDisagreement(
                status="symbolic_only",
                symbolic_start_seconds=symbolic.start_seconds,
                symbolic_midi=symbolic.midi,
                symbolic_string_index=symbolic.string_index,
                symbolic_fret=symbolic.fret,
                alignment_confidence=region_confidence,
                reason="No audio-derived Bass onset was found within the reconciliation window.",
            ))
            continue

        audio_index, audio_note, onset_delta = nearest
        used_audio.add(audio_index)

        if audio_note.midi != symbolic.midi:
            reconciled.append(ReconciledBassNote(
                start_seconds=mapped_start,
                duration_seconds=mapped_duration,
                midi=symbolic.midi,
                string_index=symbolic.string_index,
                fret=symbolic.fret,
                techniques=symbolic.techniques,
                status="pitch_conflict",
                trust_class=symbolic.trust_class,
                review_required=True,
                symbolic_start_seconds=symbolic.start_seconds,
                audio_start_seconds=audio_note.start,
                onset_delta_seconds=onset_delta,
                symbolic_midi=symbolic.midi,
                audio_midi=audio_note.midi,
                symbolic_import_confidence=symbolic.import_confidence,
                audio_confidence=audio_note.confidence,
                alignment_confidence=region_confidence,
            ))
            disagreements.append(SourceDisagreement(
                status="pitch_conflict",
                symbolic_start_seconds=symbolic.start_seconds,
                audio_start_seconds=audio_note.start,
                onset_delta_seconds=onset_delta,
                symbolic_midi=symbolic.midi,
                audio_midi=audio_note.midi,
                symbolic_string_index=symbolic.string_index,
                symbolic_fret=symbolic.fret,
                audio_confidence=audio_note.confidence,
                alignment_confidence=region_confidence,
                reason="Symbolic and audio-derived notes occur together but disagree on MIDI pitch.",
            ))
            continue

        strongly_supported = (
            onset_delta <= verified_onset_tolerance_seconds
            and audio_note.confidence >= minimum_audio_confidence
            and region_confidence >= minimum_alignment_confidence
            and not audio_note.review_required
        )
        reconciled.append(ReconciledBassNote(
            start_seconds=mapped_start,
            duration_seconds=mapped_duration,
            midi=symbolic.midi,
            string_index=symbolic.string_index,
            fret=symbolic.fret,
            techniques=symbolic.techniques,
            status="verified_match",
            trust_class=SourceTrustClass.symbolic_verified if strongly_supported else symbolic.trust_class,
            review_required=not strongly_supported,
            symbolic_start_seconds=symbolic.start_seconds,
            audio_start_seconds=audio_note.start,
            onset_delta_seconds=onset_delta,
            symbolic_midi=symbolic.midi,
            audio_midi=audio_note.midi,
            symbolic_import_confidence=symbolic.import_confidence,
            audio_confidence=audio_note.confidence,
            alignment_confidence=region_confidence,
        ))

    for index, audio_note in enumerate(audio.notes):
        if index in used_audio:
            continue
        reconciled.append(ReconciledBassNote(
            start_seconds=audio_note.start,
            duration_seconds=audio_note.duration,
            midi=audio_note.midi,
            status="audio_only",
            trust_class=SourceTrustClass.audio_derived,
            review_required=True,
            audio_start_seconds=audio_note.start,
            audio_midi=audio_note.midi,
            audio_confidence=audio_note.confidence,
            alignment_confidence=alignment.confidence,
        ))
        disagreements.append(SourceDisagreement(
            status="audio_only",
            audio_start_seconds=audio_note.start,
            audio_midi=audio_note.midi,
            audio_confidence=audio_note.confidence,
            alignment_confidence=alignment.confidence,
            reason="Audio transcription contains a Bass note with no symbolic match inside the onset window.",
        ))

    reconciled.sort(key=lambda note: (note.start_seconds, note.midi, note.status))
    disagreements.sort(key=lambda item: (
        item.audio_start_seconds if item.audio_start_seconds is not None
        else item.symbolic_start_seconds if item.symbolic_start_seconds is not None
        else 0.0,
        item.status,
    ))
    return (
        ReconciledBassChart(
            source_sha256=source.provenance.source_sha256,
            track_index=alignment.track_index,
            onset_tolerance_seconds=onset_tolerance_seconds,
            verified_onset_tolerance_seconds=verified_onset_tolerance_seconds,
            notes=reconciled,
        ),
        SourceDisagreementReport(
            source_sha256=source.provenance.source_sha256,
            track_index=alignment.track_index,
            disagreements=disagreements,
        ),
    )


def reconcile_project_bass(
    project_dir: Path,
    source_path: Path,
    *,
    alignment_path: Path | None = None,
    onset_tolerance_seconds: float = 0.15,
    verified_onset_tolerance_seconds: float = 0.08,
) -> dict[str, Path]:
    project_dir = project_dir.resolve()
    source_path = source_path.resolve()
    alignment_path = alignment_path.resolve() if alignment_path is not None else project_dir / "analysis" / "alignment.json"
    transcription_path = project_dir / "analysis" / "bass_raw.json"

    if not alignment_path.is_file():
        raise FileNotFoundError("analysis/alignment.json not found; run `cdlc align-source` first")
    if not transcription_path.is_file():
        raise FileNotFoundError("analysis/bass_raw.json not found; run `cdlc transcribe-bass` first")

    source = ImportedSource.read_json(source_path)
    alignment = AlignmentReport.model_validate_json(alignment_path.read_text(encoding="utf-8"))
    audio = read_transcription(transcription_path)
    chart, disagreement_report = reconcile_bass_sources(
        source,
        alignment,
        audio,
        onset_tolerance_seconds=onset_tolerance_seconds,
        verified_onset_tolerance_seconds=verified_onset_tolerance_seconds,
    )

    chart_path = project_dir / "charts" / "bass_reconciled.json"
    review_path = project_dir / "review" / "source_disagreements.json"
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.parent.mkdir(parents=True, exist_ok=True)
    chart_path.write_text(chart.model_dump_json(indent=2), encoding="utf-8")
    review_path.write_text(disagreement_report.model_dump_json(indent=2), encoding="utf-8")
    return {"chart": chart_path, "review": review_path}
