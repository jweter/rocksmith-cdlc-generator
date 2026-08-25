from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .reviewed_bass_authoring import (
    ReviewedBassAuthoringInput,
    reviewed_bass_authoring_input,
)
from .reviewed_guitar_authoring import (
    ReviewedGuitarAuthoringInput,
    reviewed_guitar_authoring_input,
)
from .rocksmith_xml import DIRECT_NOTE_TECHNIQUES
from .score_source import ArrangementRole
from .source_import import SourceTrustClass


class ReviewedRocksmithXmlNote(BaseModel):
    """One provenance-bearing note ready for the Rocksmith XML boundary."""

    model_config = ConfigDict(frozen=True)

    source_event_index: int = Field(ge=0)
    continuation_source_event_indices: list[int] = Field(default_factory=list)
    time_seconds: float = Field(ge=0)
    duration_seconds: float = Field(gt=0)
    midi: int = Field(ge=0, le=127)
    string_index: int = Field(ge=0, le=5)
    fret: int = Field(ge=0)
    techniques: list[str] = Field(default_factory=list)
    import_confidence: float = Field(ge=0, le=1)
    trust_class: SourceTrustClass

    @model_validator(mode="after")
    def continuation_lineage_is_unique(self) -> "ReviewedRocksmithXmlNote":
        if self.continuation_source_event_indices != sorted(self.continuation_source_event_indices):
            raise ValueError("Rocksmith tie continuation source-event indexes must remain ordered")
        if len(self.continuation_source_event_indices) != len(set(self.continuation_source_event_indices)):
            raise ValueError("Rocksmith tie continuation source-event indexes must be unique")
        if self.source_event_index in self.continuation_source_event_indices:
            raise ValueError("Rocksmith tie continuation lineage cannot repeat its primary event")
        return self


class ReviewedRocksmithXmlChord(BaseModel):
    """One explicitly reviewed guitar chord without invented names or fingering."""

    model_config = ConfigDict(frozen=True)

    source_event_indices: list[int]
    time_seconds: float = Field(ge=0)
    sustain_seconds: float = Field(gt=0)
    shape: tuple[int, int, int, int, int, int]
    notes: list[ReviewedRocksmithXmlNote]

    @model_validator(mode="after")
    def exact_membership(self) -> "ReviewedRocksmithXmlChord":
        indices = [note.source_event_index for note in self.notes]
        if len(indices) < 2:
            raise ValueError("reviewed Rocksmith chord requires at least two notes")
        if indices != self.source_event_indices:
            raise ValueError("reviewed Rocksmith chord membership must preserve source-event identity")
        strings = [note.string_index for note in self.notes]
        if len(strings) != len(set(strings)):
            raise ValueError("reviewed Rocksmith chord cannot contain duplicate strings")
        return self


