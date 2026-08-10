from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class BassTuning(BaseModel):
    """Four-string bass tuning, ordered from lowest-pitched string to highest."""

    name: str
    open_midi: tuple[int, int, int, int]

    @model_validator(mode="after")
    def validate_string_order(self) -> "BassTuning":
        if any(pitch < 0 or pitch > 127 for pitch in self.open_midi):
            raise ValueError("Open-string MIDI pitches must be between 0 and 127")
        if any(current <= previous for previous, current in zip(self.open_midi, self.open_midi[1:])):
            raise ValueError("Bass open strings must be strictly ascending in pitch")
        return self


E_STANDARD = BassTuning(name="E Standard", open_midi=(28, 33, 38, 43))
DROP_D = BassTuning(name="Drop D", open_midi=(26, 33, 38, 43))
EB_STANDARD = BassTuning(name="Eb Standard", open_midi=(27, 32, 37, 42))
D_STANDARD = BassTuning(name="D Standard", open_midi=(26, 31, 36, 41))

_TUNINGS = {
    "e-standard": E_STANDARD,
    "e standard": E_STANDARD,
    "standard": E_STANDARD,
    "drop-d": DROP_D,
    "drop d": DROP_D,
    "eb-standard": EB_STANDARD,
    "eb standard": EB_STANDARD,
    "e-flat-standard": EB_STANDARD,
    "e flat standard": EB_STANDARD,
    "d-standard": D_STANDARD,
    "d standard": D_STANDARD,
}


def resolve_bass_tuning(name: str) -> BassTuning:
    key = name.strip().lower()
    try:
        return _TUNINGS[key]
    except KeyError as exc:
        supported = ", ".join(sorted({tuning.name for tuning in _TUNINGS.values()}))
        raise ValueError(f"Unsupported bass tuning {name!r}. Supported tunings: {supported}") from exc


class FretPosition(BaseModel):
    string: int = Field(ge=0, le=3)
    fret: int = Field(ge=0)
    midi: int = Field(ge=0, le=127)


def candidate_positions(
    midi: int,
    tuning: BassTuning,
    *,
    max_fret: int = 24,
) -> list[FretPosition]:
    """Return every playable string/fret location for a MIDI pitch."""

    if max_fret < 0:
        raise ValueError("max_fret must be non-negative")

    positions: list[FretPosition] = []
    for string, open_pitch in enumerate(tuning.open_midi):
        fret = midi - open_pitch
        if 0 <= fret <= max_fret:
            positions.append(FretPosition(string=string, fret=fret, midi=midi))
    return positions
