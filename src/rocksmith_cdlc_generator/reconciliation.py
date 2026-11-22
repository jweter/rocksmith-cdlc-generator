from __future__ import annotations

import re
import wave
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .alignment import AlignmentReport, map_source_time
from .hashing import sha256_file
from .models import ProjectManifest
from .source_import import ImportedSource, SourceTrustClass
from .transcription import BassTranscription, NoteEvent, read_transcription
from .stems import StemSeparationError, verified_project_stem
from .stem_content_alignment import audit_stem_content_alignment, write_project_bass_stem_clock_audit
from .stem_signal_distinctness import screen_stem_nontrivial_difference
from .bass_octave_negative import inspect_bass_octave_leakage
from .bass_negative_signal import screen_bass_stem_obvious_negatives
from .bass_attack_evidence import BassAttackEvidence, inspect_bass_attack_onset, MIN_ATTACK_CONFIDENCE, MAX_DELAY_SECONDS

EvidenceStatus = Literal["verified_match", "pitch_conflict", "symbolic_only", "audio_only"]
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

# Bump whenever reconciliation semantics can change persisted Bass authority. Existing
# artifacts that predate this field must be treated as stale rather than silently reused.
# v3 bound input hashes/pitch/timing; v4 requires content-clock agreement.
# v5 also rejects exact, gain-scaled or otherwise indistinguishable copies of
# the original mix; v6 carries explicit per-note trust explanations.
# v7 vetoes silence-only/transient-only Bass stem candidates before note trust.
# v8 also vetoes measured stable octave-only evidence at the individual
# score-matched Bass note: old v7 charts do not contain that negative proof.
# v9 independently measures attack/onset evidence on actual verified stem PCM,
# so a confident pYIN pitch event alone can never certify onset timing.
CURRENT_RECONCILIATION_ALGORITHM_VERSION = 9


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
    qualification_reasons: list[str] = Field(default_factory=list)
    qualification_observations: dict[str, float | bool] = Field(default_factory=dict)
    qualification_thresholds: dict[str, float] = Field(default_factory=dict)


class ReconciledBassChart(BaseModel):
    schema_version: int = 1
    reconciliation_algorithm_version: int = CURRENT_RECONCILIATION_ALGORITHM_VERSION
    audio_evidence_provenance: Literal["verified_stem", "unqualified"] = "unqualified"
    source_sha256: str
    track_index: int = Field(ge=0)
    source_content_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    onset_tolerance_seconds: float = Field(gt=0)
    verified_onset_tolerance_seconds: float = Field(gt=0)
    notes: list[ReconciledBassNote]


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
    source_content_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    disagreements: list[SourceDisagreement]
    omitted_trailing_symbolic_count: int = Field(default=0, ge=0)
    first_omitted_projected_time_seconds: float | None = Field(default=None, ge=0)


def reconciled_bass_chart_is_current(path: Path) -> bool:
    """Return whether a persisted reconciliation was produced by current semantics.

    Pydantic defaults cannot distinguish an old JSON file that lacks the version field
    unless we inspect ``model_fields_set``. That distinction is essential here: otherwise
    a pre-#360 artifact would default to the current version and remain falsely current.
    """

    try:
        chart = ReconciledBassChart.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if "reconciliation_algorithm_version" not in chart.model_fields_set:
        return False
    if chart.reconciliation_algorithm_version != CURRENT_RECONCILIATION_ALGORITHM_VERSION:
        return False
    # Pydantic defaults must not silently turn an old chart with a manually
    # updated version number into current evidence: each authored note must
    # explicitly contain its actual trust reason and threshold dictionary.
    return all(
        "qualification_reasons" in note.model_fields_set
        and bool(note.qualification_reasons)
        and "qualification_thresholds" in note.model_fields_set
        for note in chart.notes
    )