class ReviewedRocksmithXmlInput(BaseModel):
    """Read-only, reviewed arrangement facts at the Rocksmith XML handoff boundary."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    role: ArrangementRole
    source_track_index: int = Field(ge=0)
    source_output_json: str
    source_output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    recording_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tuning_midi: tuple[int, ...]
    notes: list[ReviewedRocksmithXmlNote]
    chords: list[ReviewedRocksmithXmlChord] = Field(default_factory=list)
    human_confirmed_timing: Literal[True] = True

    @model_validator(mode="after")
    def arrangement_contract(self) -> "ReviewedRocksmithXmlInput":
        expected_strings = 4 if self.role is ArrangementRole.bass else 6
        if len(self.tuning_midi) != expected_strings:
            raise ValueError(
                f"reviewed {self.role.value} Rocksmith XML input requires {expected_strings}-string tuning"
            )
        if not self.notes:
            raise ValueError("reviewed Rocksmith XML input requires at least one note")
        times = [note.time_seconds for note in self.notes]
        if times != sorted(times):
            raise ValueError("reviewed Rocksmith XML notes must remain ordered")
        if self.role is ArrangementRole.bass and self.chords:
            raise ValueError("Bass Rocksmith XML input cannot contain guitar chord groups")
        return self


def _xml_note(note) -> ReviewedRocksmithXmlNote:
    unsupported = sorted(set(note.techniques) - DIRECT_NOTE_TECHNIQUES)
    if unsupported:
        names = ", ".join(unsupported)
        raise ValueError(
            f"source event {note.source_event_index} has Rocksmith XML techniques "
            f"that are not losslessly supported yet: {names}"
        )
    return ReviewedRocksmithXmlNote(
        source_event_index=note.source_event_index,
        continuation_source_event_indices=list(note.continuation_source_event_indices),
        time_seconds=note.time_seconds,
        duration_seconds=note.duration_seconds,
        midi=note.midi,
        string_index=note.string_index,
        fret=note.fret,
        techniques=list(note.techniques),
        import_confidence=note.import_confidence,
        trust_class=note.trust_class,
    )


def rocksmith_xml_input_from_reviewed_bass(
    authoring: ReviewedBassAuthoringInput,
) -> ReviewedRocksmithXmlInput:
    """Normalize reviewed Bass facts for XML construction without writing XML."""

    notes = [_xml_note(note) for note in authoring.notes]
    return ReviewedRocksmithXmlInput(
        role=ArrangementRole.bass,
        source_track_index=authoring.source_track_index,
        source_output_json=authoring.source_output_json,
        source_output_sha256=authoring.source_output_sha256,
        recording_sha256=authoring.recording_sha256,
        score_sha256=authoring.score_sha256,
        tuning_midi=authoring.tuning_midi,
        notes=notes,
        human_confirmed_timing=True,
    )


def rocksmith_xml_input_from_reviewed_guitar(
    authoring: ReviewedGuitarAuthoringInput,
) -> ReviewedRocksmithXmlInput:
    """Normalize reviewed Lead/Rhythm facts while preserving explicit chord identity."""

    notes = [_xml_note(note) for note in authoring.notes]
    by_index = {note.source_event_index: note for note in notes}
    chords: list[ReviewedRocksmithXmlChord] = []
    for group in authoring.chord_groups:
        chord_notes = [by_index[index] for index in group.source_event_indices]
        shape = tuple(
            next(
                (note.fret for note in chord_notes if note.string_index == string_index),
                -1,
            )
            for string_index in range(6)
        )
        chords.append(
            ReviewedRocksmithXmlChord(
                source_event_indices=list(group.source_event_indices),
                time_seconds=min(note.time_seconds for note in chord_notes),
                sustain_seconds=max(note.duration_seconds for note in chord_notes),
                shape=shape,
                notes=chord_notes,
            )
        )
    return ReviewedRocksmithXmlInput(
        role=authoring.role,
        source_track_index=authoring.source_track_index,
        source_output_json=authoring.source_output_json,
        source_output_sha256=authoring.source_output_sha256,
        recording_sha256=authoring.recording_sha256,
        score_sha256=authoring.score_sha256,
        tuning_midi=authoring.tuning_midi,
        notes=notes,
        chords=chords,
        human_confirmed_timing=True,
    )


def reviewed_rocksmith_xml_input(
    project_dir: Path,
    role: ArrangementRole,
) -> ReviewedRocksmithXmlInput:
    """Read current reviewed authority into the XML handoff model without side effects.

    This boundary emits no XML, writes no project artifact, performs no packaging, and
    does not infer musical identity. Unsupported technique semantics fail closed.
    """

    if role is ArrangementRole.bass:
        return rocksmith_xml_input_from_reviewed_bass(reviewed_bass_authoring_input(project_dir))
    if role in {ArrangementRole.lead, ArrangementRole.rhythm}:
        return rocksmith_xml_input_from_reviewed_guitar(reviewed_guitar_authoring_input(project_dir, role))
    raise ValueError(f"unsupported Rocksmith arrangement role: {role}")
