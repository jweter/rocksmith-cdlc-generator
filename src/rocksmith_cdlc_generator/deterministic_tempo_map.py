from __future__ import annotations

from pydantic import BaseModel, Field

from .beats import BeatEvent, TempoMap

DETERMINISTIC_ENGINE_NAME = "deterministic-notation-tempo"
DETERMINISTIC_ENGINE_VERSION = "1"


class TempoChange(BaseModel):
    """A tempo change taking effect starting at ``measure`` (1-indexed, inclusive)."""

    measure: int = Field(ge=1)
    bpm: float = Field(gt=0.0)


def build_deterministic_tempo_map(
    *,
    measure_count: int,
    bpm: float,
    time_signature_numerator: int = 4,
    time_signature_denominator: int = 4,
    tempo_changes: list[TempoChange] | None = None,
) -> TempoMap:
    """Build a self-consistent tempo/measure map with no recording anchor.

    Used for printed-notation/TAB practice arrangements, where the printed score is
    the sole timing authority: there is no commercial recording to align against, so
    internal consistency (every beat/measure boundary following deterministically
    from the previous one) is what matters, not agreement with an external waveform.

    Beat 1 of measure 1 starts at ``time=0.0``. Only tempo changes are supported in
    this slice; the time signature is constant for the whole map (mid-song time
    signature changes are a documented future extension, see
    docs/printed-notation-tab-practice-mode.md).
    """

    if measure_count < 1:
        raise ValueError("measure_count must be at least 1")

    changes_by_measure = {1: bpm}
    for change in sorted(tempo_changes or [], key=lambda change: change.measure):
        if change.measure > measure_count:
            raise ValueError(
                f"Tempo change at measure {change.measure} is beyond measure_count={measure_count}"
            )
        changes_by_measure[change.measure] = change.bpm

    beats: list[BeatEvent] = []
    current_bpm = bpm
    time = 0.0
    for measure in range(1, measure_count + 1):
        if measure in changes_by_measure:
            current_bpm = changes_by_measure[measure]
        seconds_per_beat = 60.0 / current_bpm * (4.0 / time_signature_denominator)
        for beat in range(1, time_signature_numerator + 1):
            beats.append(
                BeatEvent(
                    time=time,
                    beat=beat,
                    measure=measure,
                    bpm=current_bpm,
                    confidence=1.0,
                    is_downbeat=(beat == 1),
                )
            )
            time += seconds_per_beat

    return TempoMap(
        engine=DETERMINISTIC_ENGINE_NAME,
        engine_version=DETERMINISTIC_ENGINE_VERSION,
        time_signature_numerator=time_signature_numerator,
        time_signature_denominator=time_signature_denominator,
        beats=beats,
    )