def is_verified_bass_stem_transcription(project_dir: Path, audio: BassTranscription) -> bool:
    """A hash-bound Bass stem is required before the transcription can promote trust.

    Raw/frequency-filtered mix notes remain comparison evidence only. A matching
    filename by itself is not proof: the existing stem receipt must match both
    the current normalized recording hash and the stem hash.
    """
    project = Path(project_dir).resolve()
    path = Path(audio.source_path)
    if not path.is_absolute():
        path = project / path
    if not path.resolve().is_relative_to(project):
        return False
    try:
        proven = verified_project_stem(project, "bass")
        if path.resolve() != proven:
            return False
        # A filename + freshly written stem receipt cannot prove that the
        # transcription was generated from those bytes. Older transcriptions
        # without a digest are comparison-only until explicitly regenerated.
        if audio.source_sha256 is None or audio.source_sha256 != sha256_file(proven):
            return False
        # Hash identity alone does not establish that a stem is playable on the
        # recording clock. Reject sample-rate/channel/frame geometry mismatch.
        with wave.open(str(project / "audio" / "normalized.wav"), "rb") as master:
            original_geometry = (
                master.getframerate(), master.getnchannels(), master.getnframes(),
                master.getsampwidth(), master.getcomptype(),
            )
        with wave.open(str(proven), "rb") as stem:
            stem_geometry = (
                stem.getframerate(), stem.getnchannels(), stem.getnframes(),
                stem.getsampwidth(), stem.getcomptype(),
            )
        if not (
            original_geometry == stem_geometry
            and original_geometry[0] == audio.sample_rate_hz
            and original_geometry[3] == 2
            and original_geometry[4] == "NONE"
        ):
            return False
        # The separator may preserve frame count yet delay the actual Bass
        # attacks by tens/hundreds of milliseconds. Never promote notes from a
        # shifted, ambiguous or content-silent stem; retain comparison evidence.
        timing = audit_stem_content_alignment(
            project / "audio" / "normalized.wav", proven
        )
        if timing.status != "aligned":
            return False
        # Exact/cloned full mixes can have perfect hashes, timing and even
        # high model confidence without providing independent Bass evidence.
        # This screen only establishes NON-IDENTITY, never separation purity.
        difference = screen_stem_nontrivial_difference(
            project / "audio" / "normalized.wav", proven
        )
        # A role-labeled, hash-bound and non-cloned WAV still may be silent
        # or contain only isolated drum transients. Reject that objective
        # negative before granting *any* audio note symbolic authority.
        # This is only a necessary screen, not proof of Bass source purity.
        if difference.status != "nontrivial_difference":
            return False
        negative = screen_bass_stem_obvious_negatives(proven)
        return (
            negative.not_obviously_negative
            and audio.source_sha256 == sha256_file(proven)
            and verified_project_stem(project, "bass") == proven
        )
    except (StemSeparationError, OSError, ValueError, wave.Error, EOFError):
        return False


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
    *,
    recording_duration_seconds: float | None = None,
) -> tuple[int, NoteEvent, float] | None:
    candidates: list[tuple[float, int, NoteEvent]] = []
    for index, note in enumerate(audio_notes):
        if index in used_audio:
            continue
        if recording_duration_seconds is not None and note.start >= recording_duration_seconds:
            continue
        delta = abs(note.start - target_start)
        if delta <= tolerance:
            candidates.append((delta, index, note))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    delta, index, note = candidates[0]
    return index, note, delta


