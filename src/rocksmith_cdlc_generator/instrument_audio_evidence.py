"""Tuning-aware Instrument Audio Evidence plan for a selected note/chord event.

Headless core of the Arrangement Preview "Instrument Audio Evidence" section
(issue #787): for one selected event it decides which audio views a reviewer or
an automated qualifier may use (original mix, frequency-focused preview,
separated stem), the audition window on the shared recording clock, and the
pitch band that matters for the instrument's declared tuning.

Audio evidence is advisory. This module never changes score authority, never
reports a view as proof, and fails closed (no views, a named blocker) on any
absent, malformed, or self-contradictory input. A filtered pitch band is a
diagnostic audition aid, not proof of successful source separation.
"""
from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .tuning_contract import explicit_tuning_is_valid

EvidenceView = Literal["original_mix", "frequency_focused", "separated_stem"]
ViewStatus = Literal["available", "stale", "unavailable"]
EvidenceBlocker = Literal[
    "NONE",
    "INVALID_INSTRUMENT_OR_TUNING",
    "INVALID_EVENT_TIME",
    "INVALID_SCORE_PITCH",
    "INVALID_STRING_OR_FRET",
    "PITCH_STRING_FRET_MISMATCH",
    "PITCH_OUTSIDE_AUDIBLE_RANGE",
]

MAX_FRET = 24
# Audition window padding around the event on the shared recording clock.
WINDOW_PAD_S = 0.25
MIN_EVENT_SPAN_S = 0.1
# Focus band: a whole tone below the fundamental up to two octaves above it
# (harmonic content that identifies the note), capped to the usable range.
BAND_LOW_SEMITONES = 2
BAND_HIGH_OCTAVES = 2
MAX_BAND_HZ = 8000.0
MIN_AUDIBLE_HZ = 20.0


class ViewState(BaseModel):
    model_config = ConfigDict(frozen=True)

    view: EvidenceView
    status: ViewStatus
    reason: str
    diagnostic_only: bool


class InstrumentAudioEvidencePlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    blocker_code: EvidenceBlocker
    instrument: str
    event_time_s: float | None = None
    window_start_s: float | None = None
    window_end_s: float | None = None
    low_open_midi: int | None = None
    low_open_hz: float | None = None
    score_midi: int | None = None
    score_hz: float | None = None
    band_low_hz: float | None = None
    band_high_hz: float | None = None
    views: tuple[ViewState, ...] = ()
    default_view: EvidenceView | None = None
    score_authority: Literal["score"] = "score"
    is_proof: Literal[False] = False


def midi_to_hz(midi: int) -> float:
    """Equal-tempered A4 = 440 Hz frequency of a MIDI note."""
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


def _is_int(value: object) -> bool:
    return type(value) is int


def _finite_number(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
    )


def _blocked(blocker: EvidenceBlocker, instrument: object) -> InstrumentAudioEvidencePlan:
    return InstrumentAudioEvidencePlan(
        blocker_code=blocker,
        instrument=instrument if isinstance(instrument, str) else "",
    )


def _views(
    *, has_original_mix: bool, has_stem: bool, stem_is_current: bool
) -> tuple[ViewState, ...]:
    if has_original_mix:
        original = ViewState(
            view="original_mix", status="available",
            reason="Recording mix at the event time.", diagnostic_only=False,
        )
        focused = ViewState(
            view="frequency_focused", status="available",
            reason="Band-limited mix; a diagnostic audition aid, not separation.",
            diagnostic_only=True,
        )
    else:
        original = ViewState(
            view="original_mix", status="unavailable",
            reason="No recording is registered for this project.",
            diagnostic_only=False,
        )
        focused = ViewState(
            view="frequency_focused", status="unavailable",
            reason="Needs the recording mix to filter.", diagnostic_only=True,
        )
    if has_stem and stem_is_current:
        stem = ViewState(
            view="separated_stem", status="available",
            reason="Verified local stem for this instrument.",
            diagnostic_only=False,
        )
    elif has_stem:
        stem = ViewState(
            view="separated_stem", status="stale",
            reason="Stem no longer matches its recording or model; re-separate.",
            diagnostic_only=False,
        )
    else:
        stem = ViewState(
            view="separated_stem", status="unavailable",
            reason="No local stem has been produced for this instrument.",
            diagnostic_only=False,
        )
    return (original, focused, stem)


def _default_view(views: tuple[ViewState, ...]) -> EvidenceView | None:
    by_view = {state.view: state for state in views}
    for preferred in ("separated_stem", "frequency_focused", "original_mix"):
        if by_view[preferred].status == "available":
            return preferred
    return None


def plan_instrument_audio_evidence(
    *,
    instrument: str,
    tuning_midi: list[int] | tuple[int, ...] | None,
    score_midi: int,
    string_index: int,
    fret: int,
    event_time_s: float,
    event_duration_s: float = 0.0,
    has_original_mix: bool = False,
    has_stem: bool = False,
    stem_is_current: bool = False,
) -> InstrumentAudioEvidencePlan:
    """Plan the audio evidence offered beside one selected arrangement event.

    ``string_index`` 0 is the lowest-pitched string of ``tuning_midi``.
    ``stem_is_current`` is only meaningful when ``has_stem`` is true and must
    come from the caller's hash/provenance check, never from file existence.
    """
    if not explicit_tuning_is_valid(instrument, tuning_midi):
        return _blocked("INVALID_INSTRUMENT_OR_TUNING", instrument)
    assert tuning_midi is not None  # narrowed by explicit_tuning_is_valid
    if (
        not _finite_number(event_time_s)
        or event_time_s < 0
        or not _finite_number(event_duration_s)
        or event_duration_s < 0
    ):
        return _blocked("INVALID_EVENT_TIME", instrument)
    if not _is_int(score_midi) or not 0 <= score_midi <= 127:
        return _blocked("INVALID_SCORE_PITCH", instrument)
    if (
        not _is_int(string_index)
        or not _is_int(fret)
        or not 0 <= string_index < len(tuning_midi)
        or not 0 <= fret <= MAX_FRET
    ):
        return _blocked("INVALID_STRING_OR_FRET", instrument)
    if tuning_midi[string_index] + fret != score_midi:
        return _blocked("PITCH_STRING_FRET_MISMATCH", instrument)

    score_hz = midi_to_hz(score_midi)
    if score_hz < MIN_AUDIBLE_HZ or score_hz > MAX_BAND_HZ:
        return _blocked("PITCH_OUTSIDE_AUDIBLE_RANGE", instrument)

    low_open_midi = min(tuning_midi)
    band_low = max(MIN_AUDIBLE_HZ, score_hz * 2.0 ** (-BAND_LOW_SEMITONES / 12.0))
    band_high = min(MAX_BAND_HZ, score_hz * 2.0**BAND_HIGH_OCTAVES)
    span = max(float(event_duration_s), MIN_EVENT_SPAN_S)
    views = _views(
        has_original_mix=bool(has_original_mix),
        has_stem=bool(has_stem),
        stem_is_current=bool(stem_is_current),
    )
    return InstrumentAudioEvidencePlan(
        blocker_code="NONE",
        instrument=instrument,
        event_time_s=float(event_time_s),
        window_start_s=max(0.0, float(event_time_s) - WINDOW_PAD_S),
        window_end_s=float(event_time_s) + span + WINDOW_PAD_S,
        low_open_midi=low_open_midi,
        low_open_hz=midi_to_hz(low_open_midi),
        score_midi=score_midi,
        score_hz=score_hz,
        band_low_hz=band_low,
        band_high_hz=band_high,
        views=views,
        default_view=_default_view(views),
    )
