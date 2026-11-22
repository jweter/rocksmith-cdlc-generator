"""Bounded host RAM-pressure admission immediately before optional model launch.

The operating system's *available physical* memory naturally reflects
unrelated Windows/laptop workloads. A previous file/model readiness PASS is
not proof that RAM is still available when the child process starts.

No process names, PIDs, windows, filesystem paths, models, audio, downloads,
or networking are inspected. This is admission evidence only, never a proof
of model peak RAM, a network sandbox, or launch authorization.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import time
from typing import Callable

from .auto_cdlc_readiness import available_memory_gib

# Keep the existing model pilot floor and a modest guard margin for
# unrelated tasks that can grow between sampling and child creation.
MODEL_PILOT_RAM_FLOOR_GIB = 7.0
HOST_CONCURRENCY_HEADROOM_GIB = 0.5
HOST_RAM_SAMPLES = 3
SAMPLE_INTERVAL_SECONDS = 0.05


@dataclass(frozen=True)
class HostConcurrencyAdmission:
    status: str
    code: str
    minimum_observed_available_ram_gib: float | None
    sample_count: int
    required_available_ram_gib: float
    model_execution_authorized: bool = False
    network_isolation_proven: bool = False
    actual_model_ram_peak_measured: bool = False

    @property
    def admitted(self) -> bool:
        return self.status == "STABLE_HOST_HEADROOM"

    def public_dict(self) -> dict:
        """Sanitized aggregate evidence only: no process identity or paths."""
        return asdict(self)


def inspect_host_concurrency(
    *,
    available_probe: Callable[[], float] | None = None,
    sleep: Callable[[float], None] | None = None,
    minimum_available_ram_gib: float = MODEL_PILOT_RAM_FLOOR_GIB,
    headroom_gib: float = HOST_CONCURRENCY_HEADROOM_GIB,
    samples: int = HOST_RAM_SAMPLES,
    interval_seconds: float = SAMPLE_INTERVAL_SECONDS,
) -> HostConcurrencyAdmission:
    """Read physical RAM repeatedly; any low/invalid sample must defer.

    No model starts and no executable is launched. This guard is repeated
    in the actual separator adapter *immediately before subprocess.run*
    to close the prior readiness-to-launch resource-pressure gap.
    """
    for name, value, lo, hi in (
        ("minimum_available_ram_gib", minimum_available_ram_gib, 0.25, 64.0),
        ("headroom_gib", headroom_gib, 0.0, 16.0),
        ("interval_seconds", interval_seconds, 0.0, 0.5),
    ):
        if (type(value) not in (int, float) or not math.isfinite(value)
                or not lo <= value <= hi):
            raise ValueError("INVALID_HOST_CONCURRENCY_" + name.upper())
    if type(samples) is not int or not 2 <= samples <= 5:
        raise ValueError("INVALID_HOST_CONCURRENCY_SAMPLE_COUNT")
    probe = available_probe if available_probe is not None else available_memory_gib
    pause = sleep if sleep is not None else time.sleep
    if not callable(probe) or not callable(pause):
        raise ValueError("INVALID_HOST_CONCURRENCY_PROBE")
    floor = float(minimum_available_ram_gib + headroom_gib)
    minimum: float | None = None
    count = 0

    def result(status: str, code: str) -> HostConcurrencyAdmission:
        return HostConcurrencyAdmission(
            status=status,
            code=code,
            minimum_observed_available_ram_gib=(
                round(minimum, 3) if minimum is not None else None
            ),
            sample_count=count,
            required_available_ram_gib=round(floor, 3),
        )

    for index in range(samples):
        if index:
            # Bounded 0.2-second maximum observation interval for 5 samples.
            try:
                pause(interval_seconds)
            except (OSError, ValueError, TypeError):
                return result("DEFERRED", "HOST_CONCURRENCY_SENSOR_UNAVAILABLE")
        try:
            measurement = probe()
            if type(measurement) not in (int, float):
                return result("DEFERRED", "HOST_CONCURRENCY_SENSOR_UNAVAILABLE")
            available = float(measurement)
        except (OSError, ValueError, TypeError, OverflowError):
            return result("DEFERRED", "HOST_CONCURRENCY_SENSOR_UNAVAILABLE")
        if not math.isfinite(available) or available < 0:
            return result("DEFERRED", "HOST_CONCURRENCY_SENSOR_UNAVAILABLE")
        count += 1
        minimum = available if minimum is None else min(minimum, available)
        if available < floor:
            return result("DEFERRED", "HOST_CONCURRENCY_RAM_PRESSURE")

    return result("STABLE_HOST_HEADROOM", "HOST_CONCURRENCY_CHECK_PASSED")