def _note_qualification(
    *, verified_stem: bool, onset_delta: float, audio_note: NoteEvent,
    region_confidence: float, verified_onset_tolerance_seconds: float,
    minimum_audio_confidence: float, minimum_pitch_confidence: float,
    minimum_timing_confidence: float, minimum_alignment_confidence: float,
    octave_screen_status: str | None = None,
    attack_evidence: BassAttackEvidence | None = None,
) -> tuple[list[str], dict[str, float | bool], dict[str, float]]:
    """Deterministic proof checklist for each pitch-matching Bass event.

    This is a transparency field, not an independent confidence estimator.
    It deliberately uses the *same* thresholds as the existing authority
    gate; source evidence is not promoted by a diagnostic label.
    """
    observations: dict[str, float | bool] = {
        "verified_stem_provenance": verified_stem,
        "onset_delta_seconds": onset_delta,
        "audio_confidence": audio_note.confidence,
        "pitch_confidence": audio_note.pitch_confidence,
        "timing_confidence": audio_note.timing_confidence,
        "alignment_confidence": region_confidence,
        "audio_review_required": audio_note.review_required,
    }
    thresholds = {
        "maximum_verified_onset_delta_seconds": verified_onset_tolerance_seconds,
        "minimum_audio_confidence": minimum_audio_confidence,
        "minimum_pitch_confidence": minimum_pitch_confidence,
        "minimum_timing_confidence": minimum_timing_confidence,
        "minimum_alignment_confidence": minimum_alignment_confidence,
    }
    failures: list[str] = []
    if not verified_stem:
        failures.append("UNVERIFIED_STEM")
    if onset_delta > verified_onset_tolerance_seconds:
        failures.append("ONSET_OUTSIDE_VERIFIED_TOLERANCE")
    if audio_note.confidence < minimum_audio_confidence:
        failures.append("LOW_AUDIO_CONFIDENCE")
    if audio_note.pitch_confidence < minimum_pitch_confidence:
        failures.append("LOW_PITCH_CONFIDENCE")
    if audio_note.timing_confidence < minimum_timing_confidence:
        failures.append("LOW_TIMING_CONFIDENCE")
    if region_confidence < minimum_alignment_confidence:
        failures.append("LOW_ALIGNMENT_CONFIDENCE")
    if audio_note.review_required:
        failures.append("AUDIO_REVIEW_REQUIRED")
    if octave_screen_status is not None:
        # Unknown verdicts must never become implicit success. An unavailable
        # octave measurement blocks trust; a short note is insufficient for
        # this *negative* diagnostic but does not invent positive proof.
        if octave_screen_status not in {
            "octave_leakage", "not_detected", "insufficient_signal", "unavailable"
        }:
            raise ValueError("INVALID_BASS_OCTAVE_NEGATIVE_STATUS")
        observations["octave_leakage_detected"] = octave_screen_status == "octave_leakage"
        if octave_screen_status == "octave_leakage":
            failures.append("OCTAVE_LEAKAGE_NEGATIVE")
        elif octave_screen_status == "unavailable":
            failures.append("OCTAVE_SCREEN_UNAVAILABLE")
    if attack_evidence is not None:
        if not isinstance(attack_evidence, BassAttackEvidence) or attack_evidence.status not in {
            "attack_detected", "no_attack", "insufficient_signal", "unavailable",
        }:
            raise ValueError("INVALID_BASS_ATTACK_EVIDENCE")
        observations["independent_attack_detected"] = attack_evidence.independent_attack
        observations["independent_attack_confidence"] = attack_evidence.confidence
        if attack_evidence.measured_onset_delta_seconds is not None:
            observations["measured_attack_delta_seconds"] = attack_evidence.measured_onset_delta_seconds
        thresholds["minimum_independent_attack_confidence"] = MIN_ATTACK_CONFIDENCE
        thresholds["maximum_independent_attack_delay_seconds"] = MAX_DELAY_SECONDS
        if attack_evidence.status == "unavailable":
            failures.append("ATTACK_SCREEN_UNAVAILABLE")
        elif attack_evidence.status == "insufficient_signal":
            failures.append("INSUFFICIENT_ATTACK_EVIDENCE")
        elif not attack_evidence.independent_attack:
            failures.append(
                "NO_INDEPENDENT_ATTACK" if attack_evidence.status == "no_attack"
                else "LOW_INDEPENDENT_ATTACK_CONFIDENCE"
            )
    return failures if failures else ["QUALIFIED"], observations, thresholds


