from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping, Sequence

_ALLOWED_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "fixture_id",
        "source_kind",
        "arrangement",
        "beat_times_seconds",
        "notes",
    }
)
_ALLOWED_NOTE_KEYS = frozenset(
    {
        "onset_seconds",
        "duration_seconds",
        "string",
        "fret",
        "techniques",
    }
)
_ALLOWED_SOURCE_KINDS = frozenset({"synthetic", "original", "redistributable"})
_ALLOWED_ARRANGEMENTS = frozenset({"bass", "lead", "rhythm"})
_FORBIDDEN_MEDIA_KEYS = frozenset(
    {
        "audio",
        "audio_bytes",
        "audio_path",
        "score",
        "score_bytes",
        "score_path",
        "gp_path",
        "dlc_path",
        "workspace_path",
    }
)


@dataclass(frozen=True)
class EofParityNote:
    onset_seconds: float
    duration_seconds: float
    string: int
    fret: int
    techniques: tuple[str, ...]


@dataclass(frozen=True)
class EofParityFixture:
    schema_version: int
    fixture_id: str
    source_kind: str
    arrangement: str
    beat_times_seconds: tuple[float, ...]
    notes: tuple[EofParityNote, ...]


def _finite_nonnegative(value: Any, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric")
    number = float(value)
    if not isfinite(number) or number < 0:
        raise ValueError(f"{field_name} must be finite and non-negative")
    return number


def _strict_keys(payload: Mapping[str, Any], allowed: frozenset[str], *, scope: str) -> None:
    forbidden = set(payload) & _FORBIDDEN_MEDIA_KEYS
    if forbidden:
        names = ", ".join(sorted(forbidden))
        raise ValueError(f"{scope} contains forbidden media/private path fields: {names}")
    extra = set(payload) - allowed
    if extra:
        names = ", ".join(sorted(extra))
        raise ValueError(f"{scope} contains unsupported fields: {names}")


def _parse_note(payload: Mapping[str, Any], *, index: int) -> EofParityNote:
    _strict_keys(payload, _ALLOWED_NOTE_KEYS, scope=f"notes[{index}]")
    missing = _ALLOWED_NOTE_KEYS - set(payload)
    if missing:
        raise ValueError(f"notes[{index}] missing required fields: {', '.join(sorted(missing))}")

    string = payload["string"]
    fret = payload["fret"]
    if isinstance(string, bool) or not isinstance(string, int) or string < 0:
        raise ValueError(f"notes[{index}].string must be a non-negative integer")
    if isinstance(fret, bool) or not isinstance(fret, int) or fret < 0:
        raise ValueError(f"notes[{index}].fret must be a non-negative integer")

    raw_techniques = payload["techniques"]
    if not isinstance(raw_techniques, Sequence) or isinstance(raw_techniques, (str, bytes)):
        raise ValueError(f"notes[{index}].techniques must be a sequence of strings")
    techniques = tuple(str(item).strip() for item in raw_techniques)
    if any(not technique for technique in techniques):
        raise ValueError(f"notes[{index}].techniques may not contain empty names")
    if len(set(techniques)) != len(techniques):
        raise ValueError(f"notes[{index}].techniques may not contain duplicates")

    return EofParityNote(
        onset_seconds=_finite_nonnegative(
            payload["onset_seconds"], field_name=f"notes[{index}].onset_seconds"
        ),
        duration_seconds=_finite_nonnegative(
            payload["duration_seconds"], field_name=f"notes[{index}].duration_seconds"
        ),
        string=string,
        fret=fret,
        techniques=techniques,
    )


def parse_eof_parity_fixture(payload: Mapping[str, Any]) -> EofParityFixture:
    """Parse a media-free EOF-vs-generator differential fixture.

    The committed fixture contains only deterministic expected metadata. Commercial
    audio, score images, GP files, DLC, and private workspace paths are deliberately
    outside this contract and must remain local/private.
    """

    _strict_keys(payload, _ALLOWED_TOP_LEVEL_KEYS, scope="fixture")
    missing = _ALLOWED_TOP_LEVEL_KEYS - set(payload)
    if missing:
        raise ValueError(f"fixture missing required fields: {', '.join(sorted(missing))}")

    if payload["schema_version"] != 1:
        raise ValueError("unsupported EOF parity fixture schema_version")

    fixture_id = payload["fixture_id"]
    if not isinstance(fixture_id, str) or not fixture_id.strip():
        raise ValueError("fixture_id must be a non-empty string")

    source_kind = payload["source_kind"]
    if source_kind not in _ALLOWED_SOURCE_KINDS:
        raise ValueError("source_kind must be synthetic, original, or redistributable")

    arrangement = payload["arrangement"]
    if arrangement not in _ALLOWED_ARRANGEMENTS:
        raise ValueError("arrangement must be bass, lead, or rhythm")

    raw_beats = payload["beat_times_seconds"]
    if not isinstance(raw_beats, Sequence) or isinstance(raw_beats, (str, bytes)):
        raise ValueError("beat_times_seconds must be a sequence")
    beats = tuple(
        _finite_nonnegative(value, field_name=f"beat_times_seconds[{index}]")
        for index, value in enumerate(raw_beats)
    )
    if any(later <= earlier for earlier, later in zip(beats, beats[1:], strict=False)):
        raise ValueError("beat_times_seconds must be strictly increasing")

    raw_notes = payload["notes"]
    if not isinstance(raw_notes, Sequence) or isinstance(raw_notes, (str, bytes)):
        raise ValueError("notes must be a sequence")
    notes: list[EofParityNote] = []
    for index, note in enumerate(raw_notes):
        if not isinstance(note, Mapping):
            raise ValueError(f"notes[{index}] must be an object")
        notes.append(_parse_note(note, index=index))

    return EofParityFixture(
        schema_version=1,
        fixture_id=fixture_id.strip(),
        source_kind=source_kind,
        arrangement=arrangement,
        beat_times_seconds=beats,
        notes=tuple(notes),
    )
