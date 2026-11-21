"""Privacy-safe diagnosis of why an existing audio transcription cannot qualify timing.

This module NEVER changes confidence, reruns expensive pYIN, copies private music,
or declares a score aligned. It identifies the missing *capability*, rather than
sending the owner back through manual tests or treating every repeated project
as an independent audio recording.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .transcription import read_transcription


AudioGapCode = Literal[
    "NONE",
    "BASS_TRANSCRIPTION_MISSING",
    "BASS_TRANSCRIPTION_UNREADABLE",
    "NO_BASS_NOTES",
    "FULL_MIX_PYIN_UNQUALIFIED",
    "STEM_AVAILABLE_UNQUALIFIED_MIX",
    "BASS_STEM_UNQUALIFIED",
    "UNQUALIFIED_UNKNOWN_SOURCE",
    "AMBIGUOUS_ALIGNMENT",
]
AudioRecoveryDependency = Literal[
    "NONE",
    "BASS_AUDIO_TRANSCRIPTION",
    "VALIDATE_EXISTING_TRANSCRIPTION",
    "PRIVATE_BASS_STEM_SEPARATION",
    "INDEPENDENT_STEM_TRANSCRIPTION",
    "ALTERNATE_PITCH_ORACLE",
    "INSPECT_AUDIO_SOURCE_PROVENANCE",
    "INDEPENDENT_TIMING_ORACLE",
]
AudioInputClass = Literal["none", "full_mix", "bass_stem", "other"]


class AudioEvidenceGap(BaseModel):
    model_config = ConfigDict(frozen=True)

    blocker_code: AudioGapCode
    next_automation_dependency: AudioRecoveryDependency
    audio_input_class: AudioInputClass


_CLEAR = AudioEvidenceGap(
    blocker_code="NONE",
    next_automation_dependency="NONE",
    audio_input_class="none",
)


def _gap(
    blocker: AudioGapCode,
    dependency: AudioRecoveryDependency,
    input_class: AudioInputClass = "none",
) -> AudioEvidenceGap:
    return AudioEvidenceGap(
        blocker_code=blocker,
        next_automation_dependency=dependency,
        audio_input_class=input_class,
    )


def classify_audio_evidence_gap(
    project: Path,
    *,
    qualification_status: str,
    total_audio_notes: int | None,
    usable_audio_notes: int,
) -> AudioEvidenceGap:
    """Classify local source quality; only qualification may assert PASS/FAIL.

    The distinction between *analyzed full mix* and a separated bass stem is
    essential: pYIN can emit hundreds of low-confidence guesses from a
    polyphonic recording. Such guesses do not establish Bass note onsets,
    pitches or a global source offset. Never lower the qualification floor.
    """

    if qualification_status != "insufficient_evidence":
        return _CLEAR

    bass = project / "analysis" / "bass_raw.json"
    if not bass.is_file():
        return _gap("BASS_TRANSCRIPTION_MISSING", "BASS_AUDIO_TRANSCRIPTION")
    try:
        transcription = read_transcription(bass)
    except (OSError, ValueError):
        return _gap("BASS_TRANSCRIPTION_UNREADABLE", "VALIDATE_EXISTING_TRANSCRIPTION")

    source_name = transcription.source_path.replace("\\", "/").rsplit("/", 1)[-1].casefold()
    if source_name == "normalized.wav":
        input_class: AudioInputClass = "full_mix"
    elif source_name == "bass.wav":
        input_class = "bass_stem"
    else:
        input_class = "other"

    if not transcription.notes or total_audio_notes == 0:
        return _gap("NO_BASS_NOTES", "ALTERNATE_PITCH_ORACLE", input_class)

    if usable_audio_notes == 0:
        if input_class == "full_mix" and transcription.engine == "librosa-pyin":
            if (project / "stems" / "bass.wav").is_file():
                return _gap(
                    "STEM_AVAILABLE_UNQUALIFIED_MIX",
                    "INDEPENDENT_STEM_TRANSCRIPTION",
                    input_class,
                )
            return _gap(
                "FULL_MIX_PYIN_UNQUALIFIED",
                "PRIVATE_BASS_STEM_SEPARATION",
                input_class,
            )
        if input_class == "bass_stem":
            return _gap(
                "BASS_STEM_UNQUALIFIED",
                "ALTERNATE_PITCH_ORACLE",
                input_class,
            )
        return _gap(
            "UNQUALIFIED_UNKNOWN_SOURCE",
            "INSPECT_AUDIO_SOURCE_PROVENANCE",
            input_class,
        )

    return _gap("AMBIGUOUS_ALIGNMENT", "INDEPENDENT_TIMING_ORACLE", input_class)