def reconcile_bass_sources(
    source: ImportedSource,
    alignment: AlignmentReport,
    audio: BassTranscription,
    *,
    onset_tolerance_seconds: float = 0.15,
    verified_onset_tolerance_seconds: float = 0.08,
    minimum_audio_confidence: float = 0.70,
    minimum_pitch_confidence: float = 0.60,
    minimum_timing_confidence: float = 0.75,
    minimum_alignment_confidence: float = 0.70,
    verified_stem_provenance: bool = False,
    octave_negative_probe: Callable[[int, float, float], str] | None = None,
    attack_onset_probe: Callable[[float, float], BassAttackEvidence] | None = None,
    source_content_sha256: str | None = None,
    recording_duration_seconds: float | None = None,
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
    if not 0 <= minimum_pitch_confidence <= 1:
        raise ValueError("minimum pitch confidence must be between 0 and 1")
    if not 0 <= minimum_timing_confidence <= 1:
        raise ValueError("minimum timing confidence must be between 0 and 1")
    if not isinstance(verified_stem_provenance, bool):
        raise ValueError("verified_stem_provenance must be explicitly boolean")
    if octave_negative_probe is not None and not callable(octave_negative_probe):
        raise ValueError("INVALID_BASS_OCTAVE_NEGATIVE_PROBE")
    if attack_onset_probe is not None and not callable(attack_onset_probe):
        raise ValueError("INVALID_BASS_ATTACK_ONSET_PROBE")
    if source_content_sha256 is not None and not _SHA256_PATTERN.match(source_content_sha256):
        raise ValueError("source content SHA-256 must be a lowercase hex digest")
    if recording_duration_seconds is not None and recording_duration_seconds <= 0:
        raise ValueError("recording duration must be positive")
    if source.provenance.source_sha256 != alignment.source_sha256:
        raise ValueError("alignment source SHA-256 does not match imported source")

    track = next((t for t in source.tracks if t.source_track_index == alignment.track_index), None)
    if track is None:
        raise ValueError(f"alignment track index {alignment.track_index} not found in imported source")

    used_audio: set[int] = set()
    reconciled: list[ReconciledBassNote] = []
    disagreements: list[SourceDisagreement] = []
    omitted_trailing_symbolic_count = 0
    first_omitted_projected_time_seconds: float | None = None

    for symbolic in track.notes:
        mapped_start = map_source_time(alignment, symbolic.start_seconds)
        mapped_duration = _mapped_duration(alignment, symbolic.start_seconds, symbolic.duration_seconds)

        # Product Reality #360: a structured score can contain a count-out, trailing
        # measure, alternate ending, or simply run longer than the exact recording.
        # That source material remains immutable evidence, but it must not become
        # playable arrangement notes outside the authoritative audio boundary.
        if recording_duration_seconds is not None:
            if mapped_start >= recording_duration_seconds:
                omitted_trailing_symbolic_count += 1
                if first_omitted_projected_time_seconds is None:
                    first_omitted_projected_time_seconds = mapped_start
                continue
            mapped_duration = min(mapped_duration, recording_duration_seconds - mapped_start)
            if mapped_duration <= 0:
                omitted_trailing_symbolic_count += 1
                if first_omitted_projected_time_seconds is None:
                    first_omitted_projected_time_seconds = mapped_start
                continue

        region_confidence = _alignment_confidence_at(alignment, symbolic.start_seconds)
        nearest = _nearest_unmatched_audio(
            audio.notes,
            used_audio,
            mapped_start,
            onset_tolerance_seconds,
            recording_duration_seconds=recording_duration_seconds,
        )

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
                qualification_reasons=["NO_AUDIO_ONSET"],
                qualification_thresholds={
                    "maximum_matching_onset_delta_seconds": onset_tolerance_seconds,
                },
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
                qualification_reasons=["PITCH_CONFLICT"],
                qualification_observations={
                    "observed_audio_midi": float(audio_note.midi),
                    "expected_symbolic_midi": float(symbolic.midi),
                    "onset_delta_seconds": onset_delta,
                },
                qualification_thresholds={
                    "maximum_matching_onset_delta_seconds": onset_tolerance_seconds,
                },
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

        # Run cheap, established qualification first. A note already
        # untrusted for provenance, onset, confidence or alignment never
        # needs expensive PCM inspection. Only the production project bridge
        # supplies a measured octave-negative probe from a verified stem.
        qualification_args = dict(
            verified_stem=verified_stem_provenance,
            onset_delta=onset_delta,
            audio_note=audio_note,
            region_confidence=region_confidence,
            verified_onset_tolerance_seconds=verified_onset_tolerance_seconds,
            minimum_audio_confidence=minimum_audio_confidence,
            minimum_pitch_confidence=minimum_pitch_confidence,
            minimum_timing_confidence=minimum_timing_confidence,
            minimum_alignment_confidence=minimum_alignment_confidence,
        )
        reasons, observations, thresholds = _note_qualification(**qualification_args)
        if reasons == ["QUALIFIED"] and octave_negative_probe is not None:
            octave_status = octave_negative_probe(
                symbolic.midi, audio_note.start, audio_note.duration
            )
            reasons, observations, thresholds = _note_qualification(
                **qualification_args, octave_screen_status=octave_status
            )
        if reasons == ["QUALIFIED"] and attack_onset_probe is not None:
            attack_evidence = attack_onset_probe(audio_note.start, audio_note.duration)
            reasons, observations, thresholds = _note_qualification(
                **qualification_args, attack_evidence=attack_evidence
            )
        strongly_supported = reasons == ["QUALIFIED"]
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
            qualification_reasons=reasons,
            qualification_observations=observations,
            qualification_thresholds=thresholds,
        ))

    for index, audio_note in enumerate(audio.notes):
        if index in used_audio:
            continue
        if recording_duration_seconds is not None and audio_note.start >= recording_duration_seconds:
            continue
        duration = audio_note.duration
        if recording_duration_seconds is not None:
            duration = min(duration, recording_duration_seconds - audio_note.start)
            if duration <= 0:
                continue
        reconciled.append(ReconciledBassNote(
            start_seconds=audio_note.start,
            duration_seconds=duration,
            midi=audio_note.midi,
            status="audio_only",
            trust_class=SourceTrustClass.audio_derived,
            review_required=True,
            audio_start_seconds=audio_note.start,
            audio_midi=audio_note.midi,
            audio_confidence=audio_note.confidence,
            alignment_confidence=alignment.confidence,
            qualification_reasons=["NO_SYMBOLIC_MATCH"],
            qualification_observations={
                "audio_confidence": audio_note.confidence,
                "audio_pitch_confidence": audio_note.pitch_confidence,
                "audio_timing_confidence": audio_note.timing_confidence,
            },
            qualification_thresholds={
                "maximum_matching_onset_delta_seconds": onset_tolerance_seconds,
            },
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
            audio_evidence_provenance="verified_stem" if verified_stem_provenance else "unqualified",
            source_sha256=source.provenance.source_sha256,
            track_index=alignment.track_index,
            source_content_sha256=source_content_sha256,
            onset_tolerance_seconds=onset_tolerance_seconds,
            verified_onset_tolerance_seconds=verified_onset_tolerance_seconds,
            notes=reconciled,
        ),
        SourceDisagreementReport(
            source_sha256=source.provenance.source_sha256,
            track_index=alignment.track_index,
            source_content_sha256=source_content_sha256,
            disagreements=disagreements,
            omitted_trailing_symbolic_count=omitted_trailing_symbolic_count,
            first_omitted_projected_time_seconds=first_omitted_projected_time_seconds,
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
    manifest = ProjectManifest.load(project_dir)
    verified_stem = is_verified_bass_stem_transcription(project_dir, audio)
    octave_probe = None
    attack_probe = None
    if verified_stem:
        try:
            # Recheck the exact private approved stem identity. The octave
            # negative gate uses only local windows; no model or remote data.
            stem_path = verified_project_stem(project_dir, "bass")
        except (StemSeparationError, OSError, ValueError):
            verified_stem = False
        else:
            def octave_probe(midi: int, start: float, duration: float) -> str:
                return inspect_bass_octave_leakage(
                    stem_path, expected_midi=midi,
                    note_start_seconds=start, note_duration_seconds=duration,
                ).status

            def attack_probe(start: float, duration: float) -> BassAttackEvidence:
                return inspect_bass_attack_onset(
                    stem_path, note_start_seconds=start,
                    note_duration_seconds=duration,
                )
    chart, disagreement_report = reconcile_bass_sources(
        source,
        alignment,
        audio,
        verified_stem_provenance=verified_stem,
        octave_negative_probe=octave_probe,
        attack_onset_probe=attack_probe,
        onset_tolerance_seconds=onset_tolerance_seconds,
        verified_onset_tolerance_seconds=verified_onset_tolerance_seconds,
        source_content_sha256=sha256_file(source_path),
        recording_duration_seconds=manifest.source_metadata.duration_seconds,
    )

    chart_path = project_dir / "charts" / "bass_reconciled.json"
    review_path = project_dir / "review" / "source_disagreements.json"
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.parent.mkdir(parents=True, exist_ok=True)
    chart_path.write_text(chart.model_dump_json(indent=2), encoding="utf-8")
    review_path.write_text(disagreement_report.model_dump_json(indent=2), encoding="utf-8")
    # Every Bass reconciliation produces a local content-delay diagnosis, even
    # when the source remains unqualified. This is not a new musical PASS gate.
    clock_report = write_project_bass_stem_clock_audit(project_dir)
    return {"chart": chart_path, "review": review_path, "stem_clock_audit": clock_report}
