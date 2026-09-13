from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ClockDiagnosticStatus = Literal["PASS", "FAIL"]


class ClockSample(BaseModel):
    """One playback-clock observation: wall-clock time paired with reported audio position."""

    model_config = ConfigDict(frozen=True)

    wall_clock_seconds: float = Field(ge=0.0)
    position_seconds: float = Field(ge=0.0)


class ClockAnomaly(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    sample_index: int = Field(ge=0)
    wall_clock_seconds: float
    position_seconds: float


class ClockDiagnosticReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    status: ClockDiagnosticStatus
    sample_count: int = Field(ge=0)
    anomalies: list[ClockAnomaly] = Field(default_factory=list)


def analyze_playback_clock_samples(
    samples: list[ClockSample],
    *,
    backward_jump_tolerance_seconds: float = 0.01,
    stall_tolerance_seconds: float = 0.5,
    speed_tolerance_ratio: float = 0.15,
    minimum_interval_seconds: float = 0.05,
) -> ClockDiagnosticReport:
    """Deterministically detect playhead clock anomalies from paired (wall, position) samples.

    Every Arrangement Preview/Timeline poll (`_poll_playback`) observes one
    (wall_clock, position) pair from `ProjectAudioTransport.position_seconds`. This inspects
    consecutive pairs for the shapes issue #561 already named as a perceived-lag risk: the
    reported audio position jumping backward, freezing while wall-clock time keeps moving, or
    drifting away from wall-clock speed by more than a small tolerance. It never touches audio
    hardware or tkinter, so it is safe to run against recorded or synthetic samples in any
    environment, including CI.

    Samples are assumed roughly time-ordered; a non-positive wall-clock delta between two
    consecutive samples (duplicate or out-of-order polls) is skipped rather than flagged, since
    it reflects polling jitter, not a playback clock defect.
    """

    anomalies: list[ClockAnomaly] = []
    for index in range(1, len(samples)):
        previous = samples[index - 1]
        current = samples[index]
        wall_delta = current.wall_clock_seconds - previous.wall_clock_seconds
        position_delta = current.position_seconds - previous.position_seconds

        if wall_delta <= 0:
            continue

        if position_delta < -backward_jump_tolerance_seconds:
            anomalies.append(
                ClockAnomaly(
                    code="clock_backward_jump",
                    message=(
                        f"Playback position moved backward by {-position_delta:.3f}s "
                        f"between samples {index - 1} and {index}."
                    ),
                    sample_index=index,
                    wall_clock_seconds=current.wall_clock_seconds,
                    position_seconds=current.position_seconds,
                )
            )
            continue

        if wall_delta >= stall_tolerance_seconds and position_delta <= 0.0:
            anomalies.append(
                ClockAnomaly(
                    code="clock_stalled",
                    message=(
                        f"Playback position did not advance for {wall_delta:.3f}s of wall-clock "
                        f"time between samples {index - 1} and {index}."
                    ),
                    sample_index=index,
                    wall_clock_seconds=current.wall_clock_seconds,
                    position_seconds=current.position_seconds,
                )
            )
            continue

        if wall_delta >= minimum_interval_seconds:
            speed_error = abs(position_delta - wall_delta) / wall_delta
            if speed_error > speed_tolerance_ratio:
                anomalies.append(
                    ClockAnomaly(
                        code="clock_speed_mismatch",
                        message=(
                            f"Playback position advanced {position_delta:.3f}s while "
                            f"{wall_delta:.3f}s of wall-clock time passed "
                            f"({speed_error:.0%} off expected real-time speed) "
                            f"between samples {index - 1} and {index}."
                        ),
                        sample_index=index,
                        wall_clock_seconds=current.wall_clock_seconds,
                        position_seconds=current.position_seconds,
                    )
                )

    return ClockDiagnosticReport(
        status="FAIL" if anomalies else "PASS",
        sample_count=len(samples),
        anomalies=anomalies,
    )
